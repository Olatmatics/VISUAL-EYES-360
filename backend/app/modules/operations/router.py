import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import allowed_station_ids, get_current_user, require_permission, write_audit
from app.core.validation import parse_float, utcnow
from app.db.base import get_db
from app.models.auth import User
from app.models.core import MaintenanceRecord, Tank, TankController, TankDelivery
from app.modules.alerts.service import create_alert
from app.modules.forecourt.router import _ensure_station_scope

router = APIRouter(prefix="/api/v1", tags=["operations"])

DELIVERY_STATUSES = {"PENDING", "VERIFIED", "DISPUTED", "REJECTED"}
MAINTENANCE_STATUSES = {"OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"}


def _delivery_out(item: TankDelivery) -> dict:
    return {
        "id": item.id,
        "reference": item.reference,
        "station_id": item.station_id,
        "station_name": item.station.name if item.station else "",
        "tank_id": item.tank_id,
        "tank_code": item.tank.code if item.tank else "",
        "product_id": item.product_id,
        "supplier": item.supplier,
        "vehicle_plate": item.vehicle_plate,
        "tanker_serial": item.tanker_serial,
        "delivered_quantity_l": item.delivered_quantity_l,
        "received_quantity_l": item.received_quantity_l,
        "variance_l": item.variance_l,
        "status": item.status,
        "delivery_date": item.delivery_date.isoformat(),
        "verified_by": item.verified_by,
        "notes": item.notes,
    }


def _maintenance_out(item: MaintenanceRecord) -> dict:
    return {
        "id": item.id,
        "reference": item.reference,
        "station_id": item.station_id,
        "station_name": item.station.name if item.station else "",
        "device_type": item.device_type,
        "device_id": item.device_id,
        "maintenance_type": item.maintenance_type,
        "title": item.title,
        "description": item.description,
        "status": item.status,
        "priority": item.priority,
        "assigned_to": item.assigned_to,
        "scheduled_at": item.scheduled_at.isoformat() if item.scheduled_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "downtime_hours": item.downtime_hours,
        "cost": item.cost,
        "created_by": item.created_by,
        "created_at": item.created_at.isoformat(),
    }


