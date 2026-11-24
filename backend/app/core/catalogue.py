"""Module catalogue, role hierarchy and default permission templates."""

MODULES = [
    ("dashboard", "Dashboard", ["view"]),
    ("geo", "Geography & Coverage", ["view"]),
    ("stations", "Station Management", ["view", "create", "edit", "manage"]),
    ("pump_types", "Pump Type Management", ["view", "create", "edit", "manage"]),
    ("dispensers", "Dispenser Management", ["view", "create", "edit", "manage"]),
    ("nozzles", "Nozzle Management", ["view", "create", "edit", "manage"]),
    ("fcc_devices", "FCC Controller Management", ["view", "create", "edit", "manage"]),
    ("tanks", "Tank Management", ["view", "create", "edit", "manage"]),
    ("tank_controllers", "Tank Controller Management", ["view", "create", "edit", "manage"]),
    ("tank_pump_assignment", "Tank-to-Pump Assignment", ["view", "create", "edit", "manage", "approve"]),
    ("deliveries", "Fuel Deliveries", ["view", "create", "edit", "approve"]),
    ("maintenance", "Maintenance Management", ["view", "create", "edit", "manage"]),
    ("customers", "Customer Management", ["view", "create", "edit", "manage"]),
    ("rfid", "RFID Management", ["view", "create", "edit", "manage", "approve"]),
    ("wallet", "Wallet Management", ["view", "create", "edit", "manage", "approve"]),
    ("fleet", "Fleet Management", ["view", "create", "edit", "manage"]),
    ("vehicles", "Vehicle Management", ["view", "create", "edit", "manage"]),
    ("pos", "POS Terminal Management", ["view", "create", "edit", "manage"]),
    ("payments", "Payment Management", ["view", "create", "edit", "manage", "approve", "export"]),
    ("transactions", "Fuel Transactions", ["view", "create", "export"]),
    ("pulser", "Pulser Monitoring", ["view", "export"]),
    ("dispenser_reconciliation", "Dispenser Reconciliation", ["view", "manage", "approve", "export"]),
    ("tank_reconciliation", "Tank Reconciliation", ["view", "manage", "approve", "export"]),
    ("prices", "Fuel Price Management", ["view", "create", "edit", "approve"]),
    ("alerts", "Alerts and Notifications", ["view", "create", "edit", "manage", "approve"]),
    ("reports", "Reports", ["view", "export"]),
    ("user_activity", "User Activity", ["view", "export"]),
    ("device_config", "Device Configuration", ["view", "create", "edit", "manage", "approve"]),
    ("ingestion", "Hardware Ingestion", ["view", "manage"]),
    ("notifications", "Notification Queue", ["view", "manage"]),
    ("system_settings", "System Settings", ["view", "edit", "manage"]),
    ("users", "User Management", ["view", "create", "edit", "manage"]),
    ("audit", "Audit Log", ["view", "export"]),
]

# Role hierarchy. Order matters only for presentation.
ROLE_DEFINITIONS: dict[str, dict] = {
    "SUPERIOR_ADMIN": {
        "name": "Superior Administrator",
        "level": 100,
        "permissions": "__ALL__",
    },
    "NATIONAL_MANAGER": {
        "name": "National Manager",
        "level": 90,
        "permissions": "__ALL_OPERATIONS__",
    },
    "REGIONAL_MANAGER": {
        "name": "Regional Manager",
        "level": 80,
        "permissions": "__REGIONAL__",
    },
    "STATE_MANAGER": {
        "name": "State Manager",
        "level": 70,
        "permissions": "__STATE__",
    },
    "AREA_MANAGER": {
        "name": "Area (LGA) Manager",
        "level": 60,
        "permissions": "__AREA__",
    },
    "STATION_MANAGER": {
        "name": "Station Manager",
        "level": 50,
        "permissions": "__STATION__",
    },
    "MANAGER": {
        "name": "Manager (legacy)",
        "level": 50,
        "permissions": "__STATION__",
    },
    "SUPERVISOR": {
        "name": "Forecourt Supervisor",
        "level": 40,
        "permissions": "__SUPERVISOR__",
    },
    "ATTENDANT": {
        "name": "Forecourt Attendant",
        "level": 30,
        "permissions": "__ATTENDANT__",
    },
    "AUDITOR": {
        "name": "Auditor",
        "level": 35,
        "permissions": "__AUDITOR__",
    },
    "SPECIAL_CUSTOMER": {
        "name": "Special Customer",
        "level": 10,
        "permissions": ["dashboard:view"],
    },
    "SERVICE_ACCOUNT": {
        "name": "Service Account",
        "level": 5,
        "permissions": [],
    },
}

