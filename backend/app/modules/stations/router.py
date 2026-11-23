from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import allowed_station_ids, get_current_user, require_permission, write_audit
from app.db.base import get_db
from app.models.core import Dispenser, Station, Tank
from app.schemas.station import StationCreate, StationOut, StationUpdate

router = APIRouter(prefix="/api/v1", tags=["stations"])


def _scoped_station(db: Session, station_id: str, user) -> Station:
    station = db.scalar(select(Station).where(Station.id == station_id))
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
    allowed = allowed_station_ids(user)
    if allowed is not None and station.id not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Station access denied")
    return station


@router.get("/stations", response_model=list[StationOut])
def list_stations(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not user.has_permission("stations", "view"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    query = select(Station)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        query = query.where(Station.id.in_(allowed)) if allowed else query.where(False)
    return list(db.scalars(query.order_by(Station.name)).all())


@router.post("/stations", response_model=StationOut, status_code=status.HTTP_201_CREATED)
def create_station(
    payload: StationCreate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("stations", "create")),
):
    if db.scalar(select(Station).where(func.upper(Station.code) == payload.code.upper())):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Station code already exists")
    station = Station(**payload.model_dump())
    db.add(station)
    db.flush()
    write_audit(db, user, "CREATE_STATION", "Station", station.id, after=payload.model_dump(), request=request)
    db.commit()
    return station


@router.get("/stations/{station_id}", response_model=StationOut)
def get_station(station_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _scoped_station(db, station_id, user)


@router.patch("/stations/{station_id}", response_model=StationOut)
def update_station(
    station_id: str,
    payload: StationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("stations", "edit")),
):
    station = _scoped_station(db, station_id, user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(station, key, value)
    db.flush()
    write_audit(db, user, "UPDATE_STATION", "Station", station.id, after=payload.model_dump(exclude_unset=True), request=request)
    db.commit()
    return station


@router.get("/stations/{station_id}/summary")
def station_summary(station_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    station = _scoped_station(db, station_id, user)
    dispensers = db.scalar(select(func.count()).select_from(Dispenser).where(Dispenser.station_id == station.id)) or 0
    tanks = db.scalar(select(func.count()).select_from(Tank).where(Tank.station_id == station.id)) or 0
    return {"station_id": station.id, "dispensers": dispensers, "tanks": tanks}