# --------------------------------------------------------------------------
# Fuel deliveries
# --------------------------------------------------------------------------
@router.get("/deliveries")
def list_deliveries(
    station_id: str | None = None,
    tank_id: str | None = None,
    delivery_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.has_permission("deliveries", "view"):
        raise HTTPException(status_code=403, detail="Permission denied")
    query = select(TankDelivery)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        query = query.where(TankDelivery.station_id.in_(allowed)) if allowed else query.where(False)
    if station_id:
        query = query.where(TankDelivery.station_id == station_id)
    if tank_id:
        query = query.where(TankDelivery.tank_id == tank_id)
    if delivery_status:
        query = query.where(TankDelivery.status == delivery_status.upper())
    rows = db.scalars(query.order_by(TankDelivery.delivery_date.desc())).all()
    return [_delivery_out(row) for row in rows]


@router.post("/deliveries", status_code=201)
def create_delivery(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("deliveries", "create")),
):
    tank = db.scalar(select(Tank).where(Tank.id == payload.get("tank_id")))
    if tank is None:
        raise HTTPException(status_code=404, detail="Tank not found")
    _ensure_station_scope(db, user, tank.station_id)

    delivered = parse_float(payload.get("delivered_quantity_l"), "delivered_quantity_l", minimum=0.01)
    received = parse_float(payload.get("received_quantity_l", delivered), "received_quantity_l", minimum=0)
    variance = round(received - delivered, 2)
    reference = str(payload.get("reference") or "").strip() or f"DLV-{utcnow():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    if db.scalar(select(TankDelivery).where(TankDelivery.reference == reference)):
        raise HTTPException(status_code=409, detail="Delivery reference already exists")

    delivery_status = str(payload.get("status") or "PENDING").upper()
    if delivery_status not in DELIVERY_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid delivery status")

    if tank.current_volume_l + received > tank.capacity_l * 1.001:
        raise HTTPException(status_code=400, detail="Delivery exceeds available tank capacity")

    item = TankDelivery(
        reference=reference,
        station_id=tank.station_id,
        tank_id=tank.id,
        product_id=tank.product_id,
        supplier=payload.get("supplier"),
        vehicle_plate=payload.get("vehicle_plate"),
        tanker_serial=payload.get("tanker_serial"),
        delivered_quantity_l=delivered,
        received_quantity_l=received,
        variance_l=variance,
        status=delivery_status,
        verified_by=user.user_id if delivery_status == "VERIFIED" else None,
        notes=payload.get("notes"),
    )
    db.add(item)

    if delivery_status == "VERIFIED":
        tank.current_volume_l = round(tank.current_volume_l + received, 2)

    if abs(variance) > max(20.0, delivered * 0.005):
        create_alert(
            db,
            alert_type="DELIVERY_VARIANCE",
            category="FUEL_DISCREPANCY",
            severity="CRITICAL" if abs(variance) > delivered * 0.02 else "HIGH",
            title=f"Delivery variance on {tank.code}",
            description=(
                f"Delivery {reference}: loaded {delivered:.2f} L but received {received:.2f} L "
                f"(variance {variance:+.2f} L)."
            ),
            station_id=tank.station_id,
            entity_type="tank_delivery",
            entity_id=item.id,
            expected_value=delivered,
            actual_value=received,
            discrepancy=variance,
            dedupe_minutes=0,
        )

    db.flush()
    write_audit(db, user, "CREATE_DELIVERY", "TankDelivery", item.id, after=_delivery_out(item), request=request)
    db.commit()
    db.refresh(item)
    return _delivery_out(item)


