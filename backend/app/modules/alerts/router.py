from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.core.deps import allowed_station_ids, get_current_user, require_permission
from app.db.base import get_db
from app.models.auth import User
from app.models.core import SystemAlert

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    unresolved_only: bool = False,
    severity: str | None = None,
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

    alerts = db.scalars(stmt.limit(limit)).all()
    res = []
    for a in alerts:
        res.append({
            "id": a.id,
            "station_id": a.station_id,
            "station_name": a.station.name if a.station else "System-wide",
            "alert_type": a.alert_type,
            "severity": a.severity,
            "title": a.title,
            "description": a.description,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "is_resolved": a.is_resolved,
            "resolved_by": a.resolved_by,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        })
    return res


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts", "manage")),
):
    alert = db.scalar(select(SystemAlert).where(SystemAlert.id == alert_id))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_resolved = True
    alert.resolved_by = user.user_id
    alert.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"id": alert.id, "is_resolved": True}
