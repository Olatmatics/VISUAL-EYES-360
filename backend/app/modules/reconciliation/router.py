from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import allowed_station_ids, get_current_user, require_permission, write_audit
from app.db.base import get_db
from app.models.auth import User
from app.models.core import (
    Dispenser, FuelTransaction, Nozzle, PumpReconciliation, SystemAlert, Tank, TankDelivery, TankReconciliation,
)
from app.modules.alerts.service import create_alert

router = APIRouter(prefix="/api/v1/reconciliation", tags=["reconciliation"])


@router.get("/pulser")
def pulser_reconciliation_summary(
    station_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(FuelTransaction)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        stmt = stmt.where(FuelTransaction.station_id.in_(allowed))
    if station_id:
        stmt = stmt.where(FuelTransaction.station_id == station_id)

    txs = db.scalars(stmt).all()
    total_cpu = sum(t.dispenser_cpu_volume for t in txs)
    total_pulser = sum(t.independent_pulser_volume for t in txs)
    discrepant_txs = [t for t in txs if t.discrepancy_alert]
    discrepancy_count = len(discrepant_txs)
    total_delta = abs(round(total_cpu - total_pulser, 3))
    compliance = round((1 - (discrepancy_count / len(txs))) * 100, 1) if txs else 100.0

    return {
        "total_transactions": len(txs),
        "total_cpu_volume_l": round(total_cpu, 2),
        "total_pulser_volume_l": round(total_pulser, 2),
        "cumulative_difference_l": total_delta,
        "discrepancy_incidents": discrepancy_count,
        "compliance_rate_percent": compliance,
        "investigation_threshold_l": 0.490,
    }


@router.get("/tanks")
def list_tank_reconciliations(
    station_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(TankReconciliation).order_by(desc(TankReconciliation.recorded_at))
    allowed = allowed_station_ids(user)
    if allowed is not None:
        stmt = stmt.where(TankReconciliation.station_id.in_(allowed))
    if station_id:
        stmt = stmt.where(TankReconciliation.station_id == station_id)

    records = db.scalars(stmt.limit(50)).all()
    res = []
    for r in records:
        res.append({
            "id": r.id,
            "station_name": r.station.name if r.station else "",
            "tank_code": r.tank.code if r.tank else "",
            "shift_date": r.shift_date,
            "opening_stock_l": r.opening_stock_l,
            "deliveries_l": r.deliveries_l,
            "sales_cpu_l": r.sales_cpu_l,
            "sales_pulser_l": r.sales_pulser_l,
            "expected_closing_stock_l": r.expected_closing_stock_l,
            "actual_atg_closing_stock_l": r.actual_atg_closing_stock_l,
            "variance_l": r.variance_l,
            "variance_percentage": r.variance_percentage,
            "status": r.status,
            "investigation_notes": r.investigation_notes,
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
        })
    return res


@router.post("/tanks/run", status_code=status.HTTP_201_CREATED)
def run_tank_reconciliation(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tank_reconciliation", "manage")),
):
    """Reconcile one tank from real transactions, verified deliveries and ATG stock.

    Historical records are never overwritten — each run appends a new record.
    """
    tank = db.scalar(select(Tank).where(Tank.id == payload.get("tank_id")))
    if tank is None:
        raise HTTPException(status_code=404, detail="Tank not found")
    allowed = allowed_station_ids(user)
    if allowed is not None and tank.station_id not in allowed:
        raise HTTPException(status_code=403, detail="Station access denied")

    end = datetime.now(timezone.utc).replace(tzinfo=None)
    start = end - timedelta(days=int(payload.get("period_days", 1)))
    if payload.get("date_from"):
        start = datetime.fromisoformat(payload["date_from"])
    if payload.get("date_to"):
        end = datetime.fromisoformat(payload["date_to"]).replace(hour=23, minute=59, second=59)

    if payload.get("opening_stock_l") is not None:
        opening = float(payload["opening_stock_l"])
    else:
        prior = db.scalar(
            select(TankReconciliation).where(TankReconciliation.tank_id == tank.id)
            .order_by(desc(TankReconciliation.recorded_at))
        )
        opening = prior.actual_atg_closing_stock_l if prior else tank.current_volume_l

    if payload.get("deliveries_l") is not None:
        deliveries = float(payload["deliveries_l"])
    else:
        deliveries = float(db.scalar(
            select(func.coalesce(func.sum(TankDelivery.received_quantity_l), 0.0)).where(
                TankDelivery.tank_id == tank.id,
                TankDelivery.status == "VERIFIED",
                TankDelivery.delivery_date >= start,
                TankDelivery.delivery_date <= end,
            )
        ) or 0.0)

    nozzle_ids = db.scalars(select(Nozzle.id).where(Nozzle.tank_id == tank.id)).all()
    sales_cpu = 0.0
    sales_pulser = 0.0
    if nozzle_ids:
        totals = db.execute(
            select(
                func.coalesce(func.sum(FuelTransaction.dispenser_cpu_volume), 0.0),
                func.coalesce(func.sum(FuelTransaction.independent_pulser_volume), 0.0),
            ).where(
                FuelTransaction.nozzle_id.in_(nozzle_ids),
                FuelTransaction.started_at >= start,
                FuelTransaction.started_at <= end,
            )
        ).one()
        sales_cpu, sales_pulser = float(totals[0]), float(totals[1])

    actual = float(payload.get("actual_closing_l", tank.current_volume_l))
    expected = round(opening + deliveries - sales_cpu, 2)
    variance = round(actual - expected, 2)
    variance_pct = round(abs(variance) / expected * 100, 2) if expected > 0 else 0.0

    if variance_pct > settings.TANK_VARIANCE_CRITICAL_PCT:
        status_label = "CRITICAL_INVESTIGATION"
        create_alert(
            db,
            alert_type="TANK_INVENTORY_VARIANCE",
            category="FUEL_DISCREPANCY",
            severity="CRITICAL",
            title=f"Significant tank variance on {tank.code}",
            description=(
                f"Variance {variance:.2f} L ({variance_pct}%). Expected {expected} L, "
                f"actual ATG {actual} L over {start:%Y-%m-%d} to {end:%Y-%m-%d}."
            ),
            station_id=tank.station_id,
            entity_type="tank",
            entity_id=tank.id,
            expected_value=expected,
            actual_value=actual,
            discrepancy=variance,
        )
    elif variance_pct > settings.TANK_VARIANCE_WARNING_PCT:
        status_label = "WARNING"
    else:
        status_label = "NORMAL"

    rec = TankReconciliation(
        tank_id=tank.id,
        station_id=tank.station_id,
        shift_date=end.strftime("%Y-%m-%d"),
        opening_stock_l=round(opening, 2),
        deliveries_l=round(deliveries, 2),
        sales_cpu_l=round(sales_cpu, 2),
        sales_pulser_l=round(sales_pulser, 2),
        expected_closing_stock_l=expected,
        actual_atg_closing_stock_l=round(actual, 2),
        variance_l=variance,
        variance_percentage=variance_pct,
        status=status_label,
        investigation_notes=payload.get("notes"),
        recorded_at=end,
    )
    db.add(rec)
    db.flush()
    write_audit(db, user, "RUN_TANK_RECONCILIATION", "TankReconciliation", rec.id,
                after={"tank_id": tank.id, "variance_l": variance, "status": status_label}, request=request)
    db.commit()
    return {
        "id": rec.id, "variance_l": rec.variance_l, "variance_percentage": variance_pct,
        "status": rec.status, "opening_stock_l": rec.opening_stock_l,
        "deliveries_l": rec.deliveries_l, "sales_cpu_l": rec.sales_cpu_l,
        "expected_closing_stock_l": expected, "actual_closing_stock_l": actual,
    }


@router.get("/pumps")
def list_pump_reconciliations(
    station_id: str | None = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(PumpReconciliation).order_by(desc(PumpReconciliation.recorded_at))
    allowed = allowed_station_ids(user)
    if allowed is not None:
        stmt = stmt.where(PumpReconciliation.station_id.in_(allowed))
    if station_id:
        stmt = stmt.where(PumpReconciliation.station_id == station_id)
    return db.scalars(stmt.limit(limit)).all()


@router.post("/pumps/run", status_code=status.HTTP_201_CREATED)
def run_pump_reconciliation(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("pulser", "manage")),
):
    """Reconcile one nozzle against POS, FCC/CPU meter, pulser and totalizer readings."""
    nozzle = db.scalar(select(Nozzle).where(Nozzle.id == payload.get("nozzle_id")))
    if nozzle is None:
        raise HTTPException(status_code=404, detail="Nozzle not found")
    dispenser = db.scalar(select(Dispenser).where(Dispenser.id == nozzle.dispenser_id))
    station_id = dispenser.station_id if dispenser else None
    allowed = allowed_station_ids(user)
    if allowed is not None and station_id not in allowed:
        raise HTTPException(status_code=403, detail="Station access denied")

    end = datetime.now(timezone.utc).replace(tzinfo=None)
    start = end - timedelta(days=int(payload.get("period_days", 1)))
    if payload.get("date_from"):
        start = datetime.fromisoformat(payload["date_from"])
    if payload.get("date_to"):
        end = datetime.fromisoformat(payload["date_to"]).replace(hour=23, minute=59, second=59)

    txs = db.scalars(
        select(FuelTransaction).where(
            FuelTransaction.nozzle_id == nozzle.id,
            FuelTransaction.started_at >= start,
            FuelTransaction.started_at <= end,
        )
    ).all()
    pos_volume = round(sum(t.requested_volume for t in txs), 2)
    fcc_volume = round(
        sum(t.dispenser_cpu_volume for t in txs if getattr(t, "fcc_device_id", None)), 2
    )
    cpu_volume = round(sum(t.dispenser_cpu_volume for t in txs), 2)
    pulser_volume = round(sum(t.independent_pulser_volume for t in txs), 2)

    previous = float(payload.get("previous_totalizer_l", nozzle.previous_totalizer_l or 0))
    current = float(payload.get("current_totalizer_l", nozzle.totalizer_l or 0))
    calculated = round(current - previous, 2)
    expected = fcc_volume or pos_volume or cpu_volume
    actual = pulser_volume or calculated or cpu_volume
    variance = round(actual - expected, 2)
    variance_pct = round(abs(variance) / expected * 100, 2) if expected else 0.0

    threshold = settings.PUMP_DISCREPANCY_THRESHOLD_L
    if abs(variance) > threshold:
        status_label = "CRITICAL_INVESTIGATION"
        create_alert(
            db,
            alert_type="CPU_PULSER_DISCREPANCY",
            category="FUEL_DISCREPANCY",
            severity="CRITICAL" if abs(variance) > threshold * 4 else "HIGH",
            title=f"Dispenser reconciliation variance on nozzle {nozzle.label}",
            description=(
                f"POS {pos_volume} L, FCC {fcc_volume} L, CPU {cpu_volume} L, "
                f"pulser {pulser_volume} L, totalizer delta {calculated} L. Variance {variance} L."
            ),
            station_id=station_id,
            device_type="FCC_CONTROLLER",
            entity_type="nozzle",
            entity_id=nozzle.id,
            expected_value=expected,
            actual_value=actual,
            discrepancy=variance,
        )
    elif variance_pct > settings.TANK_VARIANCE_WARNING_PCT:
        status_label = "WARNING"
    else:
        status_label = "NORMAL"

    record = PumpReconciliation(
        station_id=station_id,
        dispenser_id=nozzle.dispenser_id,
        nozzle_id=nozzle.id,
        shift_date=end.strftime("%Y-%m-%d"),
        product_id=nozzle.product_id,
        pos_volume_l=pos_volume,
        fcc_volume_l=fcc_volume,
        previous_totalizer_l=round(previous, 2),
        current_totalizer_l=round(current, 2),
        cpu_volume_l=cpu_volume,
        pulser_volume_l=pulser_volume,
        calculated_volume_l=calculated,
        expected_volume_l=round(expected, 2),
        actual_volume_l=round(actual, 2),
        variance_l=variance,
        variance_percentage=variance_pct,
        status=status_label,
        recorded_at=end,
    )
    db.add(record)
    db.flush()
    write_audit(db, user, "RUN_PUMP_RECONCILIATION", "PumpReconciliation", record.id,
                after={"nozzle_id": nozzle.id, "variance_l": variance, "status": status_label}, request=request)
    db.commit()
    return {"id": record.id, "variance_l": variance, "status": status_label,
            "pos_volume_l": pos_volume, "fcc_volume_l": fcc_volume,
            "cpu_volume_l": cpu_volume, "pulser_volume_l": pulser_volume,
            "calculated_volume_l": calculated}