ROLE_CODES = list(ROLE_DEFINITIONS.keys())

_VIEW_MODULES = [
    "dashboard", "geo", "stations", "pump_types", "dispensers", "nozzles",
    "fcc_devices", "tanks", "tank_controllers", "tank_pump_assignment",
    "deliveries", "maintenance", "transactions", "pulser",
    "dispenser_reconciliation", "tank_reconciliation", "prices", "alerts",
    "reports", "payments", "customers", "wallet", "rfid", "fleet", "vehicles",
    "pos",
]

_STATION_MODULES = [
    "dashboard", "stations", "pump_types", "dispensers", "nozzles",
    "fcc_devices", "tanks", "tank_controllers", "tank_pump_assignment",
    "deliveries", "maintenance", "transactions", "pulser",
    "dispenser_reconciliation", "tank_reconciliation", "prices", "alerts",
    "reports", "payments", "customers", "wallet", "rfid",
]


def _permissions_for(role_code: str) -> list[str]:
    """Expand a role template into explicit module:action keys."""
    if role_code not in ROLE_DEFINITIONS:
        return []
    template = ROLE_DEFINITIONS[role_code]["permissions"]
    if template == "__ALL__":
        return [f"{code}:{action}" for code, _name, actions in MODULES for action in actions]

    allowed = set()
    if isinstance(template, str) and template in {
        "__ALL_OPERATIONS__", "__REGIONAL__", "__STATE__", "__AREA__", "__STATION__"
    }:
        actions = ("view", "create", "edit", "manage", "approve", "export")
        for module in _STATION_MODULES:
            for action in actions:
                allowed.add(f"{module}:{action}")
        if template != "__STATION__":
            allowed.update({"users:view", "audit:view", "user_activity:view"})
        if template in {"__ALL_OPERATIONS__", "__REGIONAL__", "__STATE__", "__AREA__"}:
            allowed.update({"users:create", "users:edit", "users:manage"})
        if template in {"__ALL_OPERATIONS__", "__REGIONAL__"}:
            allowed.update({"ingestion:view", "ingestion:manage", "notifications:view", "notifications:manage"})
        if template == "__ALL_OPERATIONS__":
            allowed.update({"system_settings:view", "system_settings:edit", "device_config:manage"})
    elif template == "__SUPERVISOR__":
        for module in _STATION_MODULES:
            allowed.add(f"{module}:view")
        allowed.update({"transactions:view", "alerts:view", "alerts:edit", "alerts:manage",
                        "maintenance:view", "maintenance:create", "maintenance:edit",
                        "deliveries:view", "deliveries:create", "tank_pump_assignment:view"})
    elif template == "__ATTENDANT__":
        for module in ("dashboard", "transactions", "alerts", "stations", "dispensers", "nozzles", "tanks"):
            allowed.add(f"{module}:view")
        allowed.update({"deliveries:view", "deliveries:create", "transactions:create"})
    elif template == "__AUDITOR__":
        for module in _VIEW_MODULES:
            allowed.add(f"{module}:view")
        allowed.update({"reports:export", "transactions:export", "audit:view", "audit:export",
                        "user_activity:view", "user_activity:export", "pulser:export",
                        "tank_reconciliation:export", "dispenser_reconciliation:export"})
    elif isinstance(template, list):
        allowed.update(template)
    return sorted(allowed)
