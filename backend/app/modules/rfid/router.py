"""RFID card registration and wallet-based dispensing for the Serial prototype.

The ESP32 posts the UID it reads; the backend owns identity, balance and
authorization. A card is never itself proof of payment.
"""

import hashlib
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.id_resolve import resolve_by_id_or_code
from app.core.validation import utcnow
from app.db.base import get_db
from app.models.core import (
    Customer, DeviceCommand, Dispenser, FCCDevice, Nozzle, PaymentRecord,
    RFIDCard, Station, Wallet, WalletLedgerEntry,
)
from app.modules.hardware.service import record_exchange

router = APIRouter(prefix="/api/v1/rfid", tags=["rfid"])


def _check_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key == settings.INGEST_API_KEY:
        return
    # Bench convenience only: production always requires the key.
    if settings.ENVIRONMENT.lower() in {"development", "dev", "local"} and not x_api_key:
        return
    raise HTTPException(status_code=401, detail="Invalid device API key")


def _home_station(db: Session, station_id: str | None):
    if not station_id:
        return None
    station = resolve_by_id_or_code(db, Station, station_id)
    if station is None:
        raise HTTPException(404, "Station not found — check the short code in the sketch")
    return station


def _create_card(db: Session, uid: str, name: str, station_id: str | None) -> RFIDCard:
    customer = Customer(
        id=str(uuid.uuid4()), full_name=name, phone=f"RFID-{uid}",
        category="SPECIAL_CUSTOMER", is_active=True,
    )
    db.add(customer)
    db.flush()
    db.add(Wallet(id=str(uuid.uuid4()), customer_id=customer.id, balance=0, reserved_balance=0))
    card = RFIDCard(
        id=str(uuid.uuid4()), card_uid=uid, customer_id=customer.id,
        home_station_id=station_id,
        # Placeholder hash for the bench; real secure keys are added with the
        # chosen RFID technology from docs/08-open-items.md.
        auth_key_hash=hashlib.sha256(uid.encode()).hexdigest(),
        is_blocked=False, daily_spend_limit=100000,
    )
    db.add(card)
    return card


@router.post("/scan")
def rfid_scan(payload: dict[str, Any], db: Session = Depends(get_db), _: None = Depends(_check_key)):
    """Register an unknown card automatically, or return its owner and balance."""
    uid = str(payload.get("uid") or "").strip().upper()
    if not uid:
        raise HTTPException(400, "Card UID is required")

    card = db.scalar(select(RFIDCard).where(RFIDCard.card_uid == uid))
    if card is None:
        name = str(payload.get("name") or f"Card {uid[-6:]}").strip()
        card = _create_card(db, uid, name, None)
        db.commit()
        response = {
            "registered": True, "uid": uid, "customer": name,
            "balance_ngn": 0, "message": "NEW CARD REGISTERED",
        }
        record_exchange(direction="IN", endpoint="/api/v1/rfid/scan", device_uid=uid, request=payload, response=response)
        return response

    if card.is_blocked:
        raise HTTPException(403, "Card is blocked")
    wallet = db.scalar(select(Wallet).where(Wallet.customer_id == card.customer_id))
    customer = db.scalar(select(Customer).where(Customer.id == card.customer_id))
    response = {
        "registered": False, "uid": uid,
        "customer": customer.full_name if customer else "Unknown",
        "balance_ngn": wallet.balance if wallet else 0,
        "message": "CARD RECOGNISED",
    }
    record_exchange(direction="IN", endpoint="/api/v1/rfid/scan", device_uid=uid, request=payload, response=response)
    return response


@router.post("/prototype/register")
def rfid_prototype_register(payload: dict[str, Any], db: Session = Depends(get_db), _: None = Depends(_check_key)):
    """Serial-Monitor card enrolment: UID is shown, saved for a home station, nationwide after."""
    uid = str(payload.get("uid") or "").strip().upper()
    if not uid:
        raise HTTPException(400, "Card UID is required")
    station = _home_station(db, str(payload.get("station_id") or "").strip() or None)
    name = str(payload.get("owner") or payload.get("name") or f"Card {uid[-6:]}").strip()

    card = db.scalar(select(RFIDCard).where(RFIDCard.card_uid == uid))
    created = card is None
    if created:
        card = _create_card(db, uid, name, station.id if station else None)
    else:
        if station and not card.home_station_id:
            card.home_station_id = station.id
    db.commit()

    wallet = db.scalar(select(Wallet).where(Wallet.customer_id == card.customer_id))
    customer = db.scalar(select(Customer).where(Customer.id == card.customer_id))
    response = {
        "registered": created,
        "uid": uid,
        "owner": customer.full_name if customer else name,
        "home_station_id": card.home_station_id,
        "home_station": station.name if station else None,
        "balance_ngn": wallet.balance if wallet else 0,
        "nationwide": True,
        "message": "NEW CARD SAVED" if created else "CARD ALREADY REGISTERED — UPDATED",
    }
    record_exchange(
        direction="IN", endpoint="/api/v1/rfid/prototype/register",
        device_uid=uid, request=payload, response=response,
    )
    return response


