import sqlite3

path = "visual_eyes_360_v2.db"
c = sqlite3.connect(path)
print("before:", c.execute("PRAGMA integrity_check").fetchall()[:6])
c.execute("REINDEX")
c.commit()
print("after reindex:", c.execute("PRAGMA integrity_check").fetchall()[:6])

rows = c.execute("SELECT id, created_at, is_resolved FROM system_alerts").fetchall()
for alert_id, created_at, is_resolved in rows:
    stamp = (created_at or "")[:10].replace("-", "") or "00000000"
    ref = f"ALR-{stamp}-{str(alert_id).replace('-', '')[:12].upper()}"
    c.execute(
        "UPDATE system_alerts SET alert_ref=?, "
        "status=CASE WHEN status IS NULL OR status='' THEN ? ELSE status END, "
        "category=CASE WHEN category IS NULL OR category='' THEN 'SYSTEM' ELSE category END, "
        "updated_at=COALESCE(updated_at, created_at) WHERE id=?",
        (ref, "RESOLVED" if is_resolved else "NEW", alert_id),
    )
c.commit()
c.execute("VACUUM")
c.commit()
print("final integrity:", c.execute("PRAGMA integrity_check").fetchall()[:6])
print("alerts:", c.execute("SELECT id, alert_ref, status FROM system_alerts").fetchall())
