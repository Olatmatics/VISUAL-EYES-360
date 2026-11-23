import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.deps import allowed_station_ids, get_current_user, require_permission
from app.db.base import get_db
from app.models.auth import User
from app.models.core import FuelProduct, SystemAlert, Tank, TankController, TankReading

router = APIRouter(prefix="/api/v1", tags=["tanks"])


@router.get("/tanks")
def list_tanks(station_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Tank)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        stmt = stmt.where(Tank.station_id.in_(allowed))
    if station_id:
        stmt = stmt.where(Tank.station_id == station_id)
    tanks = db.scalars(stmt).all()
    res = []
    for t in tanks:
        ullage = max(0.0, t.capacity_l - t.current_volume_l)
        percent = round((t.current_volume_l / t.capacity_l * 100), 1) if t.capacity_l > 0 else 0
        res.append({
            "id": t.id,
            "station_id": t.station_id,
            "station_name": t.station.name if t.station else "",
            "code": t.code,
            "product_code": t.product.code if t.product else "PMS",
            "product_name": t.product.name if t.product else "Premium Motor Spirit",
            "capacity_l": t.capacity_l,
            "current_volume_l": t.current_volume_l,
            "current_level_mm": t.current_level_mm,
            "current_water_mm": t.current_water_mm,
            "current_temperature_c": t.current_temperature_c,
            "ullage_l": ullage,
            "fill_percentage": percent,
            "hatch_open": t.hatch_open,
            "status": t.status,
            "controller": {
                "id": t.controller.id,
                "device_uid": t.controller.device_uid,
                "connection_mode": t.controller.connection_mode,
                "signal_strength_dbm": t.controller.signal_strength_dbm,
                "modbus_address": t.controller.modbus_address,
                "is_online": t.controller.is_online,
            } if t.controller else None,
        })
    return res


@router.post("/tanks", status_code=status.HTTP_201_CREATED)
def create_tank(payload: dict[str, Any], db: Session = Depends(get_db), user: User = Depends(require_permission("tanks", "create"))):
    station_id = payload.get("station_id")
    allowed = allowed_station_ids(user)
    if allowed is not None and station_id not in allowed:
        raise HTTPException(status_code=403, detail="Station out of scope")
    prod = db.scalar(select(FuelProduct).where(FuelProduct.code == payload.get("product_code", "PMS")))
    tank = Tank(
        station_id=station_id,
        code=payload["code"],
        product_id=prod.id if prod else None,
        capacity_l=float(payload.get("capacity_l", 50000.0)),
        current_volume_l=float(payload.get("initial_volume_l", 25000.0)),
        status=payload.get("status", "ACTIVE"),
    )
    db.add(tank)
    db.flush()

    # Create dedicated Tank Controller for this tank
    controller = TankController(
        device_uid=f"TC-ESP32-{uuid.uuid4().hex[:6].upper()}",
        tank_id=tank.id,
        connection_mode=payload.get("connection_mode", "WIFI"),
        modbus_address=int(payload.get("modbus_address", 1)),
    )
    db.add(controller)
    db.commit()
    db.refresh(tank)
    return {"id": tank.id, "code": tank.code}


@router.post("/tanks/{tank_id}/toggle-hatch")
def toggle_tank_hatch(tank_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("tanks", "manage"))):
    tank = db.scalar(select(Tank).where(Tank.id == tank_id))
    if not tank:
        raise HTTPException(status_code=404, detail="Tank not found")
    tank.hatch_open = not tank.hatch_open
    if tank.hatch_open:
        # Trigger Critical Security Alert
        alert = SystemAlert(
            station_id=tank.station_id,
            alert_type="TANK_HATCH_OPEN",
            severity="CRITICAL",
            title=f"Security Alert: Tank Hatch Opened ({tank.code})",
            description=f"Unauthorized hatch access detected by ATEX limit sensor on {tank.code} at {tank.station.name if tank.station else 'Station'}. Immediate physical inspection required.",
            entity_type="tank",
            entity_id=tank.id,
        )
        db.add(alert)
    db.commit()
    return {"tank_id": tank.id, "hatch_open": tank.hatch_open}


@router.post("/tanks/{tank_id}/update-atg")
def update_atg_reading(tank_id: str, payload: dict[str, Any], db: Session = Depends(get_db), user: User = Depends(require_permission("tanks", "manage"))):
    tank = db.scalar(select(Tank).where(Tank.id == tank_id))
    if not tank:
        raise HTTPException(status_code=404, detail="Tank not found")
    if "current_volume_l" in payload:
        tank.current_volume_l = float(payload["current_volume_l"])
    if "current_level_mm" in payload:
        tank.current_level_mm = float(payload["current_level_mm"])
    if "current_water_mm" in payload:
        tank.current_water_mm = float(payload["current_water_mm"])
    if "current_temperature_c" in payload:
        tank.current_temperature_c = float(payload["current_temperature_c"])

    # Water warning if water level > 25mm
    if tank.current_water_mm > 25.0:
        db.add(SystemAlert(
            station_id=tank.station_id,
            alert_type="WATER_DETECTED",
            severity="WARNING",
            title=f"Water Level Warning ({tank.code})",
            description=f"Interface water measured at {tank.current_water_mm} mm. Above standard 25mm threshold.",
            entity_type="tank",
            entity_id=tank.id,
        ))

    db.commit()
    return {"tank_id": tank.id, "volume": tank.current_volume_l}
