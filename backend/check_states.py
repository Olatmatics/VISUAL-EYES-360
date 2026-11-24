from sqlalchemy import func, select

from app.db.base import SessionLocal
from app.models.core import LGA, State

with SessionLocal() as db:
    rows = db.execute(
        select(State.name, func.count(LGA.id)).outerjoin(LGA).group_by(State.id)
    ).all()
    print(f"total states: {len(rows)}")
    for name, cnt in sorted(rows, key=lambda r: r[0]):
        print(f"  {name}: {cnt} LGAs")

    # duplicate-ish state names
    names = [r[0] for r in rows]
    print("\nPossible FCT variants:", [n for n in names if "FCT" in n.upper() or "CAPITAL" in n.upper() or "ABUJA" in n.upper()])
