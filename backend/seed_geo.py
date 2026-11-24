from sqlalchemy import func, select

from app.db.init_db import init_db
from app.db.base import SessionLocal
from app.models.core import LGA, State

init_db()

with SessionLocal() as db:
    states = db.scalar(select(func.count()).select_from(State)) or 0
    lgas = db.scalar(select(func.count()).select_from(LGA)) or 0
    print(f"STATES: {states} (expect 37)")
    print(f"LGAS:   {lgas} (expect 774)")

    # Spot-check a few states
    for name in ["Lagos", "Kano", "FCT Abuja", "Rivers", "Kaduna"]:
        state = db.scalar(select(State).where(State.name == name))
        if state:
            count = db.scalar(
                select(func.count()).select_from(LGA).where(LGA.state_id == state.id)
            )
            print(f"  {name}: {count} LGAs")
        else:
            print(f"  {name}: NOT FOUND")

print("SEED COMPLETE")
