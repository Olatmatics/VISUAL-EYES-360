import sqlite3

c = sqlite3.connect("file:visual_eyes_360_v2.db?mode=ro", uri=True)
print("sqlite lib:", sqlite3.sqlite_version)
queries = [
    "SELECT COUNT(*) FROM system_alerts",
    "SELECT COUNT(alert_ref) FROM system_alerts",
    'SELECT COUNT("alert_ref") FROM system_alerts',
    "SELECT COUNT(system_alerts.alert_ref) FROM system_alerts",
    "SELECT COUNT(*) FROM system_alerts WHERE alert_ref IS NULL",
    "SELECT SUM(CASE WHEN alert_ref IS NULL THEN 1 ELSE 0 END) FROM system_alerts",
    "SELECT COUNT(1) FROM system_alerts WHERE alert_ref IS NOT NULL",
    "SELECT typeof(alert_ref), COUNT(*) FROM system_alerts GROUP BY typeof(alert_ref)",
    "PRAGMA integrity_check",
]
for q in queries:
    try:
        print(q, "=>", c.execute(q).fetchall())
    except Exception as exc:
        print(q, "ERR", exc)
