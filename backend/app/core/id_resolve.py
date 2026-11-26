"""Resolve hardware identifiers that may be a database UUID or a short code.

The admin Hardware ID Generator writes short, copyable codes (for example
``NZ-7K3M2Q``) into the ESP32 sketches. Older sketches still send the long UUID.
Both must keep working, so every device-facing lookup goes through here.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def resolve_by_id_or_code(db: Session, model, value, code_field: str = "code"):
    """Return the row whose UUID or short code matches ``value``.

    Returns ``None`` when the value is empty or no row matches. Lookup is
    case-insensitive for codes, because codes are typed by humans.
    """
    if value is None:
        return None
    key = str(value).strip()
    if not key:
        return None

    row = db.scalar(select(model).where(model.id == key))
    if row is not None:
        return row

    column = getattr(model, code_field, None)
    if column is None:
        return None
    return db.scalar(select(model).where(func.upper(column) == key.upper()))
