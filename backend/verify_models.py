import app.models  # noqa: F401
from app.db.base import Base

WANT = [
    "pump_types", "tank_calibrations", "tank_sensors", "tank_deliveries",
    "maintenance_records", "pump_reconciliations", "device_events",
    "notifications", "stations", "dispensers", "fcc_devices", "tanks",
    "system_alerts", "nozzles", "fuel_transactions",
]

ts = set(Base.metadata.tables)
missing = [w for w in WANT if w not in ts]
print("total tables:", len(ts))
print("missing:", missing if missing else "NONE - all present")

# Verify Station columns
st = Base.metadata.tables["stations"]
need_st = ["company_name", "manager_name", "manager_phone", "manager_email",
           "supervisor_name", "supervisor_phone", "supervisor_email", "status"]
print("station missing cols:", [c for c in need_st if c not in st.columns] or "NONE")

# Verify Dispenser columns
dp = Base.metadata.tables["dispensers"]
need_dp = ["name", "pump_type_id", "manufacturer", "custom_manufacturer",
           "nozzle_config", "nozzle_count", "installation_date", "communication_status"]
print("dispenser missing cols:", [c for c in need_dp if c not in dp.columns] or "NONE")

# Verify FCC columns
fc = Base.metadata.tables["fcc_devices"]
need_fc = ["name", "serial_number", "hardware_version", "station_id",
           "dispenser_id", "pos_terminal_id", "protocol", "ip_address",
           "mac_address", "sim_info", "temperature_c", "power_status"]
print("fcc missing cols:", [c for c in need_fc if c not in fc.columns] or "NONE")

# Verify Tank columns
tk = Base.metadata.tables["tanks"]
need_tk = ["name", "serial_number", "location_type", "probe_id",
           "probe_comm_type", "has_tamper_switch", "has_water_detection",
           "installation_status"]
print("tank missing cols:", [c for c in need_tk if c not in tk.columns] or "NONE")

# Verify SystemAlert columns
al = Base.metadata.tables["system_alerts"]
need_al = ["alert_ref", "category", "severity", "state_id", "lga_id",
           "device_type", "device_id", "status", "assigned_to",
           "resolution_notes", "acknowledged_at", "escalated"]
print("alert missing cols:", [c for c in need_al if c not in al.columns] or "NONE")

print("\nVERIFY COMPLETE")
