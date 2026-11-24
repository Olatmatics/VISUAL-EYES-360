"""Reconcile duplicate FCT state rows using explicit SQL.

The original sample seed created a state named "FCT Abuja" while the official
dataset used "Federal Capital Territory". This merges them into one canonical
state. Raw SQL is used deliberately: ORM cascade would null out child FKs
when the duplicate parent row is deleted.
"""

from sqlalchemy import text

from app.db.base import SessionLocal

CANONICAL = "FCT Abuja"
LGA_ALIASES = {"Abuja Municipal": "Abuja Municipal Area Council"}

with SessionLocal() as db:
    rows = db.execute(
        text("SELECT id, name FROM states WHERE name IN (:a, :b)"),
        {"a": CANONICAL, "b": "Federal Capital Territory"},
    ).fetchall()
    print("FCT rows found:", [(r[0], r[1]) for r in rows])

    if len(rows) > 1:
        ids = [r[0] for r in rows]
        # Keep the state that has stations attached, else the first.
        keeper = None
        for sid in ids:
            has_station = db.execute(
                text("SELECT 1 FROM stations WHERE state_id = :sid LIMIT 1"), {"sid": sid}
            ).first()
            if has_station:
                keeper = sid
                break
        keeper = keeper or ids[0]
        losers = [i for i in ids if i != keeper]
        print("keeper:", keeper, "losers:", losers)

        for loser in losers:
            # Delete LGAs in the loser state that would duplicate keeper LGAs.
            db.execute(
                text(
                    "DELETE FROM lgas WHERE state_id = :loser AND name IN "
                    "(SELECT name FROM lgas WHERE state_id = :keeper)"
                ),
                {"loser": loser, "keeper": keeper},
            )
            # Move remaining LGAs across.
            db.execute(
                text("UPDATE lgas SET state_id = :keeper WHERE state_id = :loser"),
                {"keeper": keeper, "loser": loser},
            )
            # Repoint stations before removing the parent row.
            db.execute(
                text("UPDATE stations SET state_id = :keeper WHERE state_id = :loser"),
                {"keeper": keeper, "loser": loser},
            )
            db.execute(text("DELETE FROM states WHERE id = :loser"), {"loser": loser})
            print("merged loser:", loser)

    # Normalise LGA alias names (e.g. Abuja Municipal -> official council name).
    for alias, target in LGA_ALIASES.items():
        # Only rename when the target name does not already exist in that state.
        db.execute(
            text(
                "UPDATE lgas SET name = :target WHERE name = :alias AND state_id NOT IN "
                "(SELECT state_id FROM lgas WHERE name = :target)"
            ),
            {"alias": alias, "target": target},
        )
        # Drop any residual duplicates of the alias.
        db.execute(
            text(
                "DELETE FROM lgas WHERE name = :alias AND state_id IN "
                "(SELECT state_id FROM lgas WHERE name = :target)"
            ),
            {"alias": alias, "target": target},
        )

    db.commit()

    state_count = db.execute(text("SELECT COUNT(*) FROM states")).scalar()
    lga_count = db.execute(text("SELECT COUNT(*) FROM lgas")).scalar()
    print(f"FINAL states={state_count} lgas={lga_count}")

    fct = db.execute(
        text("SELECT id FROM states WHERE name = :n"), {"n": CANONICAL}
    ).first()
    if fct:
        names = db.execute(
            text("SELECT name FROM lgas WHERE state_id = :id ORDER BY name"),
            {"id": fct[0]},
        ).fetchall()
        print(f"FCT Abuja LGAs ({len(names)}):", [n[0] for n in names])

print("RECONCILE COMPLETE")
