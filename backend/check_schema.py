import sqlite3

conn = sqlite3.connect("visual_eyes_360_v2.db")
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print("LIVE TABLES:", len(tables))

for t in ["stations", "dispensers", "fcc_devices", "tanks", "system_alerts"]:
    if t not in tables:
        print(f"\n{t}: MISSING TABLE")
        continue
    cur.execute(f'PRAGMA table_info("{t}")')
    cols = [r[1] for r in cur.fetchall()]
    print(f"\n{t} ({len(cols)} cols): {', '.join(cols)}")

new_tables = ["pump_types", "tank_calibrations", "tank_sensors", "tank_deliveries",
              "maintenance_records", "pump_reconciliations", "device_events", "notifications"]
print("\nNEW TABLES PRESENT:", [t for t in new_tables if t in tables])
print("NEW TABLES MISSING:", [t for t in new_tables if t not in tables])
conn.close()
