import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.config import settings
from app.core.deps import allowed_station_ids, require_permission, write_audit
from app.core.security import token_hash
from app.core.validation import parse_float
from app.db.base import get_db
from app.models.auth import User
from app.models.core import DeviceEvent, FCCDevice, Tank, TankController, TankReading
from app.modules.alerts.service import create_alert

router = APIRouter(prefix="/api/v1/device-ingest", tags=["device ingestion"])


class DeviceEventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=8, max_length=96)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return value


class FCCHeartbeat(DeviceEventPayload):
    firmware_version: str | None = Field(default=None, max_length=40)
    signal_strength_dbm: int | None = Field(default=None, ge=-150, le=0)
    temperature_c: float | None = Field(default=None, ge=-40, le=125)
    power_status: str | None = Field(default=None, max_length=30)
    hardware_fault: str | None = Field(default=None, max_length=255)
    communication_errors: int | None = Field(default=None, ge=0)


class TankTelemetry(DeviceEventPayload):
    fuel_level_mm: float = Field(ge=0)
    fuel_volume_l: float = Field(ge=0)
    water_level_mm: float = Field(default=0, ge=0)
    temperature_c: float = Field(ge=-40, le=125)
    hatch_open: StrictBool = False


def _validate_time(observed_at: datetime) -> datetime:
    observed = observed_at.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if observed > now + timedelta(seconds=settings.INGEST_ALLOWED_CLOCK_SKEW_SECONDS):
        raise HTTPException(status_code=400, detail="Device event timestamp is too far in the future")
    max_age = timedelta(minutes=settings.DUPLICATE_WINDOW_MINUTES)
    if observed < now - max_age:
        raise HTTPException(status_code=400, detail="Device event is older than the accepted offline replay window")
    return observed.replace(tzinfo=None)


def _event_key(device_type: str, device_uid: str, event_id: str) -> str:
    return hashlib.sha256(f"{device_type}:{device_uid}:{event_id}".encode()).hexdigest()


def _authenticate_device(db: Session, device_type: str, device_uid: str, authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Device bearer credential required")
    presented = authorization[7:].strip()
    if not presented:
        raise HTTPException(status_code=401, detail="Device bearer credential required")

    model = FCCDevice if device_type == "FCC_CONTROLLER" else TankController
    device = db.scalar(select(model).where(model.device_uid == device_uid))
    if device is None or not device.api_key_hash:
        raise HTTPException(status_code=401, detail="Device credential is not provisioned")
    if not hmac.compare_digest(token_hash(presented), device.api_key_hash):
        raise HTTPException(status_code=401, detail="Invalid device credential")
    if getattr(device, "status", "ACTIVE") != "ACTIVE":
        raise HTTPException(status_code=403, detail="Device is not active")
    return device


def _event_payload_hash(payload: BaseModel) -> str:
    encoded = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _is_duplicate(db: Session, event_key: str, payload_hash: str) -> bool:
    # Redis answers replays without a database round trip. When Redis is not
    # available the original database-backed dedupe below still applies.
    cached_hash = cache_get(event_key)
    if cached_hash is not None:
        if cached_hash != payload_hash:
            raise HTTPException(status_code=409, detail="Event ID was already used with a different payload")
        return True
    replay_floor = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        minutes=settings.DUPLICATE_WINDOW_MINUTES
    )
    event = db.scalar(
        select(DeviceEvent).where(
            DeviceEvent.event_key == event_key,
            DeviceEvent.received_at >= replay_floor,
        )
    )
    if event is None:
        return False
    if event.payload_hash != payload_hash:
        raise HTTPException(status_code=409, detail="Event ID was already used with a different payload")
    return True


def _concurrent_duplicate(db: Session, event_key: str, payload_hash: str) -> bool:
    db.rollback()
    replay_floor = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        minutes=settings.DUPLICATE_WINDOW_MINUTES
    )
    event = db.scalar(
        select(DeviceEvent).where(
            DeviceEvent.event_key == event_key,
            DeviceEvent.received_at >= replay_floor,
        )
    )
    if event is None:
        return False
    if event.payload_hash != payload_hash:
        raise HTTPException(status_code=409, detail="Event ID was already used with a different payload")
    return True


