from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.core.deps import allowed_station_ids, get_current_user, require_permission
from app.db.base import get_db
from app.models.auth import User
from app.models.core import Nozzle, PriceHistory, Station

router = APIRouter(prefix="/api/v1/prices", tags=["prices"])


@router.get("")
def list_prices(station_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Nozzle)
    allowed = allowed_station_ids(user)
    nozzles = db.scalars(stmt).all()
    res = []
    for n in nozzles:
        if n.dispenser and allowed is not None and n.dispenser.station_id not in allowed:
            continue
        if station_id and n.dispenser and n.dispenser.station_id != station_id:
            continue
        res.append({
            "nozzle_id": n.id,
            "nozzle_number": n.number,
            "dispenser_code": n.dispenser.code if n.dispenser else "",
            "station_id": n.dispenser.station_id if n.dispenser else "",
            "station_name": n.dispenser.station.name if n.dispenser and n.dispenser.station else "",
            "product_code": n.product.code if n.product else "PMS",
            "price": n.price,
            "status": n.status,
        })
    return res


@router.post("/update")
def update_price(payload: dict[str, Any], db: Session = Depends(get_db), user: User = Depends(require_permission("prices", "create"))):
    """
    Price updates supported at:
    - scope = 'NOZZLE': updates single nozzle
    - scope = 'DISPENSER': updates all nozzles on dispenser
    - scope = 'STATION': updates all nozzles of product in station
    - scope = 'NATIONWIDE': updates all nozzles of product across all registered stations
    """
    scope = payload.get("scope", "NOZZLE")  # NOZZLE, DISPENSER, STATION, NATIONWIDE
    new_price = float(payload["new_price"])
    product_code = payload.get("product_code", "PMS")

    if new_price <= 0:
        raise HTTPException(status_code=400, detail="Invalid price value")

    updated_count = 0

    if scope == "NOZZLE":
        nozzle_id = payload.get("nozzle_id")
        nozzle = db.scalar(select(Nozzle).where(Nozzle.id == nozzle_id))
        if not nozzle:
            raise HTTPException(status_code=404, detail="Nozzle not found")
        old_price = nozzle.price
        nozzle.price = new_price
        db.add(PriceHistory(
            station_id=nozzle.dispenser.station_id,
            dispenser_id=nozzle.dispenser_id,
            nozzle_id=nozzle.id,
            product_code=product_code,
            previous_price=old_price,
            new_price=new_price,
            changed_by_user_id=user.user_id,
            status="CONFIRMED",
        ))
        updated_count = 1

    elif scope == "STATION":
        station_id = payload.get("station_id")
        station = db.scalar(select(Station).where(Station.id == station_id))
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")
        for d in station.dispensers:
            for n in d.nozzles:
                if n.product and n.product.code == product_code:
                    old = n.price
                    n.price = new_price
                    db.add(PriceHistory(
                        station_id=station.id,
                        dispenser_id=d.id,
                        nozzle_id=n.id,
                        product_code=product_code,
                        previous_price=old,
                        new_price=new_price,
                        changed_by_user_id=user.user_id,
                        status="CONFIRMED",
                    ))
                    updated_count += 1

    elif scope == "NATIONWIDE":
        if not user.is_super_admin:
            raise HTTPException(status_code=403, detail="Nationwide price change requires Superior Administrator privileges")
        nozzles = db.scalars(select(Nozzle)).all()
        for n in nozzles:
            if n.product and n.product.code == product_code:
                old = n.price
                n.price = new_price
                st_id = n.dispenser.station_id if n.dispenser else None
                if st_id:
                    db.add(PriceHistory(
                        station_id=st_id,
                        dispenser_id=n.dispenser_id,
                        nozzle_id=n.id,
                        product_code=product_code,
                        previous_price=old,
                        new_price=new_price,
                        changed_by_user_id=user.user_id,
                        status="CONFIRMED",
                    ))
                updated_count += 1

    db.commit()
    return {"status": "SUCCESS", "scope": scope, "new_price": new_price, "nozzles_updated": updated_count}


@router.get("/history")
def price_history(limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(PriceHistory).order_by(desc(PriceHistory.created_at)).limit(limit)
    history = db.scalars(stmt).all()
    res = []
    for h in history:
        res.append({
            "id": h.id,
            "station_id": h.station_id,
            "product_code": h.product_code,
            "previous_price": h.previous_price,
            "new_price": h.new_price,
            "changed_by": h.changed_by_user_id,
            "status": h.status,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        })
    return res
