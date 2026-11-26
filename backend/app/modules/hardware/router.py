"""Read-only API for the bench hardware JSON monitor."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.base import get_db
from app.models.core import HardwareExchange

router = APIRouter(prefix="/api/v1/hardware", tags=["hardware"])


@router.get("/exchanges")
def list_exchanges(
    limit: int = 100,
    device_uid: str | None = None,
    direction: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_permission("hardware", "view")),
):
    """Return the newest hardware ↔ software JSON exchanges first."""
    if direction and direction.upper() not in {"IN", "OUT"}:
        raise HTTPException(400, "direction must be IN or OUT")

    query = select(HardwareExchange)
    if device_uid:
        query = query.where(HardwareExchange.device_uid == device_uid)
    if direction:
        query = query.where(HardwareExchange.direction == direction.upper())
    rows = db.scalars(
        query.order_by(HardwareExchange.created_at.desc()).limit(max(1, min(limit, 500)))
    ).all()

    return [{
        "id": row.id,
        "direction": row.direction,
        "device_uid": row.device_uid,
        "endpoint": row.endpoint,
        "method": row.method,
        "status_code": row.status_code,
        "request_json": row.request_json,
        "response_json": row.response_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    } for row in rows]
