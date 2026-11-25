"""One-button setup for people who do not want to learn the system.

Input: a station name and a few numbers. Codes, IDs, nozzle records, tanks and
controller assignments are all generated. Nothing can be mis-assigned.
"""

import hashlib
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.validation import utcnow
from app.db.base import get_db
from app.models.auth import User
from app.models.core import (
    Customer, Dispenser, FCCDevice, FuelProduct, Nozzle, RFIDCard, Station, Tank,
    TankController, Wallet,
)

router = APIRouter(prefix="/api/v1/simple", tags=["simple-setup"])


def _code(db: Session, model, prefix: str, column) -> str:
    while True:
        value = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
        if db.scalar(select(model).where(column == value)) is None:
            return value


@router.get("/status")
def status(db: Session = Depends(get_db), _: User = Depends(require_permission("dashboard", "view"))):
    def count(model):
        return db.scalar(select(func.count()).select_from(model)) or 0
    return {
        "stations": count(Station), "pumps": count(Dispenser),
        "nozzles": count(Nozzle), "tanks": count(Tank),
        "controllers": count(FCCDevice), "cards": count(RFIDCard),
    }


@router.get("/connected")
def connected_devices(db: Session = Depends(get_db), _: User = Depends(require_permission("dashboard", "view"))):
    """Compact list for the live device ticker (UID + location + link state)."""
    result = []
    for fcc in db.scalars(select(FCCDevice)).all():
        station = db.scalar(select(Station).where(Station.id == fcc.station_id))
        result.append({
            "kind": "FCC", "uid": fcc.device_uid,
            "station": station.name if station else "",
            "state": station.state.name if station and station.state else "",
            "lga": station.lga.name if station and station.lga else "",
            "online": bool(fcc.is_online),
            "last_seen": fcc.last_heartbeat.isoformat() if fcc.last_heartbeat else None,
        })
    for tank in db.scalars(select(Tank)).all():
        station = db.scalar(select(Station).where(Station.id == tank.station_id))
        controller = db.scalar(select(TankController).where(TankController.tank_id == tank.id))
        result.append({
            "kind": "TANK", "uid": controller.device_uid if controller else tank.code,
            "station": station.name if station else "",
            "state": station.state.name if station and station.state else "",
            "lga": station.lga.name if station and station.lga else "",
            "online": bool(controller.is_online) if controller else False,
            "last_seen": controller.last_heartbeat.isoformat() if controller and controller.last_heartbeat else None,
        })
    return result


