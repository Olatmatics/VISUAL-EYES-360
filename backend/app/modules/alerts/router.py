from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.deps import allowed_station_ids, get_current_user, require_permission, write_audit
from app.core.mailer import process_pending
from app.db.base import get_db
from app.models.auth import User
from app.models.core import Notification, SystemAlert

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _scoped_alert(db: Session, user: User, alert_id: str) -> SystemAlert:
    alert = db.scalar(select(SystemAlert).where(SystemAlert.id == alert_id))
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    allowed = allowed_station_ids(user)
    if allowed is not None and alert.station_id not in allowed:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.get("")
def list_alerts(
    unresolved_only: bool = False,
    severity: str | None = None,
    status: str | None = None,
    state_id: str | None = None,
    lga_id: str | None = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(SystemAlert).order_by(desc(SystemAlert.created_at))
    allowed = allowed_station_ids(user)
    if allowed is not None:
        stmt = stmt.where(SystemAlert.station_id.in_(allowed))
    if unresolved_only:
        stmt = stmt.where(SystemAlert.is_resolved.is_(False))
    if severity:
        stmt = stmt.where(SystemAlert.severity == severity.upper())
    if status:
        stmt = stmt.where(SystemAlert.status == status.upper())
    if state_id:
        stmt = stmt.where(SystemAlert.state_id == state_id)
    if lga_id:
        stmt = stmt.where(SystemAlert.lga_id == lga_id)

    alerts = db.scalars(stmt.limit(limit)).all()
    return [{
        "id": a.id,
        "alert_ref": a.alert_ref,
        "station_id": a.station_id,
        "station_name": a.station.name if a.station else "System-wide",
        "state_id": a.state_id,
        "lga_id": a.lga_id,
        "category": a.category,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "title": a.title,
        "description": a.description,
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "status": a.status,
        "is_resolved": a.is_resolved,
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "acknowledged_by": a.acknowledged_by,
        "assigned_to": a.assigned_to,
        "resolution_notes": a.resolution_notes,
        "escalated": a.escalated,
        "expected_value": a.expected_value,
        "actual_value": a.actual_value,
        "discrepancy": a.discrepancy,
        "resolved_by": a.resolved_by,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
    } for a in alerts]


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts", "manage")),
):
    alert = _scoped_alert(db, user, alert_id)
    before = {"status": alert.status, "acknowledged_at": alert.acknowledged_at}
    if alert.acknowledged_at is None:
        alert.acknowledged_at = _utcnow()
        alert.acknowledged_by = user.user_id
        if alert.status == "NEW":
            alert.status = "ACKNOWLEDGED"
        write_audit(db, user, "ACKNOWLEDGE_ALERT", "SystemAlert", alert.id, before=before,
                    after={"status": alert.status, "acknowledged_by": user.user_id}, request=request)
        db.commit()
    return {"id": alert.id, "status": alert.status, "acknowledged": True}


@router.post("/{alert_id}/assign")
def assign_alert(
    alert_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts", "manage")),
):
    assigned_to = str(payload.get("assigned_to") or "").strip()
    if not assigned_to:
        raise HTTPException(status_code=400, detail="assigned_to is required")
    alert = _scoped_alert(db, user, alert_id)
    before = {"assigned_to": alert.assigned_to}
    alert.assigned_to = assigned_to
    if alert.status == "NEW":
        alert.status = "ACKNOWLEDGED"
    write_audit(db, user, "ASSIGN_ALERT", "SystemAlert", alert.id, before=before,
                after={"assigned_to": assigned_to}, request=request)
    db.commit()
    return {"id": alert.id, "assigned_to": assigned_to}


@router.post("/{alert_id}/escalate")
def escalate_alert(
    alert_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts", "manage")),
):
    alert = _scoped_alert(db, user, alert_id)
    before = {"escalated": alert.escalated, "status": alert.status}
    alert.escalated = True
    alert.status = "ESCALATED"
    if payload.get("notes"):
        alert.resolution_notes = f"{alert.resolution_notes or ''}\nESCALATION: {payload['notes']}".strip()
    write_audit(db, user, "ESCALATE_ALERT", "SystemAlert", alert.id, before=before,
                after={"escalated": True, "status": "ESCALATED"}, request=request)
    db.commit()
    return {"id": alert.id, "escalated": True, "status": alert.status}


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts", "manage")),
):
    alert = _scoped_alert(db, user, alert_id)
    before = {"status": alert.status, "is_resolved": alert.is_resolved}
    alert.is_resolved = True
    alert.status = "RESOLVED"
    alert.resolved_by = user.user_id
    alert.resolved_at = _utcnow()
    if payload.get("notes"):
        alert.resolution_notes = payload["notes"]
    write_audit(db, user, "RESOLVE_ALERT", "SystemAlert", alert.id, before=before,
                after={"status": "RESOLVED", "is_resolved": True}, request=request)
    db.commit()
    return {"id": alert.id, "is_resolved": True, "status": alert.status}


@router.get("/notifications/list")
def list_notifications(
    status: str | None = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Notification).order_by(desc(Notification.created_at))
    allowed = allowed_station_ids(user)
    if allowed is not None:
        alert_ids = db.scalars(select(SystemAlert.id).where(SystemAlert.station_id.in_(allowed))).all()
        stmt = stmt.where(Notification.alert_id.in_(alert_ids))
    if status:
        stmt = stmt.where(Notification.status == status.upper())
    items = db.scalars(stmt.limit(limit)).all()
    return [{
        "id": n.id, "channel": n.channel, "recipient": n.recipient,
        "subject": n.subject, "status": n.status, "attempts": n.attempts,
        "last_error": n.last_error, "created_at": n.created_at.isoformat() if n.created_at else None,
        "sent_at": n.sent_at.isoformat() if n.sent_at else None,
    } for n in items]


@router.post("/notifications/dispatch")
def dispatch_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts", "manage")),
):
    return process_pending(db, limit=100)


@router.post("/notifications/{notification_id}/retry")
def retry_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts", "manage")),
):
    item = db.scalar(select(Notification).where(Notification.id == notification_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    item.status = "PENDING"
    item.last_error = None
    db.commit()
    return {"id": item.id, "status": "PENDING"}
