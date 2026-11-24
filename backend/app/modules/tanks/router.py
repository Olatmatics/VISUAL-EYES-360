import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import (
    allowed_station_ids,
    get_current_user,
    require_permission,
    write_audit,
)
from app.core.validation import like, parse_float, validate_station, utcnow
from app.db.base import get_db
from app.models.auth import User
from app.models.core import (
    FuelProduct,
    Tank,
    TankCalibration,
    TankController,
    TankReading,
    TankSensor,
)
from app.modules.alerts.service import create_alert
from app.modules.forecourt.router import _ensure_station_scope

router = APIRouter(prefix="/api/v1", tags=["tanks"])

LOCATION_TYPES = {"UNDERGROUND", "SURFACE"}
SENSOR_TYPES = {
    "TEMPERATURE_SENSOR",
    "TEMPERATURE_SWITCH",
    "TAMPER_SWITCH",
    "LID_LIMIT_SWITCH",
    "HIGH_LEVEL_SWITCH",
    "LOW_LEVEL_SWITCH",
    "WATER_DETECTION",
    "PROBE",
    "OTHER",
}


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date/time: {value}")


def _tank_out(tank: Tank) -> dict:
    ullage = max(0.0, tank.capacity_l - tank.current_volume_l)
    percent = round((tank.current_volume_l / tank.capacity_l * 100), 1) if tank.capacity_l > 0 else 0
    return {
        "id": tank.id,
        "station_id": tank.station_id,
        "station_name": tank.station.name if tank.station else "",
        "code": tank.code,
        "name": tank.name,
        "display_name": tank.display_name,
        "serial_number": tank.serial_number,
        "product_id": tank.product_id,
        "product_code": tank.product.code if tank.product else None,
        "product_name": tank.product.name if tank.product else None,
        "capacity_l": tank.capacity_l,
        "current_volume_l": tank.current_volume_l,
        "current_level_mm": tank.current_level_mm,
        "current_water_mm": tank.current_water_mm,
        "current_temperature_c": tank.current_temperature_c,
        "ullage_l": round(ullage, 2),
        "fill_percentage": percent,
        "hatch_open": tank.hatch_open,
        "location_type": tank.location_type,
        "position": tank.position,
        "dimensions": tank.dimensions,
        "installation_date": tank.installation_date.isoformat() if tank.installation_date else None,
        "installation_status": tank.installation_status,
        "probe_id": tank.probe_id,
        "probe_comm_type": tank.probe_comm_type,
        "monitoring_device": tank.monitoring_device,
        "sensor_flags": {
            "temperature_sensor": tank.has_temperature_sensor,
            "temperature_switch": tank.has_temperature_switch,
            "tamper_switch": tank.has_tamper_switch,
            "lid_limit_switch": tank.has_lid_limit_switch,
            "high_level_switch": tank.has_high_level_switch,
            "low_level_switch": tank.has_low_level_switch,
            "water_detection": tank.has_water_detection,
        },
        "status": tank.status,
        "calibration_count": len(tank.calibration_rows),
        "sensors": [
            {
                "id": sensor.id,
                "sensor_type": sensor.sensor_type,
                "label": sensor.label,
                "is_installed": sensor.is_installed,
                "is_enabled": sensor.is_enabled,
                "status": sensor.status,
                "last_reading_at": sensor.last_reading_at.isoformat() if sensor.last_reading_at else None,
                "notes": sensor.notes,
            }
            for sensor in tank.sensors
        ],
        "controller": {
            "id": tank.controller.id,
            "device_uid": tank.controller.device_uid,
            "connection_mode": tank.controller.connection_mode,
            "signal_strength_dbm": tank.controller.signal_strength_dbm,
            "modbus_address": tank.controller.modbus_address,
            "is_online": tank.controller.is_online,
            "firmware_version": tank.controller.firmware_version,
            "last_heartbeat": tank.controller.last_heartbeat.isoformat() if tank.controller.last_heartbeat else None,
        }
        if tank.controller
        else None,
    }


