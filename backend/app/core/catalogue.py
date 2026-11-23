MODULES = [
    ("dashboard", "Dashboard", ["view"]),
    ("stations", "Station Management", ["view", "create", "edit", "manage"]),
    ("dispensers", "Dispenser Management", ["view", "create", "edit", "manage"]),
    ("nozzles", "Nozzle Management", ["view", "create", "edit", "manage"]),
    ("fcc_devices", "FCC Device Management", ["view", "create", "edit", "manage"]),
    ("tanks", "Tank Management", ["view", "create", "edit", "manage"]),
    ("tank_controllers", "Tank Controller Management", ["view", "create", "edit", "manage"]),
    ("tank_pump_assignment", "Tank-to-Pump Assignment", ["view", "create", "edit", "manage", "approve"]),
    ("customers", "Customer Management", ["view", "create", "edit", "manage"]),
    ("rfid", "RFID Management", ["view", "create", "edit", "manage", "approve"]),
    ("wallet", "Wallet Management", ["view", "create", "edit", "manage", "approve"]),
    ("fleet", "Fleet Management", ["view", "create", "edit", "manage"]),
    ("vehicles", "Vehicle Management", ["view", "create", "edit", "manage"]),
    ("pos", "POS Terminal Management", ["view", "create", "edit", "manage"]),
    ("payments", "Payment Management", ["view", "create", "edit", "manage", "approve", "export"]),
    ("transactions", "Fuel Transactions", ["view", "export"]),
    ("pulser", "Pulser Monitoring", ["view", "export"]),
    ("dispenser_reconciliation", "Dispenser Reconciliation", ["view", "manage", "approve", "export"]),
    ("tank_reconciliation", "Tank Reconciliation", ["view", "manage", "approve", "export"]),
    ("prices", "Fuel Price Management", ["view", "create", "edit", "approve"]),
    ("alerts", "Alerts and Notifications", ["view", "create", "edit", "manage", "approve"]),
    ("reports", "Reports", ["view", "export"]),
    ("maintenance", "Maintenance Management", ["view", "create", "edit", "manage"]),
    ("user_activity", "User Activity", ["view", "export"]),
    ("device_config", "Device Configuration", ["view", "create", "edit", "manage", "approve"]),
    ("system_settings", "System Settings", ["view", "edit", "manage"]),
    ("users", "User Management", ["view", "create", "edit", "manage"]),
    ("audit", "Audit Log", ["view", "export"]),
]

ROLE_CODES = ["SUPERIOR_ADMIN", "MANAGER", "SPECIAL_CUSTOMER", "SERVICE_ACCOUNT"]

SAMPLE_STATES = [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno",
    "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "FCT Abuja", "Gombe",
    "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos",
    "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto",
    "Taraba", "Yobe", "Zamfara",
]

SAMPLE_LGAS = {
    "FCT Abuja": ["Abaji", "Abuja Municipal", "Bwari", "Gwagwalada", "Kuje", "Kwali"],
    "Lagos": ["Alimosho", "Ikeja", "Lagos Island", "Lagos Mainland", "Surulere", "Eti-Osa"],
    "Kaduna": ["Kaduna North", "Kaduna South", "Zaria", "Chikun", "Igabi"],
    "Rivers": ["Port Harcourt", "Obio/Akpor", "Bonny", "Eleme"],
    "Ogun": ["Abeokuta North", "Abeokuta South", "Ado-Odo/Ota", "Ifo"],
}
