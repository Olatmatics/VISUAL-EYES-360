"""Alert creation with de-duplication and critical-email queuing."""

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.mailer import queue_email
from app.core.validation import utcnow
from app.models.core import Station, SystemAlert

SEVERITY_LEVELS = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
_SEVERITY_ALIASES = {"WARNING": "MEDIUM", "ERROR": "HIGH", "FATAL": "CRITICAL", "ALERT": "HIGH"}


def normalize_severity(value: str | None) -> str:
    token = (value or "INFO").strip().upper()
    token = _SEVERITY_ALIASES.get(token, token)
    return token if token in SEVERITY_LEVELS else "MEDIUM"


def new_alert_ref(db: Session) -> str:
    for _ in range(10):
        ref = f"ALR-{utcnow():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        if not db.scalar(select(SystemAlert.id).where(SystemAlert.alert_ref == ref)):
            return ref
    return f"ALR-{uuid.uuid4().hex[:12].upper()}"


def create_alert(
    db: Session,
    *,
    alert_type: str,
    title: str,
    description: str | None = None,
    severity: str = "MEDIUM",
    category: str = "SYSTEM",
    station_id: str | None = None,
    device_type: str | None = None,
    device_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    expected_value: float | None = None,
    actual_value: float | None = None,
    discrepancy: float | None = None,
    dedupe_minutes: int = 30,
    notify: bool = True,
) -> SystemAlert:
    """Create (or reuse) an operational alert.

    If an unresolved alert of the same type for the same entity already exists
    inside ``dedupe_minutes``, that alert is returned instead of creating a
    duplicate. This prevents alert storms from repeated hardware messages.
    """
    severity = normalize_severity(severity)

    if dedupe_minutes and entity_id:
        cutoff = utcnow() - timedelta(minutes=dedupe_minutes)
        existing = db.scalar(
            select(SystemAlert)
            .where(
                SystemAlert.alert_type == alert_type,
                SystemAlert.entity_id == entity_id,
                SystemAlert.is_resolved.is_(False),
                SystemAlert.created_at >= cutoff,
            )
            .order_by(SystemAlert.created_at.desc())
        )
        if existing is not None:
            return existing

    station = db.scalar(select(Station).where(Station.id == station_id)) if station_id else None

    alert = SystemAlert(
        alert_ref=new_alert_ref(db),
        station_id=station_id,
        category=category,
        alert_type=alert_type,
        severity=severity,
        title=title[:180],
        description=description,
        state_id=station.state_id if station else None,
        lga_id=station.lga_id if station else None,
        device_type=device_type,
        device_id=device_id,
        entity_type=entity_type,
        entity_id=entity_id,
        expected_value=expected_value,
        actual_value=actual_value,
        discrepancy=discrepancy,
        status="NEW",
        is_resolved=False,
    )
    db.add(alert)
    db.flush()

    if notify and SEVERITY_LEVELS[severity] >= SEVERITY_LEVELS.get(
        normalize_severity(settings.ALERT_EMAIL_MIN_SEVERITY), SEVERITY_LEVELS["CRITICAL"]
    ):
        station_label = station.name if station else "System-wide"
        body = "\n".join(
            [
                f"VISUAL EYES 360 — {severity} OPERATIONAL ALERT",
                "",
                f"Reference: {alert.alert_ref}",
                f"Type: {alert_type}",
                f"Station: {station_label}",
                f"Time: {alert.created_at.isoformat()}",
                "",
                title,
                "",
                description or "",
                "",
                f"Expected: {expected_value}" if expected_value is not None else "",
                f"Actual: {actual_value}" if actual_value is not None else "",
                f"Discrepancy: {discrepancy}" if discrepancy is not None else "",
                "",
                f"Open the console: {settings.PUBLIC_APP_URL}/alerts",
            ]
        )
        for recipient in settings.alert_recipient_list:
            queue_email(
                db,
                recipient=recipient,
                subject=f"[{severity}] {alert_type} — {station_label}",
                body=body,
                alert_id=alert.id,
                dedupe_key=f"alert:{alert.id}:{recipient}",
            )

    return alert
