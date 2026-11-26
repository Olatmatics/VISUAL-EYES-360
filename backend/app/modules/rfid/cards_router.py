"""RFID card registry (cards are valid nationwide, not tied to a state)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.base import get_db
from app.models.auth import User
from app.models.core import Customer, RFIDCard, Station, Wallet

router = APIRouter(prefix="/api/v1/rfid", tags=["rfid-cards"])


@router.get("/cards")
def list_cards(db: Session = Depends(get_db), _: User = Depends(require_permission("customers", "view"))):
    cards = db.scalars(select(RFIDCard).order_by(RFIDCard.created_at.desc())).all()
    result = []
    for card in cards:
        customer = db.scalar(select(Customer).where(Customer.id == card.customer_id))
        wallet = db.scalar(select(Wallet).where(Wallet.customer_id == card.customer_id))
        home = db.scalar(select(Station).where(Station.id == card.home_station_id)) if card.home_station_id else None
        result.append({
            "id": card.id, "uid": card.card_uid,
            "owner": customer.full_name if customer else "Unknown",
            "blocked": bool(card.is_blocked),
            "balance_ngn": wallet.balance if wallet else 0,
            "home_station_id": card.home_station_id,
            "home_station": home.name if home else None,
            "nationwide": True,
            "created_at": card.created_at.isoformat() if card.created_at else None,
        })
    return result
