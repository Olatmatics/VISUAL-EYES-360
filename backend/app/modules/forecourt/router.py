import uuid
from datetime import datetime
from typing import Any

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
from app.core.validation import like, parse_float, validate_station, utcnow
from app.core.config import settings
from app.db.base import get_db
from app.models.auth import User
from app.models.core import (
    Dispenser,
    FCCDevice,
    FuelProduct,
    Nozzle,
    POSTerminal,
    PumpType,
    Station,
    Tank,
)

router = APIRouter(prefix="/api/v1", tags=["forecourt"])

CONNECTION_MODES = {"WIFI", "SIM"}
NOZZLE_CONFIGS = {"SINGLE", "DOUBLE", "OTHER"}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date/time: {value}")


def _ensure_station_scope(db: Session, user: User, station_id: str) -> Station:
    station = validate_station(db, station_id)
    allowed = allowed_station_ids(user)
    if allowed is not None and station.id not in allowed:
        raise HTTPException(status_code=403, detail="Station access denied")
    return station


def _nozzle_out(nozzle: Nozzle) -> dict:
    return {
        "id": nozzle.id,
        "dispenser_id": nozzle.dispenser_id,
        "dispenser_code": nozzle.dispenser.code if nozzle.dispenser else "",
        "station_id": nozzle.dispenser.station_id if nozzle.dispenser else "",
        "station_name": nozzle.dispenser.station.name if nozzle.dispenser and nozzle.dispenser.station else "",
        "number": nozzle.number,
        "name": nozzle.name,
        "label": nozzle.label,
        "price": nozzle.price,
        "status": nozzle.status,
        "product_id": nozzle.product_id,
        "product_code": nozzle.product.code if nozzle.product else None,
        "tank_id": nozzle.tank_id,
        "tank_code": nozzle.tank.code if nozzle.tank else None,
        "totalizer_l": nozzle.totalizer_l,
        "previous_totalizer_l": nozzle.previous_totalizer_l,
        "fcc": {
            "id": nozzle.fcc.id,
            "device_uid": nozzle.fcc.device_uid,
            "connection_mode": nozzle.fcc.connection_mode,
            "signal_strength_dbm": nozzle.fcc.signal_strength_dbm,
            "is_online": nozzle.fcc.is_online,
            "calibration_factor": nozzle.fcc.calibration_factor,
            "firmware_version": nozzle.fcc.firmware_version,
        }
        if nozzle.fcc
        else None,
        "pos": {
            "id": nozzle.pos.id,
            "terminal_id": nozzle.pos.terminal_id,
            "provider": nozzle.pos.provider,
            "active": nozzle.pos.is_active,
        }
        if nozzle.pos
        else None,
    }


