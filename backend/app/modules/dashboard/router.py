from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import allowed_station_ids, require_permission
from app.db.base import get_db
from app.models.auth import User
from app.models.core import Dispenser, Nozzle, Station, Tank

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("dashboard", "view")),
):
    station_scope = allowed_station_ids(_)
    station_query = select(func.count()).select_from(Station)
    dispenser_query = select(func.count()).select_from(Dispenser)
    nozzle_query = select(func.count()).select_from(Nozzle).join(Dispenser)
    tank_query = select(func.count()).select_from(Tank)

    if station_scope is not None:
        if not station_scope:
            return {
                "stations": 0, "active_stations": 0, "dispensers": 0,
                "nozzles": 0, "tanks": 0, "users": 0,
            }
        station_query = station_query.where(Station.id.in_(station_scope))
        dispenser_query = dispenser_query.where(Dispenser.station_id.in_(station_scope))
        nozzle_query = nozzle_query.where(Dispenser.station_id.in_(station_scope))
        tank_query = tank_query.where(Tank.station_id.in_(station_scope))

    return {
        "stations": db.scalar(station_query) or 0,
        "active_stations": db.scalar(
            select(func.count()).select_from(Station).where(Station.status == "ACTIVE")
            if station_scope is None else
            select(func.count()).select_from(Station).where(Station.status == "ACTIVE", Station.id.in_(station_scope))
        ) or 0,
        "dispensers": db.scalar(dispenser_query) or 0,
        "nozzles": db.scalar(nozzle_query) or 0,
        "tanks": db.scalar(tank_query) or 0,
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
    }