@router.post("/fund")
def rfid_fund(payload: dict[str, Any], db: Session = Depends(get_db), _: None = Depends(_check_key)):
    """Bench-only: add funds to a card wallet after a verified external payment."""
    uid = str(payload.get("uid") or "").strip().upper()
    amount = float(payload.get("amount_ngn") or 0)
    if amount <= 0:
        raise HTTPException(400, "amount_ngn must be positive")
    card = db.scalar(select(RFIDCard).where(RFIDCard.card_uid == uid))
    if card is None:
        raise HTTPException(404, "Card not registered — scan it first")
    wallet = db.scalar(select(Wallet).where(Wallet.customer_id == card.customer_id))
    if wallet is None:
        raise HTTPException(404, "Wallet not found")
    before = wallet.balance
    wallet.balance = round(before + amount, 2)
    db.add(WalletLedgerEntry(
        id=str(uuid.uuid4()), wallet_id=wallet.id,
        reference=f"FUND-{uuid.uuid4().hex[:10].upper()}",
        entry_type="FUNDING", amount=amount, balance_before=before,
        balance_after=wallet.balance, created_by="RFID_BENCH", created_at=utcnow(),
    ))
    db.commit()
    response = {"uid": uid, "balance_ngn": wallet.balance}
    record_exchange(direction="IN", endpoint="/api/v1/rfid/fund", device_uid=uid, request=payload, response=response)
    return response


@router.post("/authorize")
def rfid_authorize(payload: dict[str, Any], db: Session = Depends(get_db), _: None = Depends(_check_key)):
    """Pay for fuel from the card wallet, then queue PAYMENT_SUCCESS for the nozzle."""
    uid = str(payload.get("uid") or "").strip().upper()
    amount = float(payload.get("amount_ngn") or 0)
    nozzle = resolve_by_id_or_code(db, Nozzle, payload.get("nozzle_id"))
    if not uid or amount <= 0 or nozzle is None:
        raise HTTPException(400, "uid, amount_ngn and nozzle_id are required")

    card = db.scalar(select(RFIDCard).where(RFIDCard.card_uid == uid))
    if card is None:
        raise HTTPException(404, "Card not registered — scan it first")
    if card.is_blocked:
        raise HTTPException(403, "Card is blocked")
    wallet = db.scalar(select(Wallet).where(Wallet.customer_id == card.customer_id))
    if wallet is None or wallet.balance < amount:
        raise HTTPException(402, "Insufficient wallet balance")

    dispenser = db.scalar(select(Dispenser).where(Dispenser.id == nozzle.dispenser_id))
    reference = f"RFID-{uuid.uuid4().hex[:10].upper()}"
    before = wallet.balance
    wallet.balance = round(before - amount, 2)
    db.add(WalletLedgerEntry(
        id=str(uuid.uuid4()), wallet_id=wallet.id, reference=reference,
        entry_type="SALE_DEBIT", amount=amount, balance_before=before,
        balance_after=wallet.balance, created_by="RFID_TXN", created_at=utcnow(),
    ))
    payment = PaymentRecord(
        id=str(uuid.uuid4()), reference=reference, amount=amount, currency="NGN",
        provider="RFID_WALLET", payment_method="WALLET", status="VERIFIED",
        purpose="FUEL", station_id=dispenser.station_id if dispenser else None,
        nozzle_id=nozzle.id, authorized_at=utcnow(),
    )
    db.add(payment)
    fcc = db.scalar(select(FCCDevice).where(FCCDevice.nozzle_id == nozzle.id))
    if fcc:
        import json
        db.add(DeviceCommand(
            id=str(uuid.uuid4()), device_uid=fcc.device_uid, command_type="PAYMENT_SUCCESS",
            payload_json=json.dumps({
                "reference": reference, "status": "APPROVED", "amount_ngn": amount,
                "payment_method": "RFID_WALLET", "authorized_liters": round(amount / (nozzle.price or 1), 2),
            }),
            created_at=utcnow(),
        ))
    db.commit()
    response = {
        "reference": reference, "status": "APPROVED", "amount_ngn": amount,
        "balance_ngn": wallet.balance,
        "authorized_liters": round(amount / (nozzle.price or 1), 2),
        "device_uid": fcc.device_uid if fcc else None,
    }
    record_exchange(direction="IN", endpoint="/api/v1/rfid/authorize", device_uid=uid, request=payload, response=response)
    if fcc:
        record_exchange(
            direction="OUT", endpoint="/api/v1/rfid/authorize → device command",
            device_uid=fcc.device_uid, request={
                "type": "PAYMENT_SUCCESS",
                "payload": {
                    "reference": reference, "status": "APPROVED", "amount_ngn": amount,
                    "payment_method": "RFID_WALLET",
                    "authorized_liters": response["authorized_liters"],
                },
            },
            response={"queued": True, "collected_by": "GET /api/v1/fcc/commands/poll"},
        )
    return response
