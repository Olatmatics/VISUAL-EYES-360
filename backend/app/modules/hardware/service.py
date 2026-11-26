"""Record the exact JSON that passes between bench hardware and the backend.

The logger uses its own short-lived session so a failed business transaction
cannot hide the evidence of what was sent or received.
"""

import json
import uuid
from typing import Any

from app.core.validation import utcnow
from app.db.base import SessionLocal
from app.models.core import HardwareExchange

MAX_JSON_CHARS = 40000


def _dump(value: Any) -> str | None:
    if value is None:
        return None
    try:
        text = value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True)
    except Exception:
        text = str(value)
    return text[:MAX_JSON_CHARS]


def record_exchange(
    *,
    direction: str,
    endpoint: str,
    method: str = "POST",
    device_uid: str | None = None,
    request: Any = None,
    response: Any = None,
    status_code: int | None = 200,
) -> None:
    """Write one IN (hardware→software) or OUT (software→hardware) exchange."""
    with SessionLocal() as db:
        db.add(HardwareExchange(
            id=str(uuid.uuid4()),
            direction="OUT" if str(direction).upper() == "OUT" else "IN",
            device_uid=device_uid or None,
            endpoint=endpoint[:180],
            method=method.upper()[:10],
            status_code=status_code,
            request_json=_dump(request),
            response_json=_dump(response),
            created_at=utcnow(),
        ))
        db.commit()
