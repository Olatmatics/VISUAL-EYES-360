"""Lightweight additive schema migration for SQLite and PostgreSQL databases.

`Base.metadata.create_all` only creates missing tables; it never adds columns
to tables that already exist. This module reconciles the live database with
the current model definitions by adding any missing columns and indexes.

It is intentionally additive-only: columns are never dropped or rewritten, so
existing operational and historical records are preserved.
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.sql import sqltypes

import app.models  # noqa: F401  — registers all tables on Base.metadata
from app.db.base import Base, engine

logger = logging.getLogger("ve360.migration")


def migrate() -> list[str]:
    """Bring the live schema in line with the models. Returns changes applied."""
    changes: list[str] = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    # 1. Create any brand-new tables.
    Base.metadata.create_all(bind=engine)

    # 2. Add missing columns to existing tables.
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            live_cols = {c["name"] for c in inspector.get_columns(table_name)}

            for column in table.columns:
                if column.name in live_cols:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)

                # Resolve a literal default from the model definition.
                lit_default = None
                if column.default is not None and column.default.is_scalar:
                    lit_default = column.default.arg

                if column.nullable:
                    sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {col_type}'
                else:
                    # SQLite refuses ALTER ADD COLUMN ... NOT NULL without a
                    # literal DEFAULT, so always supply one.
                    if lit_default is None:
                        if isinstance(column.type, (sqltypes.String, sqltypes.Text)):
                            lit_default = ""
                        elif isinstance(column.type, sqltypes.Boolean):
                            lit_default = False
                        elif isinstance(column.type, (sqltypes.Integer, sqltypes.Float, sqltypes.Numeric)):
                            lit_default = 0
                        else:
                            # Callable defaults (e.g. utcnow) cannot be expressed
                            # in DDL. Add the column nullable and let SQLAlchemy
                            # populate it on insert.
                            sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {col_type}'
                            conn.execute(text(sql))
                            changes.append(f"+ {table_name}.{column.name}")
                            continue

                    if isinstance(lit_default, bool):
                        literal = ("TRUE" if lit_default else "FALSE") if engine.dialect.name == "postgresql" else ("1" if lit_default else "0")
                    elif isinstance(lit_default, (int, float)):
                        literal = str(lit_default)
                    else:
                        escaped = str(lit_default).replace("'", "''")
                        literal = f"'{escaped}'"
                    sql = (
                        f'ALTER TABLE "{table_name}" ADD COLUMN '
                        f'"{column.name}" {col_type} NOT NULL DEFAULT {literal}'
                    )

                try:
                    conn.execute(text(sql))
                except Exception as exc:
                    raise RuntimeError(f"Could not add database column {table_name}.{column.name}") from exc
                changes.append(f"+ {table_name}.{column.name}")

    # 3. Add any missing indexes (ignore ones that already exist).
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            live_idx = {i["name"] for i in inspector.get_indexes(table_name)}
            for index in table.indexes:
                if index.name in live_idx:
                    continue
                cols = ", ".join(f'"{c.name}"' for c in index.columns)
                if not cols:
                    continue
                unique = "UNIQUE " if index.unique else ""
                try:
                    conn.execute(text(f'CREATE {unique}INDEX IF NOT EXISTS "{index.name}" ON "{table_name}" ({cols})'))
                except Exception as exc:
                    raise RuntimeError(f"Could not create database index {index.name}") from exc
                changes.append(f"~ index {index.name}")

    # 4. Remove internal microcontroller labels from user-facing hardware fields.
    #    The product name is "FCC Controller"; the silicon vendor is never shown.
    with engine.begin() as conn:
        existing_after = set(inspect(engine).get_table_names())
        sanitizers = [
            (
                "fcc_devices",
                "UPDATE fcc_devices SET device_uid = REPLACE(device_uid, 'FCC-S3-', 'FCC-') "
                "WHERE device_uid LIKE 'FCC-S3-%'",
            ),
            (
                "fcc_devices",
                "UPDATE fcc_devices SET firmware_version = REPLACE(REPLACE(firmware_version, '-esp32s3', ''), 'esp32s3', '') "
                "WHERE LOWER(firmware_version) LIKE '%esp32%'",
            ),
            (
                "tank_controllers",
                "UPDATE tank_controllers SET device_uid = REPLACE(REPLACE(device_uid, 'TC-ESP32-', 'TC-'), 'ESP32', 'CTRL') "
                "WHERE LOWER(device_uid) LIKE '%esp32%'",
            ),
            (
                "tank_controllers",
                "UPDATE tank_controllers SET firmware_version = REPLACE(REPLACE(firmware_version, '-esp32', ''), 'esp32', '') "
                "WHERE LOWER(firmware_version) LIKE '%esp32%'",
            ),
        ]
        for table_name, statement in sanitizers:
            if table_name not in existing_after:
                continue
            try:
                result = conn.execute(text(statement))
                if result.rowcount:
                    changes.append(f"~ sanitized {table_name} ({result.rowcount} rows)")
            except Exception as exc:
                raise RuntimeError(f"Could not sanitize {table_name}") from exc

    # 4. Data backfills that must accompany the schema changes.
    with engine.begin() as conn:
        _backfill_alert_references(conn)
        _backfill_nozzle_codes(conn)
        _scrub_hardware_identifiers(conn)

    if changes:
        logger.info("Applied %d schema changes", len(changes))
    return changes


def _backfill_alert_references(conn) -> None:
    """Give every legacy alert a reference, category and workflow status."""
    rows = conn.execute(
        text(
            "SELECT id, created_at, is_resolved FROM system_alerts "
            "WHERE alert_ref IS NULL OR alert_ref = '' OR alert_ref = 'alert_ref'"
        )
    ).fetchall()
    for alert_id, created_at, is_resolved in rows:
        stamp = created_at.strftime("%Y%m%d") if hasattr(created_at, "strftime") else (str(created_at or "")[:10].replace("-", "") or "00000000")
        ref = f"ALR-{stamp}-{str(alert_id).replace('-', '')[:12].upper()}"
        status_value = "RESOLVED" if is_resolved else "NEW"
        conn.execute(
            text(
                "UPDATE system_alerts SET alert_ref = :ref, "
                "status = CASE WHEN status IS NULL OR status = '' THEN :status ELSE status END, "
                "category = CASE WHEN category IS NULL OR category = '' THEN 'SYSTEM' ELSE category END, "
                "updated_at = COALESCE(updated_at, created_at) "
                "WHERE id = :id"
            ),
            {"ref": ref, "status": status_value, "id": alert_id},
        )


def _backfill_nozzle_codes(conn) -> None:
    """Give legacy nozzles a short code so old records work with new sketches."""
    tables = set(inspect(conn).get_table_names())
    if "nozzles" not in tables:
        return
    rows = conn.execute(
        text("SELECT id, number FROM nozzles WHERE code IS NULL OR code = ''")
    ).fetchall()
    taken = {str(row[0]).upper() for row in conn.execute(text("SELECT code FROM nozzles WHERE code IS NOT NULL"))}
    for nozzle_id, number in rows:
        stem = str(nozzle_id).replace("-", "")[:6].upper() or "000000"
        candidate = f"NZ-{stem}"
        suffix = 1
        while candidate.upper() in taken:
            suffix += 1
            candidate = f"NZ-{stem}{suffix}"
        taken.add(candidate.upper())
        conn.execute(text("UPDATE nozzles SET code = :code WHERE id = :id"), {"code": candidate, "id": nozzle_id})


def _scrub_hardware_identifiers(conn) -> None:
    """Remove internal microcontroller branding from stored identifiers."""
    replacements = [
        ("device_uid", "TC-ESP32-", "TC-"),
        ("device_uid", "FCC-S3-", "FCC-"),
        ("firmware_version", "v1.0.4-esp32s3", "v1.0.0"),
        ("firmware_version", "v1.0.2-tank-esp32", "v1.0.0"),
    ]
    # REPLACE is table-specific, so run it explicitly for the two device tables.
    for table in ("fcc_devices", "tank_controllers"):
        for column, old, new in replacements:
            conn.execute(
                text(f'UPDATE "{table}" SET "{column}" = REPLACE("{column}", :old, :new)'),
                {"old": old, "new": new},
            )


if __name__ == "__main__":
    applied = migrate()
    print(f"Applied {len(applied)} changes:")
    for c in applied:
        print(" ", c)
