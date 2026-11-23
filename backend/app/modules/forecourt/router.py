import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.deps import allowed_station_ids, get_current_user, require_permission, write_audit
from app.db.base import get_db
from app.models.auth import User
from app.models.core import Dispenser, FCCDevice, Nozzle, Station, Tank

router = APIRouter(prefix="/api/v1", tags=["forecourt"])


@router.get("/dispensers")
def list_dispensers(station_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Dispenser)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        stmt = stmt.where(Dispenser.station_id.in_(allowed))
    if station_id:
        stmt = stmt.where(Dispenser.station_id == station_id)
    dispensers = db.scalars(stmt).all()
    res = []
    for d in dispensers:
        res.append({
            "id": d.id,
            "station_id": d.station_id,
            "station_name": d.station.name if d.station else "",
            "code": d.code,
            "manufacturer": d.manufacturer,
            "model": d.model,
            "protocol": d.protocol,
            "interface": d.interface,
            "serial": d.serial,
            "status": d.status,
            "totalizer_l": d.totalizer_l,
            "nozzle_count": len(d.nozzles),
            "nozzles": [
                {
                    "id": n.id,
                    "number": n.number,
                    "price": n.price,
                    "status": n.status,
                    "tank_id": n.tank_id,
                    "product_code": n.product.code if n.product else "PMS",
                    "fcc_device_id": n.fcc.id if n.fcc else None,
                    "fcc_uid": n.fcc.device_uid if n.fcc else None,
                    "fcc_online": n.fcc.is_online if n.fcc else False,
                    "pos_terminal_id": n.pos.terminal_id if n.pos else None,
                }
                for n in d.nozzles
            ]
        })
    return res


@router.post("/dispensers", status_code=status.HTTP_201_CREATED)
def create_dispenser(payload: dict[str, Any], db: Session = Depends(get_db), user: User = Depends(require_permission("dispensers", "create"))):
    station_id = payload.get("station_id")
    allowed = allowed_station_ids(user)
    if allowed is not None and station_id not in allowed:
        raise HTTPException(status_code=403, detail="Station out of scope")
    dispenser = Dispenser(
        station_id=station_id,
        code=payload["code"],
        manufacturer=payload.get("manufacturer", "Wayne"),
        model=payload.get("model", "iGEM"),
        protocol=payload.get("protocol", "Wayne_Dart"),
        interface=payload.get("interface", "RS485_CurrentLoop"),
        serial=payload.get("serial", f"SN-{uuid.uuid4().hex[:8].upper()}"),
        status=payload.get("status", "ACTIVE"),
    )
    db.add(dispenser)
    db.commit()
    db.refresh(dispenser)
    return {"id": dispenser.id, "code": dispenser.code}


@router.get("/nozzles")
def list_nozzles(station_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Nozzle)
    nozzles = db.scalars(stmt).all()
    allowed = allowed_station_ids(user)
    res = []
    for n in nozzles:
        if n.dispenser and allowed is not None and n.dispenser.station_id not in allowed:
            continue
        if station_id and n.dispenser and n.dispenser.station_id != station_id:
            continue
        res.append({
            "id": n.id,
            "dispenser_id": n.dispenser_id,
            "dispenser_code": n.dispenser.code if n.dispenser else "",
            "station_id": n.dispenser.station_id if n.dispenser else "",
            "station_name": n.dispenser.station.name if n.dispenser and n.dispenser.station else "",
            "number": n.number,
            "price": n.price,
            "status": n.status,
            "product_code": n.product.code if n.product else "PMS",
            "tank_id": n.tank_id,
            "fcc": {
                "id": n.fcc.id if n.fcc else None,
                "uid": n.fcc.device_uid if n.fcc else None,
                "connection": n.fcc.connection_mode if n.fcc else "WIFI",
                "signal_dbm": n.fcc.signal_strength_dbm if n.fcc else -70,
                "online": n.fcc.is_online if n.fcc else False,
                "cal_factor": n.fcc.calibration_factor if n.fcc else 100.0,
            } if n.fcc else None,
            "pos": {
                "terminal_id": n.pos.terminal_id,
                "provider": n.pos.provider,
                "active": n.pos.is_active,
            } if n.pos else None,
        })
    return res


@router.get("/fcc-devices")
def list_fcc_devices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    fccs = db.scalars(select(FCCDevice)).all()
    allowed = allowed_station_ids(user)
    res = []
    for f in fccs:
        st_id = f.nozzle.dispenser.station_id if f.nozzle and f.nozzle.dispenser else None
        if allowed is not None and st_id not in allowed:
            continue
        res.append({
            "id": f.id,
            "device_uid": f.device_uid,
            "nozzle_id": f.nozzle_id,
            "nozzle_number": f.nozzle.number if f.nozzle else 1,
            "dispenser_code": f.nozzle.dispenser.code if f.nozzle and f.nozzle.dispenser else "",
            "station_name": f.nozzle.dispenser.station.name if f.nozzle and f.nozzle.dispenser and f.nozzle.dispenser.station else "",
            "firmware_version": f.firmware_version,
            "connection_mode": f.connection_mode,
            "signal_strength_dbm": f.signal_strength_dbm,
            "calibration_factor": f.calibration_factor,
            "is_online": f.is_online,
            "last_heartbeat": f.last_heartbeat.isoformat() if f.last_heartbeat else None,
        })
    return res


@router.post("/fcc-devices/{fcc_id}/toggle-online")
def toggle_fcc_online(fcc_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("fcc_devices", "manage"))):
    fcc = db.scalar(select(FCCDevice).where(FCCDevice.id == fcc_id))
    if not fcc:
        raise HTTPException(status_code=404, detail="FCC Device not found")
    fcc.is_online = not fcc.is_online
    db.commit()
    return {"id": fcc.id, "is_online": fcc.is_online}


@router.post("/nozzles/{nozzle_id}/assign-tank")
def assign_tank_to_nozzle(nozzle_id: str, payload: dict[str, Any], db: Session = Depends(get_db), user: User = Depends(require_permission("tank_pump_assignment", "manage"))):
    nozzle = db.scalar(select(Nozzle).where(Nozzle.id == nozzle_id))
    if not nozzle:
        raise HTTPException(status_code=404, detail="Nozzle not found")
    tank_id = payload.get("tank_id")
    if tank_id:
        tank = db.scalar(select(Tank).where(Tank.id == tank_id))
        if not tank:
            raise HTTPException(status_code=404, detail="Tank not found")
        # Check product match if applicable
        if nozzle.product_id and tank.product_id and nozzle.product_id != tank.product_id:
            raise HTTPException(status_code=400, detail="Incompatible fuel product: Nozzle and Tank products do not match")
    nozzle.tank_id = tank_id
    db.commit()
    return {"nozzle_id": nozzle.id, "tank_id": nozzle.tank_id}