@router.post("/deliveries/{delivery_id}/verify")
def verify_delivery(
    delivery_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("deliveries", "approve")),
):
    item = db.scalar(select(TankDelivery).where(TankDelivery.id == delivery_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    _ensure_station_scope(db, user, item.station_id)
    if item.status == "VERIFIED":
        raise HTTPException(status_code=409, detail="Delivery is already verified")

    tank = db.scalar(select(Tank).where(Tank.id == item.tank_id))
    received = parse_float(payload.get("received_quantity_l", item.received_quantity_l), "received_quantity_l", minimum=0)
    if tank and tank.current_volume_l + received > tank.capacity_l * 1.001:
        raise HTTPException(status_code=400, detail="Verified delivery exceeds available tank capacity")

    item.received_quantity_l = received
    item.variance_l = round(received - item.delivered_quantity_l, 2)
    item.status = "VERIFIED"
    item.verified_by = user.user_id
    if payload.get("notes"):
        item.notes = payload["notes"]
    if tank:
        tank.current_volume_l = round(tank.current_volume_l + received, 2)

    write_audit(db, user, "VERIFY_DELIVERY", "TankDelivery", item.id, after=_delivery_out(item), request=request)
    db.commit()
    return _delivery_out(item)


# --------------------------------------------------------------------------
# Maintenance
# --------------------------------------------------------------------------
@router.get("/maintenance")
def list_maintenance(
    station_id: str | None = None,
    maintenance_status: str | None = Query(default=None, alias="status"),
    device_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.has_permission("maintenance", "view"):
        raise HTTPException(status_code=403, detail="Permission denied")
    query = select(MaintenanceRecord)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        query = query.where(MaintenanceRecord.station_id.in_(allowed)) if allowed else query.where(False)
    if station_id:
        query = query.where(MaintenanceRecord.station_id == station_id)
    if maintenance_status:
        query = query.where(MaintenanceRecord.status == maintenance_status.upper())
    if device_type:
        query = query.where(MaintenanceRecord.device_type == device_type.upper())
    rows = db.scalars(query.order_by(MaintenanceRecord.created_at.desc())).all()
    return [_maintenance_out(row) for row in rows]


@router.post("/maintenance", status_code=201)
def create_maintenance(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance", "create")),
):
    station = _ensure_station_scope(db, user, payload.get("station_id"))
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    reference = str(payload.get("reference") or "").strip() or f"MNT-{utcnow():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    if db.scalar(select(MaintenanceRecord).where(MaintenanceRecord.reference == reference)):
        raise HTTPException(status_code=409, detail="Maintenance reference already exists")
    item = MaintenanceRecord(
        reference=reference,
        station_id=station.id,
        device_type=str(payload.get("device_type") or "OTHER").upper(),
        device_id=payload.get("device_id"),
        maintenance_type=str(payload.get("maintenance_type") or "PREVENTIVE").upper(),
        title=title,
        description=payload.get("description"),
        status=str(payload.get("status") or "OPEN").upper(),
        priority=str(payload.get("priority") or "MEDIUM").upper(),
        assigned_to=payload.get("assigned_to"),
        scheduled_at=payload.get("scheduled_at"),
        created_by=user.user_id,
    )
    db.add(item)
    db.flush()
    write_audit(db, user, "CREATE_MAINTENANCE", "MaintenanceRecord", item.id, after=_maintenance_out(item), request=request)
    db.commit()
    db.refresh(item)
    return _maintenance_out(item)


@router.patch("/maintenance/{record_id}")
def update_maintenance(
    record_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("maintenance", "edit")),
):
    item = db.scalar(select(MaintenanceRecord).where(MaintenanceRecord.id == record_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    _ensure_station_scope(db, user, item.station_id)
    before = _maintenance_out(item)

    if "status" in payload:
        new_status = str(payload["status"]).upper()
        if new_status not in MAINTENANCE_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid maintenance status")
        item.status = new_status
        if new_status == "COMPLETED" and item.completed_at is None:
            item.completed_at = utcnow()
    for field in ("title", "description", "assigned_to", "priority", "device_type", "device_id", "maintenance_type"):
        if field in payload:
            setattr(item, field, payload[field])
    if "downtime_hours" in payload:
        item.downtime_hours = parse_float(payload["downtime_hours"], "downtime_hours", minimum=0)
    if "cost" in payload:
        item.cost = parse_float(payload["cost"], "cost", minimum=0)
    if "scheduled_at" in payload:
        item.scheduled_at = payload["scheduled_at"]

    db.flush()
    write_audit(db, user, "UPDATE_MAINTENANCE", "MaintenanceRecord", item.id, before=before, after=_maintenance_out(item), request=request)
    db.commit()
    return _maintenance_out(item)


# --------------------------------------------------------------------------
# Tank controllers (read-only registry for ingestion/diagnostics)
# --------------------------------------------------------------------------
@router.get("/tank-controllers")
def list_tank_controllers(
    station_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.has_permission("tank_controllers", "view"):
        raise HTTPException(status_code=403, detail="Permission denied")
    query = select(TankController).join(Tank, TankController.tank_id == Tank.id)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        query = query.where(Tank.station_id.in_(allowed)) if allowed else query.where(False)
    if station_id:
        query = query.where(Tank.station_id == station_id)
    rows = db.scalars(query.order_by(TankController.device_uid)).all()
    return [
        {
            "id": row.id,
            "device_uid": row.device_uid,
            "tank_id": row.tank_id,
            "tank_code": row.tank.code if row.tank else None,
            "station_id": row.tank.station_id if row.tank else None,
            "connection_mode": row.connection_mode,
            "signal_strength_dbm": row.signal_strength_dbm,
            "modbus_address": row.modbus_address,
            "firmware_version": row.firmware_version,
            "is_online": row.is_online,
            "last_heartbeat": row.last_heartbeat.isoformat() if row.last_heartbeat else None,
        }
        for row in rows
    ]
