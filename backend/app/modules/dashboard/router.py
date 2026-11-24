from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import allowed_station_ids, require_permission
from app.db.base import get_db
from app.models.auth import User
from app.models.core import (
    Dispenser, FCCDevice, FuelTransaction, LGA, Nozzle, State, Station,
    SystemAlert, Tank,
)

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


def _station_filter(station_scope, column):
    return column.in_(station_scope) if station_scope is not None else None


@router.get("/dashboard/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("dashboard", "view")),
):
    scope = allowed_station_ids(_)
    if scope is not None and not scope:
        return {"stations": 0, "active_stations": 0, "dispensers": 0, "nozzles": 0,
                "tanks": 0, "fcc_total": 0, "fcc_online": 0, "fcc_offline": 0, "users": 0}

    def count(model, station_col=None, **filters):
        stmt = select(func.count()).select_from(model)
        if scope is not None and station_col is not None:
            stmt = stmt.where(station_col.in_(scope))
        for key, value in filters.items():
            stmt = stmt.where(getattr(model, key) == value)
        return db.scalar(stmt) or 0

    return {
        "stations": count(Station, Station.id),
        "active_stations": count(Station, Station.id, status="ACTIVE"),
        "dispensers": count(Dispenser, Dispenser.station_id),
        "nozzles": db.scalar(
            select(func.count()).select_from(Nozzle).join(Dispenser).where(
                Dispenser.station_id.in_(scope)
            ) if scope is not None else select(func.count()).select_from(Nozzle)
        ) or 0,
        "tanks": count(Tank, Tank.station_id),
        "fcc_total": count(FCCDevice, FCCDevice.station_id),
        "fcc_online": count(FCCDevice, FCCDevice.station_id, is_online=True),
        "fcc_offline": count(FCCDevice, FCCDevice.station_id, is_online=False),
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
    }


@router.get("/dashboard/analytics")
def dashboard_analytics(
    state_id: str | None = None,
    lga_id: str | None = None,
    station_id: str | None = None,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("dashboard", "view")),
):
    """Real operational aggregates with geographic, station and date filters."""
    scope = allowed_station_ids(user)
    end = datetime.now(timezone.utc).replace(tzinfo=None)
    start = end - timedelta(days=days)

    station_stmt = select(Station)
    if state_id:
        station_stmt = station_stmt.where(Station.state_id == state_id)
    if lga_id:
        station_stmt = station_stmt.where(Station.lga_id == lga_id)
    if station_id:
        station_stmt = station_stmt.where(Station.id == station_id)
    if scope is not None:
        station_stmt = station_stmt.where(Station.id.in_(scope))
    stations = db.scalars(station_stmt).all()
    station_ids = [s.id for s in stations]

    tx_stmt = select(FuelTransaction).where(
        FuelTransaction.started_at >= start, FuelTransaction.started_at <= end
    )
    alert_stmt = select(SystemAlert).where(SystemAlert.is_resolved.is_(False))
    fcc_stmt = select(FCCDevice)
    tank_stmt = select(Tank)
    if station_ids:
        tx_stmt = tx_stmt.where(FuelTransaction.station_id.in_(station_ids))
        alert_stmt = alert_stmt.where(SystemAlert.station_id.in_(station_ids))
        fcc_stmt = fcc_stmt.where(FCCDevice.station_id.in_(station_ids))
        tank_stmt = tank_stmt.where(Tank.station_id.in_(station_ids))

    txs = db.scalars(tx_stmt).all()
    alerts = db.scalars(alert_stmt).all()
    fccs = db.scalars(fcc_stmt).all()
    tanks = db.scalars(tank_stmt).all()

    litre_totals = {
        "cpu_l": round(sum(t.dispenser_cpu_volume for t in txs), 2),
        "pulser_l": round(sum(t.independent_pulser_volume for t in txs), 2),
    }
    revenue = round(sum(t.total_amount_billed for t in txs), 2)

    by_state = {}
    for station in stations:
        key = station.state.name if station.state else "Unknown"
        bucket = by_state.setdefault(key, {"stations": 0, "litres": 0.0, "revenue": 0.0})
        bucket["stations"] += 1
    for tx in txs:
        station = next((s for s in stations if s.id == tx.station_id), None)
        if station:
            key = station.state.name if station.state else "Unknown"
            by_state.setdefault(key, {"stations": 0, "litres": 0.0, "revenue": 0.0})
            by_state[key]["litres"] += tx.dispenser_cpu_volume
            by_state[key]["revenue"] += tx.total_amount_billed
    for bucket in by_state.values():
        bucket["litres"] = round(bucket["litres"], 2)
        bucket["revenue"] = round(bucket["revenue"], 2)

    daily = {}
    for tx in txs:
        key = tx.started_at.strftime("%Y-%m-%d") if tx.started_at else "unknown"
        bucket = daily.setdefault(key, {"litres": 0.0, "revenue": 0.0, "transactions": 0})
        bucket["litres"] += tx.dispenser_cpu_volume
        bucket["revenue"] += tx.total_amount_billed
        bucket["transactions"] += 1
    for bucket in daily.values():
        bucket["litres"] = round(bucket["litres"], 2)
        bucket["revenue"] = round(bucket["revenue"], 2)

    return {
        "period_days": days,
        "stations": len(stations),
        "litres_sold": litre_totals["cpu_l"],
        "pulser_verified_l": litre_totals["pulser_l"],
        "revenue_ngn": revenue,
        "transactions": len(txs),
        "active_critical_alerts": sum(1 for a in alerts if a.severity == "CRITICAL"),
        "unresolved_discrepancies": sum(1 for t in txs if t.discrepancy_alert),
        "fcc_online": sum(1 for f in fccs if f.is_online),
        "fcc_offline": sum(1 for f in fccs if not f.is_online),
        "fuel_inventory_l": round(sum(t.current_volume_l for t in tanks), 2),
        "by_state": by_state,
        "daily": dict(sorted(daily.items())),
    }
