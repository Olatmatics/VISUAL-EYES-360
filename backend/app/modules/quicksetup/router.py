"""Minimal registration endpoints: only vital fields, everything else generated.

These wrap the same models as the advanced forms, so records are real and usable
by every other module.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_permission, write_audit
from app.core.validation import utcnow
from app.db.base import get_db
from app.models.auth import User
from app.models.core import (
    Dispenser, FCCDevice, FuelProduct, Nozzle, Station, Tank,
)

router = APIRouter(prefix="/api/v1/quick", tags=["quick-setup"])


def _unique_code(db: Session, model, prefix: str, column) -> str:
    while True:
        code = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
        if db.scalar(select(model).where(column == code)) is None:
            return code


def _station(db: Session, station_id: str | None) -> Station:
    station = db.scalar(select(Station).where(Station.id == station_id)) if station_id else None
    if station is None:
        station = db.scalar(select(Station).order_by(Station.registered_at))
    if station is None:
        raise HTTPException(400, "Register a station first")
    return station


@router.get("/options")
def options(db: Session = Depends(get_db), _: User = Depends(require_permission("stations", "view"))):
    stations = db.scalars(select(Station).order_by(Station.registered_at)).all()
    free_nozzles = db.scalars(
        select(Nozzle).where(~select(FCCDevice.id).where(FCCDevice.nozzle_id == Nozzle.id).exists())
    ).all()
    tanks = db.scalars(select(Tank)).all()
    return {
        "stations": [{"id": s.id, "name": s.name, "code": s.code} for s in stations],
        "free_nozzles": [{
            "id": n.id, "number": n.number, "dispenser_id": n.dispenser_id,
            "dispenser_code": n.dispenser.code if n.dispenser else "",
            "station_id": n.dispenser.station_id if n.dispenser else None,
            "price": n.price,
        } for n in free_nozzles],
        "tanks": [{"id": t.id, "code": t.code, "station_id": t.station_id} for t in tanks],
    }


@router.post("/station")
def quick_station(
    payload: dict[str, Any], request: Request, db: Session = Depends(get_db),
    user: User = Depends(require_permission("stations", "create")),
):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Station name is required")
    code = str(payload.get("code") or "").strip() or _unique_code(db, Station, "ST", Station.code)
    if db.scalar(select(Station).where(Station.code == code)):
        raise HTTPException(409, "Station code already exists")
    station = Station(
        id=str(uuid.uuid4()), code=code, name=name, country="Nigeria",
        state_id=payload.get("state_id"), lga_id=payload.get("lga_id"),
        city=payload.get("city"), address=payload.get("address"),
        gps_lat=payload.get("gps_lat"), gps_lng=payload.get("gps_lng"),
        manager_name=payload.get("manager_name"), manager_phone=payload.get("manager_phone"),
        supervisor_name=payload.get("supervisor_name"), supervisor_phone=payload.get("supervisor_phone"),
        status="ACTIVE", registered_at=utcnow(),
    )
    db.add(station)
    db.flush()
    write_audit(db, user, "QUICK_REGISTER_STATION", "Station", station.id,
                after={"code": code, "name": name}, request=request)
    db.commit()
    return {"id": station.id, "code": station.code, "name": station.name}


@router.post("/pump")
def quick_pump(
    payload: dict[str, Any], request: Request, db: Session = Depends(get_db),
    user: User = Depends(require_permission("dispensers", "create")),
):
    station = _station(db, payload.get("station_id"))
    config = str(payload.get("nozzle_config") or "DOUBLE").upper()
    count = 2 if config == "DOUBLE" else 1
    code = str(payload.get("code") or "").strip() or _unique_code(db, Dispenser, "PMP", Dispenser.code)
    if db.scalar(select(Dispenser).where(Dispenser.station_id == station.id, Dispenser.code == code)):
        raise HTTPException(409, "Dispenser code already exists at this station")
    price = float(payload.get("price") or 1000)
    dispenser = Dispenser(
        id=str(uuid.uuid4()), station_id=station.id, code=code, name=payload.get("name") or code,
        serial=f"DSP-{uuid.uuid4().hex[:8].upper()}", manufacturer="Wayne",
        model=payload.get("model") or "Prototype", nozzle_config=config, nozzle_count=count,
        protocol="WAYNE_DART", interface="RS485", status="ACTIVE",
        communication_status="UNKNOWN", installation_date=utcnow(),
    )
    db.add(dispenser)
    db.flush()
    for i in range(count):
        db.add(Nozzle(
            id=str(uuid.uuid4()), dispenser_id=dispenser.id, number=i + 1,
            name=f"Nozzle {i + 1}", price=price, status="ACTIVE",
        ))
    db.flush()
    write_audit(db, user, "QUICK_REGISTER_PUMP", "Dispenser", dispenser.id,
                after={"code": code, "nozzles": count}, request=request)
    db.commit()
    nozzles = db.scalars(select(Nozzle).where(Nozzle.dispenser_id == dispenser.id)).all()
    return {"id": dispenser.id, "code": code, "station_id": station.id,
            "nozzle_config": config, "nozzles": [{"id": n.id, "number": n.number, "price": n.price} for n in nozzles]}


@router.post("/tank")
def quick_tank(
    payload: dict[str, Any], request: Request, db: Session = Depends(get_db),
    user: User = Depends(require_permission("tanks", "create")),
):
    station = _station(db, payload.get("station_id"))
    code = str(payload.get("code") or "").strip() or _unique_code(db, Tank, "TK", Tank.code)
    if db.scalar(select(Tank).where(Tank.code == code)):
        raise HTTPException(409, "Tank code already exists")
    product = db.scalar(select(FuelProduct))
    tank = Tank(
        id=str(uuid.uuid4()), station_id=station.id, code=code, name=code,
        product_id=product.id if product else None,
        capacity_l=float(payload.get("capacity_l") or 30000),
        current_volume_l=float(payload.get("current_volume_l") or 0),
        status="ACTIVE", installation_status="INSTALLED", location_type="UNDERGROUND",
        installation_date=utcnow(),
    )
    db.add(tank)
    db.flush()
    write_audit(db, user, "QUICK_REGISTER_TANK", "Tank", tank.id,
                after={"code": code, "capacity_l": tank.capacity_l}, request=request)
    db.commit()
    return {"id": tank.id, "code": tank.code, "station_id": station.id, "capacity_l": tank.capacity_l}


@router.post("/fcc")
def quick_fcc(
    payload: dict[str, Any], request: Request, db: Session = Depends(get_db),
    user: User = Depends(require_permission("fcc_devices", "create")),
):
    """Register an FCC with just a device UID. Creates a pump if none is free."""
    device_uid = str(payload.get("device_uid") or "").strip()
    if not device_uid:
        raise HTTPException(400, "Controller UID is required (the UID in your ESP32 sketch)")
    if db.scalar(select(FCCDevice).where(FCCDevice.device_uid == device_uid)):
        raise HTTPException(409, "Controller UID already registered")
    station = _station(db, payload.get("station_id"))

    nozzle = db.scalar(
        select(Nozzle).join(Dispenser).where(
            Dispenser.station_id == station.id,
            ~select(FCCDevice.id).where(FCCDevice.nozzle_id == Nozzle.id).exists(),
        ).order_by(Dispenser.code)
    )
    if nozzle is None:
        created = quick_pump({"station_id": station.id, "nozzle_config": "SINGLE"}, request, db, user)
        nozzle = db.scalar(select(Nozzle).where(Nozzle.id == created["nozzles"][0]["id"]))

    fcc = FCCDevice(
        id=str(uuid.uuid4()), device_uid=device_uid,
        name=payload.get("name") or f"FCC {nozzle.dispenser.code} N{nozzle.number}",
        station_id=station.id, dispenser_id=nozzle.dispenser_id, nozzle_id=nozzle.id,
        firmware_version=payload.get("firmware_version") or "v1.0.0",
        connection_mode=str(payload.get("connection_mode") or "WIFI").upper(),
        calibration_factor=float(payload.get("calibration_factor") or 1),
        status="ACTIVE", is_online=False,
    )
    db.add(fcc)
    db.flush()
    write_audit(db, user, "QUICK_REGISTER_FCC", "FCCDevice", fcc.id,
                after={"device_uid": device_uid, "nozzle_id": nozzle.id}, request=request)
    db.commit()
    return {"id": fcc.id, "device_uid": fcc.device_uid,
            "station_id": station.id, "dispenser_id": nozzle.dispenser_id,
            "nozzle_id": nozzle.id, "next": "Provision the device credential, then flash the UID into the sketch"}