def _provision_device_key(db: Session, device, actor: User, request: Request) -> dict:
    key = secrets.token_urlsafe(32)
    device.api_key_hash = token_hash(key)
    write_audit(
        db,
        actor,
        "ROTATE_DEVICE_CREDENTIAL",
        "Device",
        device.id,
        after={"device_uid": device.device_uid},
        request=request,
    )
    db.commit()
    return {
        "device_uid": device.device_uid,
        "authorization_scheme": "Bearer",
        "credential": key,
        "warning": "Shown once. Store securely on the device; rotate to revoke it.",
    }


@router.post("/provision/fcc/{fcc_id}")
def provision_fcc_credential(
    fcc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("fcc_devices", "manage")),
):
    device = db.scalar(select(FCCDevice).where(FCCDevice.id == fcc_id))
    if device is None:
        raise HTTPException(status_code=404, detail="FCC controller not found")
    station_id = device.nozzle.dispenser.station_id
    allowed = allowed_station_ids(user)
    if allowed is not None and station_id not in allowed:
        raise HTTPException(status_code=403, detail="Station access denied")
    return _provision_device_key(db, device, user, request)


@router.post("/provision/tank/{controller_id}")
def provision_tank_credential(
    controller_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tank_controllers", "manage")),
):
    device = db.scalar(select(TankController).where(TankController.id == controller_id))
    if device is None:
        raise HTTPException(status_code=404, detail="Tank controller not found")
    station_id = device.tank.station_id
    allowed = allowed_station_ids(user)
    if allowed is not None and station_id not in allowed:
        raise HTTPException(status_code=403, detail="Station access denied")
    return _provision_device_key(db, device, user, request)


