from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import (
    allowed_station_ids,
    get_current_user,
    require_permission,
    scoped_station_or_404,
    write_audit,
)
from app.core.validation import like, validate_geo
from app.db.base import get_db
from app.models.auth import User
from app.models.core import Dispenser, FCCDevice, Nozzle, Station, Tank
from app.schemas.station import StationCreate, StationOut, StationUpdate

router = APIRouter(prefix="/api/v1", tags=["stations"])

VALID_STATUS = {"ACTIVE", "INACTIVE", "SUSPENDED", "MAINTENANCE", "PENDING_APPROVAL"}


def _out(station: Station) -> dict:
    return {
        "id": station.id,
        "code": station.code,
        "name": station.name,
        "company_name": station.company_name,
        "address": station.address,
        "country": station.country,
        "state_id": station.state_id,
        "lga_id": station.lga_id,
        "state_name": station.state.name if station.state else None,
        "lga_name": station.lga.name if station.lga else None,
        "city": station.city,
        "gps_lat": station.gps_lat,
        "gps_lng": station.gps_lng,
        "manager_name": station.manager_name,
        "manager_phone": station.manager_phone,
        "manager_email": station.manager_email,
        "supervisor_name": station.supervisor_name,
        "supervisor_phone": station.supervisor_phone,
        "supervisor_email": station.supervisor_email,
        "contact_person": station.contact_person,
        "phone": station.phone,
        "email": station.email,
        "notes": station.notes,
        "status": station.status,
        "registered_at": station.registered_at,
        "dispenser_count": len(station.dispensers),
        "tank_count": len(station.tanks),
    }


def _assert_can_create_in_geo(user: User, state_id: str | None, lga_id: str | None) -> None:
    if user.is_super_admin or user.all_stations:
        return
    if user.scope_lga_id:
        if lga_id != user.scope_lga_id:
            raise HTTPException(status_code=403, detail="Station creation is limited to your assigned LGA")
        return
    if user.scope_state_id:
        if state_id != user.scope_state_id:
            raise HTTPException(status_code=403, detail="Station creation is limited to your assigned state")
        return
    raise HTTPException(
        status_code=403,
        detail="Station creation requires a state or LGA geographic scope",
    )


@router.get("/stations", response_model=list[StationOut])
def list_stations(
    state_id: str | None = None,
    lga_id: str | None = None,
    station_status: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    limit: int = Query(default=500, le=2000),
    offset: int = 0,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not user.has_permission("stations", "view"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    query = select(Station)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        query = query.where(Station.id.in_(allowed)) if allowed else query.where(False)
    if state_id:
        query = query.where(Station.state_id == state_id)
    if lga_id:
        query = query.where(Station.lga_id == lga_id)
    if station_status:
        query = query.where(Station.status == station_status.upper())
    if search:
        pattern = like(search)
        query = query.where(
            Station.name.ilike(pattern)
            | Station.code.ilike(pattern)
            | Station.city.ilike(pattern)
            | Station.company_name.ilike(pattern)
        )
    rows = db.scalars(query.order_by(Station.name).offset(offset).limit(limit)).all()
    return [_out(station) for station in rows]


@router.post("/stations", response_model=StationOut, status_code=status.HTTP_201_CREATED)
def create_station(
    payload: StationCreate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("stations", "create")),
):
    code = payload.code.strip()
    if db.scalar(select(Station).where(func.upper(Station.code) == code.upper())):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Station code already exists")

    state, lga = validate_geo(db, payload.state_id, payload.lga_id)
    _assert_can_create_in_geo(user, state.id if state else None, lga.id if lga else None)

    if state is not None:
        duplicate = db.scalar(
            select(Station).where(
                func.lower(Station.name) == payload.name.strip().lower(),
                Station.state_id == state.id,
                Station.lga_id == (lga.id if lga else None),
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A station with this name already exists in the selected LGA",
            )

    station_status = (payload.status or "ACTIVE").upper()
    if station_status not in VALID_STATUS:
        raise HTTPException(status_code=400, detail="Invalid station status")

    data = payload.model_dump()
    data["code"] = code
    data["state_id"] = state.id if state else None
    data["lga_id"] = lga.id if lga else None
    data["status"] = station_status
    station = Station(**data)
    db.add(station)
    db.flush()
    write_audit(db, user, "CREATE_STATION", "Station", station.id, after=_out(station), request=request)
    db.commit()
    db.refresh(station)
    return _out(station)


@router.get("/stations/{station_id}", response_model=StationOut)
def get_station(station_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not user.has_permission("stations", "view"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    return _out(scoped_station_or_404(db, user, station_id))


@router.patch("/stations/{station_id}", response_model=StationOut)
def update_station(
    station_id: str,
    payload: StationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("stations", "edit")),
):
    station = scoped_station_or_404(db, user, station_id)
    before = _out(station)
    changes = payload.model_dump(exclude_unset=True)

    if "state_id" in changes or "lga_id" in changes:
        state, lga = validate_geo(
            db,
            changes.get("state_id", station.state_id),
            changes.get("lga_id", station.lga_id),
        )
        changes["state_id"] = state.id if state else None
        changes["lga_id"] = lga.id if lga else None

    if "status" in changes:
        changes["status"] = (changes["status"] or "").upper()
        if changes["status"] not in VALID_STATUS:
            raise HTTPException(status_code=400, detail="Invalid station status")

    if "name" in changes and changes["name"]:
        duplicate = db.scalar(
            select(Station).where(
                func.lower(Station.name) == changes["name"].strip().lower(),
                Station.id != station.id,
                Station.state_id == changes.get("state_id", station.state_id),
                Station.lga_id == changes.get("lga_id", station.lga_id),
            )
        )
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="Another station already uses this name in the area")

    for key, value in changes.items():
        setattr(station, key, value)
    db.flush()
    write_audit(db, user, "UPDATE_STATION", "Station", station.id, before=before, after=_out(station), request=request)
    db.commit()
    db.refresh(station)
    return _out(station)


@router.get("/stations/{station_id}/summary")
def station_summary(station_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    station = scoped_station_or_404(db, user, station_id)
    dispensers = db.scalar(select(func.count()).select_from(Dispenser).where(Dispenser.station_id == station.id)) or 0
    tanks = db.scalar(select(func.count()).select_from(Tank).where(Tank.station_id == station.id)) or 0
    nozzles = db.scalar(
        select(func.count()).select_from(Nozzle).join(Dispenser).where(Dispenser.station_id == station.id)
    ) or 0
    fcc_online = db.scalar(
        select(func.count())
        .select_from(FCCDevice)
        .join(Nozzle, FCCDevice.nozzle_id == Nozzle.id)
        .join(Dispenser, Nozzle.dispenser_id == Dispenser.id)
        .where(Dispenser.station_id == station.id, FCCDevice.is_online.is_(True))
    ) or 0
    return {
        "station_id": station.id,
        "state": station.state.name if station.state else None,
        "lga": station.lga.name if station.lga else None,
        "dispensers": dispensers,
        "nozzles": nozzles,
        "tanks": tanks,
        "fcc_online": fcc_online,
        "total_capacity_l": db.scalar(
            select(func.coalesce(func.sum(Tank.capacity_l), 0.0)).where(Tank.station_id == station.id)
        ) or 0.0,
        "current_stock_l": db.scalar(
            select(func.coalesce(func.sum(Tank.current_volume_l), 0.0)).where(Tank.station_id == station.id)
        ) or 0.0,
    }
