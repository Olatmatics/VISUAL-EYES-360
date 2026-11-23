from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session
from app.core.deps import allowed_station_ids, get_current_user, require_permission
from app.db.base import get_db
from app.models.auth import User
from app.models.core import FuelTransaction, SystemAlert, Tank, TankReconciliation

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
def run_tank_reconciliation(payload: dict[str, Any], db: Session = Depends(get_db), user: User = Depends(require_permission("tank_reconciliation", "manage"))):
    tank_id = payload.get("tank_id")
    tank = db.scalar(select(Tank).where(Tank.id == tank_id))
    if not tank:
        raise HTTPException(status_code=404, detail="Tank not found")

    opening_stock = float(payload.get("opening_stock_l", tank.current_volume_l + 2500.0))
    deliveries = float(payload.get("deliveries_l", 0.0))
    sales_cpu = float(payload.get("sales_cpu_l", 2480.0))
    sales_pulser = float(payload.get("sales_pulser_l", 2478.5))

    expected_closing = round(opening_stock + deliveries - sales_cpu, 2)
    actual_atg = round(tank.current_volume_l, 2)
    variance = round(actual_atg - expected_closing, 2)
    variance_pct = round((abs(variance) / expected_closing * 100), 2) if expected_closing > 0 else 0.0

    # Tolerance threshold ±0.5%
    status_label = "NORMAL"
    if variance_pct > 1.5 or abs(variance) > 200.0:
        status_label = "CRITICAL_INVESTIGATION"
        # Trigger tank variance alert
        db.add(SystemAlert(
            station_id=tank.station_id,
            alert_type="TANK_INVENTORY_VARIANCE",
            severity="CRITICAL",
            title=f"Significant Tank Variance on {tank.code}",
            description=f"Tank reconciliation variance of {variance:.2f} L ({variance_pct}%). Expected: {expected_closing} L, Actual ATG: {actual_atg} L.",
            entity_type="tank",
            entity_id=tank.id,
        ))
    elif variance_pct > 0.5:
        status_label = "WARNING"

    rec = TankReconciliation(
        tank_id=tank.id,
        station_id=tank.station_id,
        shift_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        opening_stock_l=opening_stock,
        deliveries_l=deliveries,
        sales_cpu_l=sales_cpu,
        sales_pulser_l=sales_pulser,
        expected_closing_stock_l=expected_closing,
        actual_atg_closing_stock_l=actual_atg,
        variance_l=variance,
        variance_percentage=variance_pct,
        status=status_label,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "variance_l": rec.variance_l, "status": rec.status}