@router.post("/fcc/{device_uid}/heartbeat")
def receive_fcc_heartbeat(
    device_uid: str,
    payload: FCCHeartbeat,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    device = _authenticate_device(db, "FCC_CONTROLLER", device_uid, authorization)
    key = _event_key("FCC_CONTROLLER", device_uid, payload.event_id)
    payload_hash = _event_payload_hash(payload)
    if _is_duplicate(db, key, payload_hash):
        return {"accepted": True, "duplicate": True, "device_uid": device_uid}
    observed = _validate_time(payload.observed_at)

    is_stale = device.last_heartbeat is not None and observed <= device.last_heartbeat
    if not is_stale and payload.firmware_version is not None:
        device.firmware_version = payload.firmware_version
    if not is_stale and payload.signal_strength_dbm is not None:
        device.signal_strength_dbm = payload.signal_strength_dbm
    if not is_stale and payload.temperature_c is not None:
        device.temperature_c = payload.temperature_c
    if not is_stale and payload.power_status is not None:
        device.power_status = payload.power_status
    if not is_stale and payload.hardware_fault is not None:
        device.hardware_fault = payload.hardware_fault
    if not is_stale and payload.communication_errors is not None:
        device.communication_errors = payload.communication_errors
    if not is_stale:
        device.last_heartbeat = observed
        device.last_communication_at = datetime.now(timezone.utc).replace(tzinfo=None)
        device.is_online = True

    db.add(DeviceEvent(
        device_uid=device_uid,
        device_type="FCC_CONTROLLER",
        event_key=key,
        station_id=device.nozzle.dispenser.station_id,
        event_type="HEARTBEAT",
        payload_hash=payload_hash,
        processing_status="STALE" if is_stale else "ACCEPTED",
        device_timestamp=observed,
    ))
    try:
        db.commit()
    except IntegrityError:
        if _concurrent_duplicate(db, key, payload_hash):
            return {"accepted": True, "duplicate": True, "device_uid": device_uid}
        raise
    cache_set(key, payload_hash, settings.DUPLICATE_WINDOW_MINUTES * 60)
    return {"accepted": True, "duplicate": False, "stale": is_stale, "device_uid": device_uid}


@router.post("/tank/{device_uid}/reading")
def receive_tank_reading(
    device_uid: str,
    payload: TankTelemetry,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    controller = _authenticate_device(db, "TANK_CONTROLLER", device_uid, authorization)
    tank = db.scalar(select(Tank).where(Tank.id == controller.tank_id))
    if tank is None or tank.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Tank is not active")
    key = _event_key("TANK_CONTROLLER", device_uid, payload.event_id)
    payload_hash = _event_payload_hash(payload)
    if _is_duplicate(db, key, payload_hash):
        return {"accepted": True, "duplicate": True, "device_uid": device_uid}
    observed = _validate_time(payload.observed_at)

    reported_volume = parse_float(payload.fuel_volume_l, "fuel_volume_l", minimum=0, maximum=tank.capacity_l)
    if tank.calibration_rows:
        heights = [row.height_mm for row in tank.calibration_rows]
        if payload.fuel_level_mm < min(heights) or payload.fuel_level_mm > max(heights):
            raise HTTPException(status_code=400, detail="Fuel level is outside the configured calibration chart")
    measured_volume = tank.volume_from_calibration(payload.fuel_level_mm)
    volume_source = "SERVER_CALIBRATION" if measured_volume is not None else "DEVICE_REPORTED"
    volume = round(measured_volume if measured_volume is not None else reported_volume, 2)
    if volume > tank.capacity_l:
        raise HTTPException(status_code=400, detail="Calibrated tank volume exceeds configured capacity")

    is_stale = controller.last_heartbeat is not None and observed <= controller.last_heartbeat
    if not is_stale:
        tank.current_level_mm = payload.fuel_level_mm
        tank.current_volume_l = volume
        tank.current_water_mm = payload.water_level_mm
        tank.current_temperature_c = payload.temperature_c
        tank.hatch_open = payload.hatch_open
        controller.last_heartbeat = observed
        controller.is_online = True
    db.add(TankReading(
        tank_id=tank.id,
        fuel_level_mm=payload.fuel_level_mm,
        fuel_volume_l=volume,
        water_level_mm=payload.water_level_mm,
        temperature_c=payload.temperature_c,
        ullage_l=max(0.0, tank.capacity_l - volume),
        hatch_open=payload.hatch_open,
        recorded_at=observed,
        volume_source=volume_source,
    ))
    db.add(DeviceEvent(
        device_uid=device_uid,
        device_type="TANK_CONTROLLER",
        event_key=key,
        station_id=tank.station_id,
        event_type="TANK_READING",
        payload_hash=payload_hash,
        processing_status="STALE" if is_stale else "ACCEPTED",
        device_timestamp=observed,
    ))
    if not is_stale and payload.water_level_mm >= settings.TANK_WATER_WARNING_MM:
        create_alert(
            db,
            alert_type="WATER_DETECTED",
            category="TANK_SECURITY",
            severity="CRITICAL" if payload.water_level_mm >= settings.TANK_WATER_CRITICAL_MM else "HIGH",
            title=f"Water ingress detected in {tank.code}",
            description=f"Device telemetry reported {payload.water_level_mm:.2f} mm of water.",
            station_id=tank.station_id,
            device_type="TANK",
            device_id=tank.id,
            entity_type="tank",
            entity_id=tank.id,
            actual_value=payload.water_level_mm,
            expected_value=settings.TANK_WATER_WARNING_MM,
            discrepancy=payload.water_level_mm - settings.TANK_WATER_WARNING_MM,
        )
    if not is_stale and payload.hatch_open:
        create_alert(
            db,
            alert_type="TANK_HATCH_OPEN",
            category="TANK_SECURITY",
            severity="CRITICAL",
            title=f"Tank hatch open: {tank.code}",
            description="Tank controller telemetry reports an open hatch.",
            station_id=tank.station_id,
            device_type="TANK",
            device_id=tank.id,
            entity_type="tank",
            entity_id=tank.id,
        )
    try:
        db.commit()
    except IntegrityError:
        if _concurrent_duplicate(db, key, payload_hash):
            return {"accepted": True, "duplicate": True, "device_uid": device_uid}
        raise
    cache_set(key, payload_hash, settings.DUPLICATE_WINDOW_MINUTES * 60)
    return {
        "accepted": True,
        "duplicate": False,
        "stale": is_stale,
        "device_uid": device_uid,
        "tank_id": tank.id,
        "fuel_volume_l": volume,
        "volume_source": volume_source,
    }