@router.post("/setup")
def setup(payload: dict[str, Any], request: Request, db: Session = Depends(get_db),
          _: User = Depends(require_permission("stations", "create"))):
    name = str(payload.get("station_name") or "").strip()
    if not name:
        return {"ok": False, "message": "Please type a station name."}

    station = db.scalar(select(Station).where(func.lower(Station.name) == name.lower()))
    created_station = station is None
    if station is None:
        station = Station(
            id=str(uuid.uuid4()), code=_code(db, Station, "ST", Station.code),
            name=name, country="Nigeria", status="ACTIVE", registered_at=utcnow(),
        )
        db.add(station)
        db.flush()

    pump_count = max(1, min(10, int(payload.get("pump_count") or 1)))
    nozzle_count = 2 if str(payload.get("nozzles_per_pump") or "2") == "2" else 1
    price = float(payload.get("price_per_litre") or 1000)
    capacity = float(payload.get("tank_capacity_l") or 30000)
    product = db.scalar(select(FuelProduct))

    pumps = []
    nozzles = []
    for _ in range(pump_count):
        dispenser = Dispenser(
            id=str(uuid.uuid4()), station_id=station.id,
            code=_code(db, Dispenser, "PMP", Dispenser.code),
            name=f"Pump {len(pumps) + 1}", serial=f"DSP-{uuid.uuid4().hex[:8].upper()}",
            manufacturer="Wayne", model="Prototype",
            nozzle_config="DOUBLE" if nozzle_count == 2 else "SINGLE",
            nozzle_count=nozzle_count, status="ACTIVE", installation_date=utcnow(),
        )
        db.add(dispenser)
        db.flush()
        nozzle_records = []
        for i in range(nozzle_count):
            nozzle = Nozzle(
                id=str(uuid.uuid4()), dispenser_id=dispenser.id, number=i + 1,
                name=f"Nozzle {i + 1}", price=price, status="ACTIVE",
            )
            db.add(nozzle)
            db.flush()
            nozzles.append(nozzle)
            nozzle_records.append(nozzle)
        pumps.append({"id": dispenser.id, "code": dispenser.code,
                      "nozzles": [n.id for n in nozzle_records]})

    tanks = []
    for _ in range(pump_count):
        tank = Tank(
            id=str(uuid.uuid4()), station_id=station.id,
            code=_code(db, Tank, "TK", Tank.code),
            name="Fuel tank", product_id=product.id if product else None,
            capacity_l=capacity, current_volume_l=0,
            status="ACTIVE", location_type="UNDERGROUND",
            installation_status="INSTALLED", installation_date=utcnow(),
        )
        db.add(tank)
        db.flush()
        tanks.append({"id": tank.id, "code": tank.code})

    raw_uids = payload.get("controller_uids") or ""
    if isinstance(raw_uids, str):
        uids = [u.strip().upper() for u in raw_uids.replace(",", "\n").splitlines() if u.strip()]
    else:
        uids = [str(u).strip().upper() for u in raw_uids if str(u).strip()]

    controllers = []
    for i, uid in enumerate(uids):
        existing = db.scalar(select(FCCDevice).where(FCCDevice.device_uid == uid))
        if existing:
            controllers.append({"uid": uid, "status": "already registered"})
            continue
        if i < len(nozzles):
            nozzle = nozzles[i]
        else:
            extra = Dispenser(
                id=str(uuid.uuid4()), station_id=station.id,
                code=_code(db, Dispenser, "PMP", Dispenser.code),
                name=f"Pump {len(pumps) + 1}", serial=f"DSP-{uuid.uuid4().hex[:8].upper()}",
                manufacturer="Wayne", nozzle_config="SINGLE", nozzle_count=1,
                status="ACTIVE", installation_date=utcnow(),
            )
            db.add(extra)
            db.flush()
            nozzle = Nozzle(id=str(uuid.uuid4()), dispenser_id=extra.id, number=1,
                            name="Nozzle 1", price=price, status="ACTIVE")
            db.add(nozzle)
            db.flush()
            pumps.append({"id": extra.id, "code": extra.code, "nozzles": [nozzle.id]})
        fcc = FCCDevice(
            id=str(uuid.uuid4()), device_uid=uid, name=f"FCC {uid}",
            station_id=station.id, dispenser_id=nozzle.dispenser_id, nozzle_id=nozzle.id,
            firmware_version="v1.0.0", connection_mode="WIFI",
            calibration_factor=1, status="ACTIVE", is_online=False,
        )
        db.add(fcc)
        controllers.append({"uid": uid, "status": "registered", "nozzle_id": nozzle.id})

    cards = []
    raw_card = payload.get("card_uid")
    if raw_card:
        uid = str(raw_card).strip().upper()
        card = db.scalar(select(RFIDCard).where(RFIDCard.card_uid == uid))
        if card is None:
            customer = Customer(
                id=str(uuid.uuid4()), full_name=f"Driver {uid[-6:]}",
                phone=f"RFID-{uid}", category="SPECIAL_CUSTOMER", is_active=True,
            )
            db.add(customer)
            db.flush()
            db.add(Wallet(id=str(uuid.uuid4()), customer_id=customer.id, balance=0))
            db.add(RFIDCard(
                id=str(uuid.uuid4()), card_uid=uid, customer_id=customer.id,
                auth_key_hash=hashlib.sha256(uid.encode()).hexdigest(),
                is_blocked=False, daily_spend_limit=100000,
            ))
            cards.append({"uid": uid, "status": "registered"})
        else:
            cards.append({"uid": uid, "status": "already registered"})

    db.commit()
    return {
        "ok": True,
        "message": "Setup complete. Everything is registered and ready.",
        "station": {"id": station.id, "name": station.name, "code": station.code,
                    "created": created_station},
        "pumps": pumps, "tanks": tanks, "controllers": controllers, "cards": cards,
        "summary": f"{len(pumps)} pump(s), {len(nozzles)} nozzle(s), {len(tanks)} tank(s), "
                   f"{len(controllers)} controller(s), {len(cards)} card(s).",
    }
