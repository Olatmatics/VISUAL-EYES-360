from sqlalchemy import select
from app.core.catalogue import MODULES, ROLE_CODES, SAMPLE_LGAS, SAMPLE_STATES
from app.db.base import Base, SessionLocal, engine
from app.models.auth import Permission, Role, role_permissions
from app.models.core import FuelProduct, LGA, State


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        roles: dict[str, Role] = {}
        for code in ROLE_CODES:
            role = db.scalar(select(Role).where(Role.code == code))
            if role is None:
                role = Role(code=code, name=code.replace("_", " ").title())
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

        admin = roles["SUPERIOR_ADMIN"]
        all_permissions = db.scalars(select(Permission)).all()
        existing_pairs = set(db.execute(select(role_permissions)).all())
        for permission in all_permissions:
            if (admin.id, permission.id) not in existing_pairs:
                db.execute(
                    role_permissions.insert().values(role_id=admin.id, permission_id=permission.id)
                )

        for code, name in [("PMS", "Premium Motor Spirit"), ("AGO", "Automotive Gas Oil"), ("DPK", "Dual Purpose Kerosene")]:
            if db.scalar(select(FuelProduct).where(FuelProduct.code == code)) is None:
                db.add(FuelProduct(code=code, name=name))

        for state_name in SAMPLE_STATES:
            if db.scalar(select(State).where(State.name == state_name)) is None:
                db.add(State(name=state_name))

        db.flush()
        for state_name, lga_names in SAMPLE_LGAS.items():
            state = db.scalar(select(State).where(State.name == state_name))
            if state is None:
                continue
            for lga_name in lga_names:
                if db.scalar(select(LGA).where(LGA.state_id == state.id, LGA.name == lga_name)) is None:
                    db.add(LGA(state_id=state.id, name=lga_name))

        db.commit()
