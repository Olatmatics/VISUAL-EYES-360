"""Persistent system settings (replaces the previous local-only Settings page)."""

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_permission, write_audit
from app.core.validation import utcnow
from app.db.base import get_db
from app.models.auth import User
from app.models.core import SystemSetting

router = APIRouter(prefix="/api/v1/system-settings", tags=["settings"])

DEFAULTS = {
    "network_priority": "WIFI_PRIMARY",
    "carrier_preset": "MTN",
    "apn": "web.gprs.mtnnigeria.net",
    "pump_discrepancy_threshold_l": 0.49,
}


@router.get("")
def get_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("system_settings", "view")),
):
    result = dict(DEFAULTS)
    for row in db.scalars(select(SystemSetting)).all():
        try:
            result[row.key] = json.loads(row.value)
        except (TypeError, ValueError):
            result[row.key] = row.value
    return result


@router.put("")
def put_settings(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("system_settings", "manage")),
):
    changed = {}
    for key, value in payload.items():
        if key not in DEFAULTS:
            continue
        encoded = json.dumps(value)
        row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if row is None:
            row = SystemSetting(key=key, value=encoded, updated_by=user.user_id)
            db.add(row)
        else:
            row.value = encoded
            row.updated_by = user.user_id
            row.updated_at = utcnow()
        changed[key] = value
    write_audit(db, user, "UPDATE_SYSTEM_SETTINGS", "SystemSetting", "settings",
                after=changed, request=request)
    db.commit()
    return get_settings(db, user)
