"""Scheduled maintenance jobs run by the worker service.

Every job is idempotent and safe to re-run. All database work uses short-lived
sessions so a failed job cannot leave a transaction open.
"""

import logging
from datetime import timedelta

from sqlalchemy import delete, or_, select

from app.core.config import settings
from app.core.mailer import process_pending
from app.core.validation import utcnow
from app.db.base import SessionLocal, engine
from app.db.partitioning import drop_old_partitions, ensure_partitions
from app.models.auth import LoginSession, PasswordResetToken, RefreshToken
from app.models.core import FCCDevice, FuelTransaction, TankController
from app.modules.alerts.service import create_alert

logger = logging.getLogger("ve360.worker")


def check_offline_devices() -> dict:
    """Alert once per device that has stopped heartbeating."""
    cutoff = utcnow() - timedelta(minutes=settings.DEVICE_OFFLINE_AFTER_MINUTES)
    result = {"fcc_offline": 0, "tank_offline": 0}
    with SessionLocal() as db:
        fcc_devices = db.scalars(
            select(FCCDevice).where(
                FCCDevice.status == "ACTIVE",
                or_(FCCDevice.last_heartbeat.is_(None), FCCDevice.last_heartbeat < cutoff),
            )
        ).all()
        for device in fcc_devices:
            # Ticker truth: a device with no recent heartbeat is not online.
            device.is_online = False
            create_alert(
                db,
                alert_type="FCC_OFFLINE",
                category="DEVICE",
                severity="HIGH",
                title=f"FCC controller offline: {device.device_uid}",
                description=(
                    f"No heartbeat received for more than "
                    f"{settings.DEVICE_OFFLINE_AFTER_MINUTES} minutes."
                ),
                station_id=device.station_id,
                device_type="FCC_CONTROLLER",
                device_id=device.id,
                entity_type="fcc_device",
                entity_id=device.id,
                dedupe_minutes=180,
                notify=False,
            )
            result["fcc_offline"] += 1

        tank_devices = db.scalars(
            select(TankController).where(
                or_(TankController.last_heartbeat.is_(None), TankController.last_heartbeat < cutoff)
            )
        ).all()
        for device in tank_devices:
            device.is_online = False
            tank = device.tank
            create_alert(
                db,
                alert_type="TANK_CONTROLLER_OFFLINE",
                category="DEVICE",
                severity="HIGH",
                title=f"Tank controller offline: {device.device_uid}",
                description=(
                    f"No heartbeat received for more than "
                    f"{settings.DEVICE_OFFLINE_AFTER_MINUTES} minutes."
                ),
                station_id=tank.station_id if tank else None,
                device_type="TANK_CONTROLLER",
                device_id=device.id,
                entity_type="tank_controller",
                entity_id=device.id,
                dedupe_minutes=180,
                notify=False,
            )
            result["tank_offline"] += 1
        db.commit()
    return result


def reconcile_discrepancies() -> dict:
    """Turn CPU/pulser mismatches into review items and alerts."""
    result = {"flagged": 0}
    with SessionLocal() as db:
        transactions = db.scalars(
            select(FuelTransaction)
            .where(
                FuelTransaction.discrepancy_alert.is_(True),
                FuelTransaction.investigation_status == "NORMAL",
            )
            .limit(200)
        ).all()
        for tx in transactions:
            create_alert(
                db,
                alert_type="PULSER_DISCREPANCY",
                category="FUEL_DISCREPANCY",
                severity="HIGH",
                title=f"CPU/pulser mismatch on transaction {tx.transaction_ref}",
                description=(
                    f"CPU measured {tx.dispenser_cpu_volume:.2f} L, "
                    f"independent pulser measured {tx.independent_pulser_volume:.2f} L."
                ),
                station_id=tx.station_id,
                entity_type="fuel_transaction",
                entity_id=tx.id,
                expected_value=tx.dispenser_cpu_volume,
                actual_value=tx.independent_pulser_volume,
                discrepancy=tx.volume_difference,
                dedupe_minutes=1440,
            )
            tx.investigation_status = "UNDER_REVIEW"
            result["flagged"] += 1
        db.commit()
    return result


def process_notifications() -> dict:
    with SessionLocal() as db:
        return process_pending(db, limit=100)


def cleanup_expired_tokens() -> dict:
    now = utcnow()
    result = {}
    with SessionLocal() as db:
        for name, model in (
            ("refresh_tokens", RefreshToken),
            ("password_reset_tokens", PasswordResetToken),
            ("login_sessions", LoginSession),
        ):
            outcome = db.execute(delete(model).where(model.expires_at < now))
            result[name] = outcome.rowcount or 0
        db.commit()
    return result


def partition_maintenance() -> dict:
    with engine.begin() as conn:
        created = ensure_partitions(conn)
        dropped = drop_old_partitions(conn, settings.TELEMETRY_RETENTION_MONTHS)
    return {"partitions_checked": len(created), "partitions_dropped": len(dropped)}