def _resolve_product(db: Session, payload: dict) -> FuelProduct | None:
    product_id = payload.get("product_id")
    code = payload.get("product_code")
    if product_id:
        product = db.scalar(select(FuelProduct).where(FuelProduct.id == product_id))
        if product is None:
            raise HTTPException(status_code=400, detail="Unknown fuel product")
        return product
    if code:
        product = db.scalar(select(FuelProduct).where(FuelProduct.code == str(code).upper()))
        if product is None:
            raise HTTPException(status_code=400, detail="Unknown fuel product code")
        return product
    return None


def _replace_calibration(db: Session, tank: Tank, rows: list[dict], version: str) -> int:
    if not rows:
        return 0
    parsed = []
    for row in rows:
        height = parse_float(row.get("height_mm"), "height_mm", minimum=0)
        volume = parse_float(row.get("volume_l"), "volume_l", minimum=0)
        parsed.append((height, volume, parse_float(row.get("water_mm", 0), "water_mm", minimum=0)))
    parsed.sort(key=lambda item: item[0])
    for previous, current in zip(parsed, parsed[1:]):
        if current[0] <= previous[0]:
            raise HTTPException(status_code=400, detail="Calibration heights must be strictly increasing")
    if parsed[-1][1] > tank.capacity_l * 1.05:
        raise HTTPException(status_code=400, detail="Calibration volume exceeds tank capacity")

    db.query(TankCalibration).filter(TankCalibration.tank_id == tank.id).delete()
    for height, volume, water in parsed:
        db.add(
            TankCalibration(
                tank_id=tank.id,
                version=version,
                height_mm=height,
                volume_l=volume,
                water_mm=water,
            )
        )
    return len(parsed)


def _replace_sensors(db: Session, tank: Tank, sensors: list[dict]) -> int:
    if sensors is None:
        return 0
    db.query(TankSensor).filter(TankSensor.tank_id == tank.id).delete()
    count = 0
    for item in sensors:
        sensor_type = str(item.get("sensor_type") or "OTHER").upper()
        if sensor_type not in SENSOR_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid sensor type: {sensor_type}")
        db.add(
            TankSensor(
                tank_id=tank.id,
                sensor_type=sensor_type,
                label=item.get("label"),
                is_installed=bool(item.get("is_installed", True)),
                is_enabled=bool(item.get("is_enabled", True)),
                status=str(item.get("status") or "OK").upper(),
                notes=item.get("notes"),
            )
        )
        count += 1
    return count