def _dispenser_out(dispenser: Dispenser) -> dict:
    return {
        "id": dispenser.id,
        "station_id": dispenser.station_id,
        "station_name": dispenser.station.name if dispenser.station else "",
        "code": dispenser.code,
        "name": dispenser.name,
        "display_name": dispenser.display_name,
        "serial": dispenser.serial,
        "manufacturer": dispenser.manufacturer,
        "custom_manufacturer": dispenser.custom_manufacturer,
        "brand": dispenser.brand,
        "model": dispenser.model,
        "dispenser_type": dispenser.dispenser_type,
        "pump_type_id": dispenser.pump_type_id,
        "pump_type": dispenser.pump_type.name if dispenser.pump_type else None,
        "nozzle_config": dispenser.nozzle_config,
        "nozzle_count": len(dispenser.nozzles),
        "protocol": dispenser.protocol,
        "interface": dispenser.interface,
        "status": dispenser.status,
        "communication_status": dispenser.communication_status,
        "installation_date": dispenser.installation_date.isoformat() if dispenser.installation_date else None,
        "totalizer_l": dispenser.totalizer_l,
        "nozzles": [_nozzle_out(nozzle) for nozzle in sorted(dispenser.nozzles, key=lambda n: n.number)],
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


def _validate_tank_assignment(db: Session, dispenser: Dispenser, tank_id: str | None, product_id: str | None) -> Tank | None:
    if not tank_id:
        return None
    tank = db.scalar(select(Tank).where(Tank.id == tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Tank not found")
    if tank.station_id != dispenser.station_id:
        raise HTTPException(status_code=400, detail="Tank belongs to a different station")
    if product_id and tank.product_id and tank.product_id != product_id:
        raise HTTPException(status_code=400, detail="Nozzle product does not match the tank product")
    return tank


# --------------------------------------------------------------------------
# Pump types (administrator-managed)
# --------------------------------------------------------------------------
@router.get("/pump-types")
def list_pump_types(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.has_permission("pump_types", "view") and not user.has_permission("dispensers", "view"):
        raise HTTPException(status_code=403, detail="Permission denied")
    query = select(PumpType)
    if not include_inactive:
        query = query.where(PumpType.is_active.is_(True))
    rows = db.scalars(query.order_by(PumpType.name)).all()
    return [
        {"id": p.id, "code": p.code, "name": p.name, "description": p.description, "is_active": p.is_active}
        for p in rows
    ]


@router.post("/pump-types", status_code=201)
def create_pump_type(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("pump_types", "create")),
):
    code = str(payload.get("code") or "").strip().upper()
    name = str(payload.get("name") or "").strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail="Code and name are required")
    if db.scalar(select(PumpType).where(func.upper(PumpType.code) == code)):
        raise HTTPException(status_code=409, detail="Pump type code already exists")
    if db.scalar(select(PumpType).where(func.lower(PumpType.name) == name.lower())):
        raise HTTPException(status_code=409, detail="Pump type name already exists")
    item = PumpType(code=code, name=name, description=payload.get("description"))
    db.add(item)
    db.flush()
    write_audit(db, user, "CREATE_PUMP_TYPE", "PumpType", item.id, after=payload, request=request)
    db.commit()
    return {"id": item.id, "code": item.code, "name": item.name}


@router.patch("/pump-types/{pump_type_id}")
def update_pump_type(
    pump_type_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("pump_types", "edit")),
):
    item = db.scalar(select(PumpType).where(PumpType.id == pump_type_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Pump type not found")
    if payload.get("name"):
        item.name = str(payload["name"]).strip()
    if "description" in payload:
        item.description = payload.get("description")
    if "is_active" in payload:
        item.is_active = bool(payload["is_active"])
    db.flush()
    write_audit(db, user, "UPDATE_PUMP_TYPE", "PumpType", item.id, after=payload, request=request)
    db.commit()
    return {"id": item.id, "code": item.code, "name": item.name, "is_active": item.is_active}


# --------------------------------------------------------------------------
# Dispensers
# --------------------------------------------------------------------------
@router.get("/dispensers")
def list_dispensers(
    station_id: str | None = None,
    state_id: str | None = None,
    lga_id: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.has_permission("dispensers", "view"):
        raise HTTPException(status_code=403, detail="Permission denied")
    query = select(Dispenser)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        query = query.where(Dispenser.station_id.in_(allowed)) if allowed else query.where(False)
    if station_id:
        query = query.where(Dispenser.station_id == station_id)
    if state_id or lga_id:
        query = query.join(Station, Dispenser.station_id == Station.id)
        if state_id:
            query = query.where(Station.state_id == state_id)
        if lga_id:
            query = query.where(Station.lga_id == lga_id)
    if search:
        pattern = like(search)
        query = query.where(Dispenser.code.ilike(pattern) | Dispenser.serial.ilike(pattern) | Dispenser.model.ilike(pattern))
    return [_dispenser_out(d) for d in db.scalars(query.order_by(Dispenser.code)).all()]


@router.post("/dispensers", status_code=status.HTTP_201_CREATED)
def create_dispenser(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("dispensers", "create")),
):
    station = _ensure_station_scope(db, user, payload.get("station_id"))
    code = str(payload.get("code") or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Dispenser code is required")
    if db.scalar(
        select(Dispenser).where(Dispenser.station_id == station.id, func.upper(Dispenser.code) == code.upper())
    ):
        raise HTTPException(status_code=409, detail="Dispenser code already exists at this station")

    serial = (payload.get("serial") or "").strip() or None
    if serial and db.scalar(select(Dispenser).where(Dispenser.serial == serial)):
        raise HTTPException(status_code=409, detail="Dispenser serial number already registered")

    manufacturer = str(payload.get("manufacturer") or "Wayne").strip()
    custom_manufacturer = (payload.get("custom_manufacturer") or "").strip() or None
    if manufacturer.lower() == "other" and not custom_manufacturer:
        raise HTTPException(status_code=400, detail="Custom manufacturer name is required when brand is 'Other'")

    pump_type = None
    if payload.get("pump_type_id"):
        pump_type = db.scalar(select(PumpType).where(PumpType.id == payload["pump_type_id"]))
        if pump_type is None:
            raise HTTPException(status_code=400, detail="Unknown pump type")

    nozzle_config = str(payload.get("nozzle_config") or "SINGLE").upper()
    if nozzle_config not in NOZZLE_CONFIGS:
        raise HTTPException(status_code=400, detail="nozzle_config must be SINGLE, DOUBLE or OTHER")
    if nozzle_config == "SINGLE":
        nozzle_count = 1
    elif nozzle_config == "DOUBLE":
        nozzle_count = 2
    else:
        nozzle_count = int(payload.get("nozzle_count") or 1)
        if not 1 <= nozzle_count <= 12:
            raise HTTPException(status_code=400, detail="nozzle_count must be between 1 and 12")

    dispenser = Dispenser(
        station_id=station.id,
        code=code,
        name=payload.get("name"),
        serial=serial or f"DSP-{uuid.uuid4().hex[:8].upper()}",
        manufacturer=manufacturer,
        custom_manufacturer=custom_manufacturer,
        model=payload.get("model"),
        dispenser_type=payload.get("dispenser_type"),
        pump_type_id=pump_type.id if pump_type else None,
        nozzle_config=nozzle_config,
        nozzle_count=nozzle_count,
        protocol=payload.get("protocol"),
        interface=payload.get("interface"),
        status=str(payload.get("status") or "ACTIVE").upper(),
        communication_status=str(payload.get("communication_status") or "UNKNOWN").upper(),
        installation_date=_parse_datetime(payload.get("installation_date")),
        totalizer_l=parse_float(payload.get("totalizer_l", 0), "totalizer_l", minimum=0),
    )
    db.add(dispenser)
    db.flush()

    supplied = payload.get("nozzles") or []
    for index in range(nozzle_count):
        detail = supplied[index] if index < len(supplied) else {}
        product = _resolve_product(db, detail)
        tank = _validate_tank_assignment(db, dispenser, detail.get("tank_id"), product.id if product else None)
        db.add(
            Nozzle(
                dispenser_id=dispenser.id,
                tank_id=tank.id if tank else None,
                number=int(detail.get("number") or index + 1),
                name=detail.get("name") or f"Nozzle {index + 1}",
                product_id=product.id if product else None,
                price=parse_float(detail.get("price", 0), "price", minimum=0),
                status=str(detail.get("status") or "ACTIVE").upper(),
            )
        )
    db.flush()
    db.refresh(dispenser)

    write_audit(db, user, "CREATE_DISPENSER", "Dispenser", dispenser.id, after=_dispenser_out(dispenser), request=request)
    db.commit()
    return _dispenser_out(dispenser)


@router.patch("/dispensers/{dispenser_id}")
def update_dispenser(
    dispenser_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("dispensers", "edit")),
):
    dispenser = db.scalar(select(Dispenser).where(Dispenser.id == dispenser_id))
    if dispenser is None:
        raise HTTPException(status_code=404, detail="Dispenser not found")
    _ensure_station_scope(db, user, dispenser.station_id)
    before = _dispenser_out(dispenser)

    if payload.get("code"):
        code = str(payload["code"]).strip()
        if db.scalar(
            select(Dispenser).where(
                Dispenser.station_id == dispenser.station_id,
                func.upper(Dispenser.code) == code.upper(),
                Dispenser.id != dispenser.id,
            )
        ):
            raise HTTPException(status_code=409, detail="Dispenser code already exists at this station")
        dispenser.code = code
    if "serial" in payload and payload["serial"]:
        serial = str(payload["serial"]).strip()
        if db.scalar(select(Dispenser).where(Dispenser.serial == serial, Dispenser.id != dispenser.id)):
            raise HTTPException(status_code=409, detail="Dispenser serial number already registered")
        dispenser.serial = serial
    for field in ("name", "model", "dispenser_type", "protocol", "interface"):
        if field in payload:
            setattr(dispenser, field, payload[field])
    if "manufacturer" in payload:
        manufacturer = str(payload["manufacturer"]).strip()
        custom = (payload.get("custom_manufacturer") or dispenser.custom_manufacturer or "").strip()
        if manufacturer.lower() == "other" and not custom:
            raise HTTPException(status_code=400, detail="Custom manufacturer name is required when brand is 'Other'")
        dispenser.manufacturer = manufacturer
        dispenser.custom_manufacturer = custom or None
    if "pump_type_id" in payload:
        if payload["pump_type_id"]:
            if db.scalar(select(PumpType).where(PumpType.id == payload["pump_type_id"])) is None:
                raise HTTPException(status_code=400, detail="Unknown pump type")
            dispenser.pump_type_id = payload["pump_type_id"]
        else:
            dispenser.pump_type_id = None
    if "status" in payload:
        dispenser.status = str(payload["status"]).upper()
    if "communication_status" in payload:
        dispenser.communication_status = str(payload["communication_status"]).upper()
    if "installation_date" in payload:
        dispenser.installation_date = _parse_datetime(payload["installation_date"])

    db.flush()
    write_audit(db, user, "UPDATE_DISPENSER", "Dispenser", dispenser.id, before=before, after=_dispenser_out(dispenser), request=request)
    db.commit()
    return _dispenser_out(dispenser)


# --------------------------------------------------------------------------
# Nozzles
# --------------------------------------------------------------------------
@router.get("/nozzles")
def list_nozzles(
    station_id: str | None = None,
    dispenser_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.has_permission("nozzles", "view"):
        raise HTTPException(status_code=403, detail="Permission denied")
    query = select(Nozzle)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        query = query.join(Dispenser, Nozzle.dispenser_id == Dispenser.id).where(
            Dispenser.station_id.in_(allowed) if allowed else False
        )
    if station_id:
        query = query.join(Dispenser, Nozzle.dispenser_id == Dispenser.id).where(Dispenser.station_id == station_id)
    if dispenser_id:
        query = query.where(Nozzle.dispenser_id == dispenser_id)
    return [_nozzle_out(n) for n in db.scalars(query.order_by(Nozzle.number)).all()]


@router.post("/dispensers/{dispenser_id}/nozzles", status_code=201)
def create_nozzle(
    dispenser_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("nozzles", "create")),
):
    dispenser = db.scalar(select(Dispenser).where(Dispenser.id == dispenser_id))
    if dispenser is None:
        raise HTTPException(status_code=404, detail="Dispenser not found")
    _ensure_station_scope(db, user, dispenser.station_id)

    number = int(payload.get("number") or (len(dispenser.nozzles) + 1))
    if any(n.number == number for n in dispenser.nozzles):
        raise HTTPException(status_code=409, detail=f"Nozzle number {number} already exists on this dispenser")
    product = _resolve_product(db, payload)
    tank = _validate_tank_assignment(db, dispenser, payload.get("tank_id"), product.id if product else None)

    nozzle = Nozzle(
        dispenser_id=dispenser.id,
        tank_id=tank.id if tank else None,
        number=number,
        name=payload.get("name") or f"Nozzle {number}",
        product_id=product.id if product else None,
        price=parse_float(payload.get("price", 0), "price", minimum=0),
        status=str(payload.get("status") or "ACTIVE").upper(),
    )
    db.add(nozzle)
    dispenser.nozzle_count = len(dispenser.nozzles) + 1
    db.flush()
    write_audit(db, user, "CREATE_NOZZLE", "Nozzle", nozzle.id, after=payload, request=request)
    db.commit()
    db.refresh(nozzle)
    return _nozzle_out(nozzle)


@router.patch("/nozzles/{nozzle_id}")
def update_nozzle(
    nozzle_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("nozzles", "edit")),
):
    nozzle = db.scalar(select(Nozzle).where(Nozzle.id == nozzle_id))
    if nozzle is None:
        raise HTTPException(status_code=404, detail="Nozzle not found")
    _ensure_station_scope(db, user, nozzle.dispenser.station_id)
    before = _nozzle_out(nozzle)

    if "product_id" in payload or "product_code" in payload:
        product = _resolve_product(db, payload)
        nozzle.product_id = product.id if product else None
    if "tank_id" in payload:
        tank = _validate_tank_assignment(
            db, nozzle.dispenser, payload.get("tank_id"), nozzle.product_id
        )
        nozzle.tank_id = tank.id if tank else None
    if "price" in payload:
        nozzle.price = parse_float(payload["price"], "price", minimum=0)
    if "status" in payload:
        nozzle.status = str(payload["status"]).upper()
    if "name" in payload:
        nozzle.name = payload["name"]

    db.flush()
    write_audit(db, user, "UPDATE_NOZZLE", "Nozzle", nozzle.id, before=before, after=_nozzle_out(nozzle), request=request)
    db.commit()
    return _nozzle_out(nozzle)


@router.post("/nozzles/{nozzle_id}/assign-tank")
def assign_tank_to_nozzle(
    nozzle_id: str,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tank_pump_assignment", "manage")),
):
    nozzle = db.scalar(select(Nozzle).where(Nozzle.id == nozzle_id))
    if nozzle is None:
        raise HTTPException(status_code=404, detail="Nozzle not found")
    _ensure_station_scope(db, user, nozzle.dispenser.station_id)
    tank = _validate_tank_assignment(db, nozzle.dispenser, payload.get("tank_id"), nozzle.product_id)
    nozzle.tank_id = tank.id if tank else None
    db.commit()
    return {"nozzle_id": nozzle.id, "tank_id": nozzle.tank_id}


# --------------------------------------------------------------------------
# FCC controllers
# --------------------------------------------------------------------------
@router.get("/fcc-devices")
def list_fcc_devices(
    station_id: str | None = None,
    state_id: str | None = None,
    online_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.has_permission("fcc_devices", "view"):
        raise HTTPException(status_code=403, detail="Permission denied")
    query = select(FCCDevice)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        query = (
            query.join(Nozzle, FCCDevice.nozzle_id == Nozzle.id)
            .join(Dispenser, Nozzle.dispenser_id == Dispenser.id)
            .where(Dispenser.station_id.in_(allowed) if allowed else False)
        )
    if station_id or state_id:
        query = query.join(Nozzle, FCCDevice.nozzle_id == Nozzle.id).join(
            Dispenser, Nozzle.dispenser_id == Dispenser.id
        )
        if station_id:
            query = query.where(Dispenser.station_id == station_id)
        if state_id:
            query = query.join(Station, Dispenser.station_id == Station.id).where(Station.state_id == state_id)
    if online_only:
        query = query.where(FCCDevice.is_online.is_(True))

    rows = db.scalars(query.order_by(FCCDevice.device_uid)).all()
    result = []
    for device in rows:
        nozzle = device.nozzle
        dispenser = nozzle.dispenser if nozzle else None
        result.append(
            {
                "id": device.id,
                "device_uid": device.device_uid,
                "name": device.name,
                "serial_number": device.serial_number,
                "nozzle_id": device.nozzle_id,
                "nozzle_number": nozzle.number if nozzle else None,
                "dispenser_id": dispenser.id if dispenser else None,
                "dispenser_code": dispenser.code if dispenser else None,
                "station_id": dispenser.station_id if dispenser else None,
                "station_name": dispenser.station.name if dispenser and dispenser.station else "",
                "pos_terminal_id": device.pos_terminal_id,
                "pos_terminal": device.pos_terminal.terminal_id if device.pos_terminal else None,
                "firmware_version": device.firmware_version,
                "hardware_version": device.hardware_version,
                "connection_mode": device.connection_mode,
                "protocol": device.protocol,
                "ip_address": device.ip_address,
                "mac_address": device.mac_address,
                "sim_info": device.sim_info,
                "signal_strength_dbm": device.signal_strength_dbm,
                "calibration_factor": device.calibration_factor,
                "is_online": device.is_online,
                "status": device.status,
                "last_heartbeat": device.last_heartbeat.isoformat() if device.last_heartbeat else None,
                "last_communication_at": device.last_communication_at.isoformat() if device.last_communication_at else None,
                "temperature_c": device.temperature_c,
                "power_status": device.power_status,
                "hardware_fault": device.hardware_fault,
                "communication_errors": device.communication_errors,
            }
        )
    return result


@router.post("/fcc-devices", status_code=201)
def register_fcc(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("fcc_devices", "create")),
):
    device_uid = str(payload.get("device_uid") or "").strip()
    if not device_uid:
        raise HTTPException(status_code=400, detail="Controller device UID is required")
    if db.scalar(select(FCCDevice).where(FCCDevice.device_uid == device_uid)):
        raise HTTPException(status_code=409, detail="A controller with this UID already exists")

    nozzle_id = payload.get("nozzle_id")
    if not nozzle_id:
        raise HTTPException(status_code=400, detail="A nozzle must be selected")
    nozzle = db.scalar(select(Nozzle).where(Nozzle.id == nozzle_id))
    if nozzle is None:
        raise HTTPException(status_code=404, detail="Nozzle not found")
    dispenser = nozzle.dispenser
    station = dispenser.station if dispenser else None
    if dispenser is None or station is None:
        raise HTTPException(status_code=400, detail="Nozzle is not attached to a valid dispenser/station")
    _ensure_station_scope(db, user, station.id)

    if payload.get("station_id") and payload["station_id"] != station.id:
        raise HTTPException(status_code=400, detail="Selected station does not match the nozzle's station")
    if payload.get("dispenser_id") and payload["dispenser_id"] != dispenser.id:
        raise HTTPException(status_code=400, detail="Selected dispenser does not match the nozzle's dispenser")
    if nozzle.fcc is not None:
        raise HTTPException(status_code=409, detail="This nozzle already has a dedicated FCC controller")

    pos_terminal_id = payload.get("pos_terminal_id") or None
    if pos_terminal_id:
        pos = db.scalar(select(POSTerminal).where(POSTerminal.id == pos_terminal_id))
        if pos is None:
            raise HTTPException(status_code=404, detail="POS terminal not found")
        if pos.station_id != station.id:
            raise HTTPException(status_code=400, detail="POS terminal belongs to a different station")
        if pos.nozzle_id and pos.nozzle_id != nozzle.id:
            raise HTTPException(status_code=400, detail="POS terminal is assigned to a different nozzle")

    connection_mode = str(payload.get("connection_mode") or "WIFI").upper()
    if connection_mode not in CONNECTION_MODES:
        raise HTTPException(status_code=400, detail="connection_mode must be WIFI or SIM")

    device = FCCDevice(
        device_uid=device_uid,
        name=payload.get("name") or f"FCC {dispenser.code} N{nozzle.number}",
        serial_number=payload.get("serial_number"),
        hardware_version=payload.get("hardware_version"),
        firmware_version=payload.get("firmware_version") or "v1.0.0",
        station_id=station.id,
        dispenser_id=dispenser.id,
        nozzle_id=nozzle.id,
        pos_terminal_id=pos_terminal_id,
        protocol=payload.get("protocol"),
        ip_address=payload.get("ip_address"),
        mac_address=payload.get("mac_address"),
        sim_info=payload.get("sim_info"),
        connection_mode=connection_mode,
        signal_strength_dbm=int(payload.get("signal_strength_dbm") or -65),
        calibration_factor=parse_float(payload.get("calibration_factor", 100), "calibration_factor", minimum=0.01),
        installation_date=_parse_datetime(payload.get("installation_date")),
        status=str(payload.get("status") or "ACTIVE").upper(),
        is_online=False,
        last_heartbeat=None,
    )
    db.add(device)
    db.flush()
    write_audit(db, user, "REGISTER_FCC", "FCCDevice", device.id, after=payload, request=request)
    db.commit()
    db.refresh(device)
    return {
        "id": device.id,
        "device_uid": device.device_uid,
        "station_id": device.station_id,
        "dispenser_id": device.dispenser_id,
        "nozzle_id": device.nozzle_id,
    }


@router.patch("/fcc-devices/{fcc_id}")
def update_fcc(
    fcc_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("fcc_devices", "edit")),
):
    device = db.scalar(select(FCCDevice).where(FCCDevice.id == fcc_id))
    if device is None:
        raise HTTPException(status_code=404, detail="FCC controller not found")
    _ensure_station_scope(db, user, device.nozzle.dispenser.station_id)
    if "connection_mode" in payload:
        mode = str(payload["connection_mode"]).upper()
        if mode not in CONNECTION_MODES:
            raise HTTPException(status_code=400, detail="connection_mode must be WIFI or SIM")
        device.connection_mode = mode
    for field in ("name", "serial_number", "hardware_version", "firmware_version", "protocol", "ip_address", "mac_address", "sim_info", "power_status"):
        if field in payload:
            setattr(device, field, payload[field])
    if "signal_strength_dbm" in payload:
        device.signal_strength_dbm = int(payload["signal_strength_dbm"])
    if "calibration_factor" in payload:
        device.calibration_factor = parse_float(payload["calibration_factor"], "calibration_factor", minimum=0.01)
    if "status" in payload:
        device.status = str(payload["status"]).upper()
    if "is_online" in payload:
        raise HTTPException(status_code=400, detail="Online status is controlled by authenticated device telemetry")
    db.flush()
    write_audit(db, user, "UPDATE_FCC", "FCCDevice", device.id, after=payload, request=request)
    db.commit()
    return {"id": device.id, "is_online": device.is_online, "status": device.status}


@router.post("/fcc-devices/{fcc_id}/toggle-online")
def toggle_fcc_online(
    fcc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("fcc_devices", "manage")),
):
    if settings.ENVIRONMENT.lower() in {"production", "prod", "live"}:
        raise HTTPException(status_code=404, detail="FCC status simulation is unavailable")
    fcc = db.scalar(select(FCCDevice).where(FCCDevice.id == fcc_id))
    if not fcc:
        raise HTTPException(status_code=404, detail="FCC controller not found")
    _ensure_station_scope(db, user, fcc.nozzle.dispenser.station_id)
    fcc.is_online = not fcc.is_online
    fcc.status = "ACTIVE" if fcc.is_online else "OFFLINE"
    db.commit()
    return {"id": fcc.id, "is_online": fcc.is_online}
