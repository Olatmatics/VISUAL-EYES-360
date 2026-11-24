from sqlalchemy import select

from app.core.catalogue import MODULES, ROLE_CODES, ROLE_DEFINITIONS, _permissions_for
from app.db.base import Base, SessionLocal, engine
from app.db.nigeria_geo import NIGERIA_STATES
from app.models.auth import Permission, Role, role_permissions
from app.models.core import FuelProduct, LGA, PumpType, State

DEFAULT_PUMP_TYPES = [
    ("WAYNE", "Wayne", "Wayne / Dresser electronic dispensers (Dart, iGEM)"),
    ("GILBARCO", "Gilbarco", "Gilbarco Veeder-Root (Encore, TwoWire)"),
    ("TATSUNO", "Tatsuno", "Tatsuno / Benc dispensers"),
    ("TOKHEIM", "Tokheim", "Tokheim / ProGauge dispensers"),
    ("BENNETT", "Bennett", "Bennett pump and dispenser systems"),
    ("OTHER", "Other", "Any other manufacturer or custom pump type"),
]


def seed_nigeria_geo(db) -> None:
    """Load all 37 states and 774 LGAs, preserving existing rows."""
    for state_name, lga_names in NIGERIA_STATES:
        state = db.scalar(select(State).where(State.name == state_name))
        if state is None:
            state = State(name=state_name)
            db.add(state)
            db.flush()

        for lga_name in lga_names:
            exists = db.scalar(
                select(LGA).where(LGA.state_id == state.id, LGA.name == lga_name)
            )
            if exists is None:
                db.add(LGA(state_id=state.id, name=lga_name))
        db.flush()


def _seed_pump_types(db) -> None:
    for code, name, description in DEFAULT_PUMP_TYPES:
        if db.scalar(select(PumpType).where(PumpType.code == code)) is None:
            db.add(PumpType(code=code, name=name, description=description))
    db.flush()


def _seed_roles_and_permissions(db) -> None:
    roles: dict[str, Role] = {}
    for code in ROLE_CODES:
        role = db.scalar(select(Role).where(Role.code == code))
        if role is None:
            role = Role(code=code, name=ROLE_DEFINITIONS[code]["name"])
            db.add(role)
            db.flush()
        roles[code] = role

    for module_code, _name, actions in MODULES:
        for action in actions:
            exists = db.scalar(
                select(Permission).where(
                    Permission.module_code == module_code, Permission.action_code == action
                )
            )
            if exists is None:
                db.add(Permission(module_code=module_code, action_code=action))
    db.flush()

    permissions = {p.key: p for p in db.scalars(select(Permission)).all()}
    existing_pairs = set(db.execute(select(role_permissions)).all())
    for code, role in roles.items():
        for key in _permissions_for(code):
            permission = permissions.get(key)
            if permission is None:
                continue
            if (role.id, permission.id) in existing_pairs:
                continue
            db.execute(
                role_permissions.insert().values(role_id=role.id, permission_id=permission.id)
            )
            existing_pairs.add((role.id, permission.id))


def init_db() -> None:
    # Reconcile additive schema changes before seeding or using live databases.
    from app.db.migration import migrate
    migrate()
    Base.metadata.create_all(bind=engine)

    # On PostgreSQL this creates the current month's telemetry partitions
    # before any device can write. No-op on SQLite.
    from app.db.partitioning import ensure_partitions

    with engine.begin() as conn:
        ensure_partitions(conn)

    with SessionLocal() as db:
        _seed_roles_and_permissions(db)
        _seed_pump_types(db)

        for code, name in [
            ("PMS", "Premium Motor Spirit"),
            ("AGO", "Automotive Gas Oil"),
            ("DPK", "Dual Purpose Kerosene"),
        ]:
            if db.scalar(select(FuelProduct).where(FuelProduct.code == code)) is None:
                db.add(FuelProduct(code=code, name=name))

        seed_nigeria_geo(db)
        db.commit()


if __name__ == "__main__":
    # One-shot startup command for the `migrate` service. Safe to re-run:
    # every seed is idempotent and the additive migration preserves history.
    init_db()
    print("Database schema and seed data are up to date.")