@router.get("/tanks")
def list_tanks(
    station_id: str | None = None,
    state_id: str | None = None,
    lga_id: str | None = None,
    product_code: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.has_permission("tanks", "view"):
        raise HTTPException(status_code=403, detail="Permission denied")
    query = select(Tank)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        query = query.where(Tank.station_id.in_(allowed)) if allowed else query.where(False)
    if station_id:
        query = query.where(Tank.station_id == station_id)
    if state_id or lga_id:
        from app.models.core import Station

        query = query.join(Station, Tank.station_id == Station.id)
        if state_id:
            query = query.where(Station.state_id == state_id)
        if lga_id:
            query = query.where(Station.lga_id == lga_id)
    if product_code:
        query = query.join(FuelProduct, Tank.product_id == FuelProduct.id).where(
            FuelProduct.code == product_code.upper()
        )
    if search:
        pattern = like(search)
        query = query.where(Tank.code.ilike(pattern) | Tank.name.ilike(pattern) | Tank.serial_number.ilike(pattern))
    return [_tank_out(t) for t in db.scalars(query.order_by(Tank.code)).all()]


@router.post("/tanks", status_code=status.HTTP_201_CREATED)
def create_tank(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tanks", "create")),
):
    station = _ensure_station_scope(db, user, payload.get("station_id"))
    code = str(payload.get("code") or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Tank code is required")
    if db.scalar(select(Tank).where(Tank.station_id == station.id, func.upper(Tank.code) == code.upper())):
        raise HTTPException(status_code=409, detail="Tank code already exists at this station")
    serial = (payload.get("serial_number") or "").strip() or None
    if serial and db.scalar(select(Tank).where(Tank.serial_number == serial)):
        raise HTTPException(status_code=409, detail="Tank serial number already registered")

    capacity = parse_float(payload.get("capacity_l", 0), "capacity_l", minimum=1)
    volume = parse_float(payload.get("initial_volume_l", 0), "initial_volume_l", minimum=0)
    if volume > capacity:
        raise HTTPException(status_code=400, detail="Initial volume cannot exceed tank capacity")
    location_type = str(payload.get("location_type") or "UNDERGROUND").upper()
    if location_type not in LOCATION_TYPES:
        raise HTTPException(status_code=400, detail="location_type must be UNDERGROUND or SURFACE")

    product = _resolve_product(db, payload)
    tank = Tank(
        station_id=station.id,
        code=code,
        name=payload.get("name"),
        serial_number=serial,
        product_id=product.id if product else None,
        capacity_l=capacity,
        current_volume_l=volume,
        current_level_mm=parse_float(payload.get("current_level_mm", 0), "current_level_mm", minimum=0),
        current_water_mm=parse_float(payload.get("current_water_mm", 0), "current_water_mm", minimum=0),
        current_temperature_c=parse_float(payload.get("current_temperature_c", 25), "current_temperature_c"),
        hatch_open=bool(payload.get("hatch_open", False)),
        location_type=location_type,
        position=payload.get("position"),
        dimensions=payload.get("dimensions"),
        installation_date=_parse_datetime(payload.get("installation_date")),
        installation_status=str(payload.get("installation_status") or "INSTALLED").upper(),
        probe_id=payload.get("probe_id"),
        probe_comm_type=payload.get("probe_comm_type"),
        monitoring_device=payload.get("monitoring_device"),
        has_temperature_sensor=bool(payload.get("has_temperature_sensor", True)),
        has_temperature_switch=bool(payload.get("has_temperature_switch", False)),
        has_tamper_switch=bool(payload.get("has_tamper_switch", False)),
        has_lid_limit_switch=bool(payload.get("has_lid_limit_switch", False)),
        has_high_level_switch=bool(payload.get("has_high_level_switch", False)),
        has_low_level_switch=bool(payload.get("has_low_level_switch", False)),
        has_water_detection=bool(payload.get("has_water_detection", True)),
        status=str(payload.get("status") or "ACTIVE").upper(),
    )
    db.add(tank)
    db.flush()

    calibration_count = _replace_calibration(
        db, tank, payload.get("calibration") or [], payload.get("calibration_version") or "v1"
    )
    sensor_count = _replace_sensors(db, tank, payload.get("sensors"))

    controller_payload = payload.get("controller")
    if controller_payload:
        controller_uid = str(controller_payload.get("device_uid") or "").strip()
        if not controller_uid:
            raise HTTPException(status_code=400, detail="Controller device UID is required")
        if db.scalar(select(TankController).where(TankController.device_uid == controller_uid)):
            raise HTTPException(status_code=409, detail="Controller UID already registered")
        db.add(
            TankController(
                device_uid=controller_uid,
                tank_id=tank.id,
                connection_mode=str(controller_payload.get("connection_mode") or "WIFI").upper(),
                signal_strength_dbm=int(controller_payload.get("signal_strength_dbm") or -65),
                modbus_address=int(controller_payload.get("modbus_address") or 1),
                firmware_version=controller_payload.get("firmware_version") or "v1.0.0",
                is_online=False,
            )
        )

    db.flush()
    write_audit(
        db,
        user,
        "CREATE_TANK",
        "Tank",
        tank.id,
        after={**_tank_out(tank), "calibration_rows": calibration_count, "sensors": sensor_count},
        request=request,
    )
    db.commit()
    db.refresh(tank)
    return _tank_out(tank)


@router.patch("/tanks/{tank_id}")
def update_tank(
    tank_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tanks", "edit")),
):
    tank = db.scalar(select(Tank).where(Tank.id == tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Tank not found")
    _ensure_station_scope(db, user, tank.station_id)
    before = _tank_out(tank)

    if payload.get("code"):
        code = str(payload["code"]).strip()
        if db.scalar(
            select(Tank).where(
                Tank.station_id == tank.station_id,
                func.upper(Tank.code) == code.upper(),
                Tank.id != tank.id,
            )
        ):
            raise HTTPException(status_code=409, detail="Tank code already exists at this station")
        tank.code = code
    if "product_id" in payload or "product_code" in payload:
        product = _resolve_product(db, payload)
        tank.product_id = product.id if product else None
    if "capacity_l" in payload:
        tank.capacity_l = parse_float(payload["capacity_l"], "capacity_l", minimum=1)
    if "location_type" in payload:
        location = str(payload["location_type"]).upper()
        if location not in LOCATION_TYPES:
            raise HTTPException(status_code=400, detail="location_type must be UNDERGROUND or SURFACE")
        tank.location_type = location
    for field in ("name", "serial_number", "position", "dimensions", "probe_id", "probe_comm_type", "monitoring_device"):
        if field in payload:
            setattr(tank, field, payload[field])
    if "installation_date" in payload:
        tank.installation_date = _parse_datetime(payload["installation_date"])
    if "installation_status" in payload:
        tank.installation_status = str(payload["installation_status"]).upper()
    for flag in (
        "has_temperature_sensor",
        "has_temperature_switch",
        "has_tamper_switch",
        "has_lid_limit_switch",
        "has_high_level_switch",
        "has_low_level_switch",
        "has_water_detection",
    ):
        if flag in payload:
            setattr(tank, flag, bool(payload[flag]))
    if "status" in payload:
        tank.status = str(payload["status"]).upper()

    if "calibration" in payload:
        _replace_calibration(db, tank, payload.get("calibration") or [], payload.get("calibration_version") or "v1")
    if "sensors" in payload:
        _replace_sensors(db, tank, payload.get("sensors") or [])

    db.flush()
    write_audit(db, user, "UPDATE_TANK", "Tank", tank.id, before=before, after=_tank_out(tank), request=request)
    db.commit()
    db.refresh(tank)
    return _tank_out(tank)


@router.get("/tanks/{tank_id}/calibration")
def get_calibration(tank_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tank = db.scalar(select(Tank).where(Tank.id == tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Tank not found")
    _ensure_station_scope(db, user, tank.station_id)
    rows = sorted(tank.calibration_rows, key=lambda r: r.height_mm)
    return [
        {"id": r.id, "version": r.version, "height_mm": r.height_mm, "volume_l": r.volume_l, "water_mm": r.water_mm}
        for r in rows
    ]


@router.put("/tanks/{tank_id}/calibration")
def set_calibration(
    tank_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tanks", "edit")),
):
    tank = db.scalar(select(Tank).where(Tank.id == tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Tank not found")
    _ensure_station_scope(db, user, tank.station_id)
    count = _replace_calibration(
        db, tank, payload.get("rows") or [], payload.get("version") or "v1"
    )
    write_audit(db, user, "SET_TANK_CALIBRATION", "Tank", tank.id, after={"rows": count}, request=request)
    db.commit()
    return {"tank_id": tank.id, "rows": count}


@router.get("/tanks/{tank_id}/volume")
def volume_at_level(
    tank_id: str,
    level_mm: float = Query(..., ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tank = db.scalar(select(Tank).where(Tank.id == tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Tank not found")
    _ensure_station_scope(db, user, tank.station_id)
    volume = tank.volume_from_calibration(level_mm)
    estimated = volume is None
    if volume is None:
        # Clearly-labelled proportional estimate when no strapping chart exists.
        volume = round(tank.capacity_l * min(1.0, max(0.0, level_mm / 3000.0)), 2)
    return {
        "tank_id": tank.id,
        "level_mm": level_mm,
        "volume_l": round(volume, 2),
        "source": "ESTIMATE" if estimated else "CALIBRATION",
        "has_calibration": bool(tank.calibration_rows),
    }


@router.post("/tanks/{tank_id}/toggle-hatch")
def toggle_tank_hatch(
    tank_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tanks", "manage")),
):
    tank = db.scalar(select(Tank).where(Tank.id == tank_id))
    if not tank:
        raise HTTPException(status_code=404, detail="Tank not found")
    _ensure_station_scope(db, user, tank.station_id)
    tank.hatch_open = not tank.hatch_open
    if tank.hatch_open:
        create_alert(
            db,
            alert_type="TANK_HATCH_OPEN",
            category="TANK_SECURITY",
            severity="CRITICAL",
            title=f"Tank hatch opened: {tank.code}",
            description=(
                f"Hatch access detected on {tank.code} at "
                f"{tank.station.name if tank.station else 'station'}. Physical inspection required."
            ),
            station_id=tank.station_id,
            device_type="TANK",
            device_id=tank.id,
            entity_type="tank",
            entity_id=tank.id,
            dedupe_minutes=10,
        )
    db.commit()
    return {"tank_id": tank.id, "hatch_open": tank.hatch_open}


@router.post("/tanks/{tank_id}/update-atg")
def update_atg_reading(
    tank_id: str,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tanks", "manage")),
):
    tank = db.scalar(select(Tank).where(Tank.id == tank_id))
    if not tank:
        raise HTTPException(status_code=404, detail="Tank not found")
    _ensure_station_scope(db, user, tank.station_id)

    level = payload.get("current_level_mm")
    if level is not None:
        tank.current_level_mm = parse_float(level, "current_level_mm", minimum=0)
        calibrated = tank.volume_from_calibration(tank.current_level_mm)
        if calibrated is not None:
            tank.current_volume_l = round(calibrated, 2)
    if "current_volume_l" in payload:
        tank.current_volume_l = parse_float(
            payload["current_volume_l"], "current_volume_l", minimum=0, maximum=tank.capacity_l
        )
    if "current_water_mm" in payload:
        tank.current_water_mm = parse_float(payload["current_water_mm"], "current_water_mm", minimum=0)
    if "current_temperature_c" in payload:
        tank.current_temperature_c = parse_float(payload["current_temperature_c"], "current_temperature_c")
    if "hatch_open" in payload:
        tank.hatch_open = bool(payload["hatch_open"])

    db.add(
        TankReading(
            tank_id=tank.id,
            fuel_level_mm=tank.current_level_mm,
            fuel_volume_l=tank.current_volume_l,
            water_level_mm=tank.current_water_mm,
            temperature_c=tank.current_temperature_c,
            ullage_l=max(0.0, tank.capacity_l - tank.current_volume_l),
            hatch_open=tank.hatch_open,
            volume_source="MANUAL",
        )
    )

    if tank.current_water_mm >= settings.TANK_WATER_WARNING_MM:
        create_alert(
            db,
            alert_type="WATER_DETECTED",
            category="TANK_SECURITY",
            severity="CRITICAL" if tank.current_water_mm >= settings.TANK_WATER_CRITICAL_MM else "HIGH",
            title=f"Water ingress detected in {tank.code}",
            description=(
                f"Interface water measured at {tank.current_water_mm} mm "
                f"(warning threshold {settings.TANK_WATER_WARNING_MM} mm)."
            ),
            station_id=tank.station_id,
            device_type="TANK",
            device_id=tank.id,
            entity_type="tank",
            entity_id=tank.id,
            actual_value=tank.current_water_mm,
            expected_value=settings.TANK_WATER_WARNING_MM,
            discrepancy=tank.current_water_mm - settings.TANK_WATER_WARNING_MM,
            dedupe_minutes=60,
        )
    if tank.hatch_open:
        create_alert(
            db,
            alert_type="TANK_HATCH_OPEN",
            category="TANK_SECURITY",
            severity="CRITICAL",
            title=f"Tank hatch open: {tank.code}",
            description="Hatch sensor reports an open cover. Verify authorised access immediately.",
            station_id=tank.station_id,
            device_type="TANK",
            device_id=tank.id,
            entity_type="tank",
            entity_id=tank.id,
            dedupe_minutes=10,
        )

    db.commit()
    return {"tank_id": tank.id, "volume_l": tank.current_volume_l, "level_mm": tank.current_level_mm}


@router.get("/tanks/{tank_id}/readings")
def tank_readings(
    tank_id: str,
    limit: int = Query(default=100, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tank = db.scalar(select(Tank).where(Tank.id == tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Tank not found")
    _ensure_station_scope(db, user, tank.station_id)
    rows = db.scalars(
        select(TankReading)
        .where(TankReading.tank_id == tank.id)
        .order_by(TankReading.recorded_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "fuel_level_mm": row.fuel_level_mm,
            "fuel_volume_l": row.fuel_volume_l,
            "water_level_mm": row.water_level_mm,
            "temperature_c": row.temperature_c,
            "ullage_l": row.ullage_l,
            "hatch_open": row.hatch_open,
            "volume_source": row.volume_source,
            "recorded_at": row.recorded_at.isoformat(),
        }
        for row in rows
    ]
