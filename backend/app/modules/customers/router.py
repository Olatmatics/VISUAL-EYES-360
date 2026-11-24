import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, require_permission, write_audit
from app.db.base import get_db
from app.models.auth import User
from app.models.core import (
    Customer,
    Fleet,
    PaymentRecord,
    RFIDCard,
    Vehicle,
    Wallet,
    WalletLedgerEntry,
)

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("")
def list_customers(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    customers = db.scalars(select(Customer)).all()
    res = []
    for c in customers:
        res.append({
            "id": c.id,
            "full_name": c.full_name,
            "phone": c.phone,
            "email": c.email,
            "category": c.category,
            "is_active": c.is_active,
            "wallet": {
                "balance": c.wallet.balance if c.wallet else 0.0,
                "reserved": c.wallet.reserved_balance if c.wallet else 0.0,
                "available": max(0.0, (c.wallet.balance - c.wallet.reserved_balance)) if c.wallet else 0.0,
            } if c.wallet else None,
            "cards": [
                {
                    "id": card.id,
                    "card_uid": card.card_uid,
                    "is_blocked": card.is_blocked,
                    "daily_spend_limit": card.daily_spend_limit,
                }
                for card in c.cards
            ],
        })
    return res


@router.post("", status_code=status.HTTP_201_CREATED)
def create_customer(payload: dict[str, Any], db: Session = Depends(get_db), user: User = Depends(require_permission("customers", "create"))):
    customer = Customer(
        full_name=payload["full_name"],
        phone=payload["phone"],
        email=payload.get("email"),
        category=payload.get("category", "SPECIAL_CUSTOMER"),
    )
    db.add(customer)
    db.flush()

    # Automatically create dedicated wallet
    wallet = Wallet(
        customer_id=customer.id,
        balance=0.0,
        reserved_balance=0.0,
    )
    db.add(wallet)

    # Optional initial RFID card
    card_uid = payload.get("card_uid")
    if card_uid:
        card = RFIDCard(
            card_uid=card_uid,
            customer_id=customer.id,
            auth_key_hash=uuid.uuid4().hex,
            daily_spend_limit=float(payload.get("daily_spend_limit", 100000.0)),
        )
        db.add(card)

    db.commit()
    db.refresh(customer)
    return {"id": customer.id, "full_name": customer.full_name}


@router.post("/wallets/{customer_id}/fund")
def fund_wallet(
    customer_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("wallet", "manage")),
):
    wallet = db.scalar(select(Wallet).where(Wallet.customer_id == customer_id).with_for_update())
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    amount = float(payload.get("amount", 0.0))
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid funding amount")
    payment_reference = str(payload.get("payment_reference") or "").strip()
    if not payment_reference:
        raise HTTPException(status_code=400, detail="Verified payment reference is required")
    payment = db.scalar(
        select(PaymentRecord)
        .where(PaymentRecord.reference == payment_reference)
        .with_for_update()
    )
    if (
        payment is None
        or payment.status != "VERIFIED"
        or payment.transaction_id is not None
        or payment.purpose != "WALLET_FUNDING"
        or payment.customer_id != customer_id
    ):
        raise HTTPException(status_code=400, detail="Payment is not verified")
    if abs(payment.amount - amount) > 0.01:
        raise HTTPException(status_code=400, detail="Funding amount does not match the verified payment")
    if db.scalar(select(WalletLedgerEntry).where(WalletLedgerEntry.payment_reference == payment_reference)):
        raise HTTPException(status_code=409, detail="This payment has already funded a wallet")

    balance_before = wallet.balance
    wallet.balance += amount
    db.add(WalletLedgerEntry(
        wallet_id=wallet.id,
        reference=f"WLF-{uuid.uuid4().hex[:12].upper()}",
        entry_type="FUNDING",
        amount=amount,
        balance_before=balance_before,
        balance_after=wallet.balance,
        payment_reference=payment_reference,
        created_by=user.user_id,
    ))
    write_audit(
        db,
        user,
        "FUND_WALLET",
        "Wallet",
        wallet.id,
        before={"balance": balance_before},
        after={
            "balance": wallet.balance,
            "amount": amount,
            "payment_reference": payment_reference,
            "customer_id": customer_id,
        },
        request=request,
    )
    db.commit()
    return {"customer_id": customer_id, "new_balance": wallet.balance}


@router.post("/rfid-cards/{card_id}/toggle-block")
def toggle_rfid_block(card_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("rfid", "manage"))):
    card = db.scalar(select(RFIDCard).where(RFIDCard.id == card_id))
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    card.is_blocked = not card.is_blocked
    db.commit()
    return {"id": card.id, "is_blocked": card.is_blocked}


@router.get("/fleets")
def list_fleets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    fleets = db.scalars(select(Fleet)).all()
    res = []
    for f in fleets:
        res.append({
            "id": f.id,
            "name": f.name,
            "code": f.code,
            "organization": f.organization,
            "spending_limit": f.spending_limit,
            "status": f.status,
            "vehicle_count": len(f.vehicles),
            "vehicles": [
                {
                    "id": v.id,
                    "plate_number": v.plate_number,
                    "vehicle_type": v.vehicle_type,
                    "driver_name": v.driver_name,
                    "fuel_type": v.fuel_type,
                    "spending_limit": v.spending_limit,
                    "odometer_km": v.odometer_km,
                }
                for v in f.vehicles
            ]
        })
    return res


@router.post("/fleets", status_code=status.HTTP_201_CREATED)
def create_fleet(payload: dict[str, Any], db: Session = Depends(get_db), user: User = Depends(require_permission("fleet", "create"))):
    fleet = Fleet(
        name=payload["name"],
        code=payload["code"],
        organization=payload["organization"],
        spending_limit=float(payload.get("spending_limit", 1000000.0)),
    )
    db.add(fleet)
    db.commit()
    db.refresh(fleet)
    return {"id": fleet.id, "code": fleet.code}
