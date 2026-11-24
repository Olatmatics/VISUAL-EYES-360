"""CSV / Excel export endpoints backed by real database records."""

from datetime import datetime, time
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.core.deps import allowed_station_ids, get_current_user, require_permission
from app.core.exports import csv_bytes, xlsx_bytes
from app.db.base import get_db
from app.models.auth import AuditLog, User
from app.models.core import (
    Dispenser,
    FCCDevice,
    FuelTransaction,
    MaintenanceRecord,
    Nozzle,
    PumpReconciliation,
    Station,
    SystemAlert,
    Tank,
    TankDelivery,
    TankReconciliation,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/reports/export", tags=["reports"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


def _dataset(name: str):
    return DATASETS.get(name)


# name -> (permission module, model, station column, date column, headers, row builder)
DATASETS: dict[str, tuple[str, object, str | None, str | None, list[str], Callable]] = {
    "stations": (
        "stations", Station, "id", "registered_at",
        ["ID", "Code", "Name", "Company", "State ID", "LGA ID", "City", "Address", "Status", "Registered At"],
        lambda s: [s.id, s.code, s.name, s.company_name, s.state_id, s.lga_id, s.city, s.address, s.status, _iso(s.registered_at)],
    ),
    "tanks": (
        "tanks", Tank, "station_id", "created_at",
        ["ID", "Code", "Name", "Station ID", "Capacity L", "Current Volume L", "Product ID", "Status", "Created At"],
        lambda t: [t.id, t.code, t.name, t.station_id, t.capacity_l, t.current_volume_l, t.product_id, t.status, _iso(t.created_at)],
    ),
    "dispensers": (
        "dispensers", Dispenser, "station_id", "created_at",
        ["ID", "Code", "Name", "Station ID", "Manufacturer", "Pump Type ID", "Nozzle Config", "Status", "Created At"],
        lambda d: [d.id, d.code, d.name, d.station_id, d.manufacturer, d.pump_type_id, d.nozzle_config, d.status, _iso(d.created_at)],
    ),
    "nozzles": (
        "dispensers", Nozzle, None, "created_at",
        ["ID", "Dispenser ID", "Number", "Name", "Product ID", "Tank ID", "Price", "Status", "Totalizer L"],
        lambda n: [n.id, n.dispenser_id, n.number, n.name, n.product_id, n.tank_id, n.price, n.status, n.totalizer_l],
    ),
    "fcc-controllers": (
        "fcc_devices", FCCDevice, "station_id", "created_at",
        ["ID", "Device UID", "Name", "Station ID", "Dispenser ID", "Nozzle ID", "Firmware", "Online", "Status", "Last Heartbeat"],
        lambda f: [f.id, f.device_uid, f.name, f.station_id, f.dispenser_id, f.nozzle_id, f.firmware_version, f.is_online, f.status, _iso(f.last_heartbeat)],
    ),
    "transactions": (
        "transactions", FuelTransaction, "station_id", "started_at",
        ["Ref", "Station ID", "Nozzle ID", "Channel", "CPU Volume L", "Pulser Volume L", "Variance L", "Amount", "Status", "Started At"],
        lambda t: [t.transaction_ref, t.station_id, t.nozzle_id, t.payment_channel, t.dispenser_cpu_volume, t.independent_pulser_volume, t.volume_difference, t.total_amount_billed, t.status, _iso(t.started_at)],
    ),
    "alerts": (
        "alerts", SystemAlert, "station_id", "created_at",
        ["Ref", "Station ID", "Type", "Category", "Severity", "Status", "Title", "Expected", "Actual", "Discrepancy", "Created At"],
        lambda a: [a.alert_ref, a.station_id, a.alert_type, a.category, a.severity, a.status, a.title, a.expected_value, a.actual_value, a.discrepancy, _iso(a.created_at)],
    ),
    "tank-reconciliation": (
        "tank_reconciliation", TankReconciliation, "station_id", "recorded_at",
        ["ID", "Station ID", "Tank ID", "Date", "Opening L", "Deliveries L", "Expected Closing L", "Actual Closing L", "Variance L", "Variance %", "Status"],
        lambda r: [r.id, r.station_id, r.tank_id, r.shift_date, r.opening_stock_l, r.deliveries_l, r.expected_closing_stock_l, r.actual_atg_closing_stock_l, r.variance_l, r.variance_percentage, r.status],
    ),
    "pump-reconciliation": (
        "pulser", PumpReconciliation, "station_id", "recorded_at",
        ["ID", "Station ID", "Dispenser ID", "Nozzle ID", "Date", "POS L", "FCC L", "CPU L", "Pulser L", "Variance L", "Status"],
        lambda r: [r.id, r.station_id, r.dispenser_id, r.nozzle_id, r.shift_date, r.pos_volume_l, r.fcc_volume_l, r.cpu_volume_l, r.pulser_volume_l, r.variance_l, r.status],
    ),
    "deliveries": (
        "deliveries", TankDelivery, "station_id", "delivery_date",
        ["Ref", "Station ID", "Tank ID", "Supplier", "Vehicle", "Expected L", "Received L", "Variance L", "Status", "Date"],
        lambda d: [d.reference, d.station_id, d.tank_id, d.supplier, d.vehicle_plate, d.delivered_quantity_l, d.received_quantity_l, d.variance_l, d.status, _iso(d.delivery_date)],
    ),
    "maintenance": (
        "maintenance", MaintenanceRecord, "station_id", "created_at",
        ["Ref", "Station ID", "Device Type", "Device ID", "Type", "Title", "Status", "Priority", "Downtime Hrs", "Created At"],
        lambda m: [m.reference, m.station_id, m.device_type, m.device_id, m.maintenance_type, m.title, m.status, m.priority, m.downtime_hours, _iso(m.created_at)],
    ),
    "audit": (
        "audit", AuditLog, None, "created_at",
        ["ID", "Actor", "Action", "Entity", "Entity ID", "Created At"],
        lambda a: [a.id, a.actor_user_id, a.action, a.entity_type, a.entity_id, _iso(a.created_at)],
    ),
}


@router.get("/datasets")
def list_datasets(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports", "view")),
):
    return [
        {"name": name, "module": spec[0], "headers": spec[4]}
        for name, spec in sorted(DATASETS.items())
    ]


@router.get("/{dataset}")
def export_dataset(
    dataset: str,
    fmt: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    station_id: str | None = None,
    state_id: str | None = None,
    lga_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(default=10000, le=100000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    spec = _dataset(dataset)
    if spec is None:
        raise HTTPException(status_code=404, detail="Unknown dataset")
    module, model, station_column, date_column, headers, build_row = spec
    if not user.has_permission(module, "export") and not user.is_super_admin:
        raise HTTPException(status_code=403, detail=f"Missing {module}:export permission")

    stmt = select(model)
    allowed = allowed_station_ids(user)
    if allowed is not None and station_column:
        stmt = stmt.where(getattr(model, station_column).in_(allowed))
    if station_id and station_column:
        stmt = stmt.where(getattr(model, station_column) == station_id)
    if station_column and state_id:
        station_ids = db.scalars(select(Station.id).where(Station.state_id == state_id)).all()
        stmt = stmt.where(getattr(model, station_column).in_(station_ids))
    if station_column and lga_id:
        station_ids = db.scalars(select(Station.id).where(Station.lga_id == lga_id)).all()
        stmt = stmt.where(getattr(model, station_column).in_(station_ids))
    if date_column:
        if date_from:
            start = datetime.fromisoformat(date_from)
            stmt = stmt.where(getattr(model, date_column) >= start)
        if date_to:
            end = datetime.combine(datetime.fromisoformat(date_to).date(), time.max)
            stmt = stmt.where(getattr(model, date_column) <= end)

    rows = [build_row(item) for item in db.scalars(stmt.limit(limit)).all()]

    if fmt == "csv":
        content = csv_bytes(headers, rows)
        media = "text/csv; charset=utf-8"
        suffix = "csv"
    else:
        content = xlsx_bytes([(dataset.replace("-", " ")[:31], headers, rows)])
        media = XLSX_MIME
        suffix = "xlsx"
    filename = f"ve360-{dataset}-{datetime.utcnow():%Y%m%d-%H%M%S}.{suffix}"
    return Response(content=content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
