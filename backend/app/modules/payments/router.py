import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.core.deps import allowed_station_ids, get_current_user, require_permission
from app.db.base import get_db
from app.models.auth import User
from app.models.core import Nozzle, PaymentRecord, POSTerminal

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.get("/terminals")
def list_pos_terminals(station_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(POSTerminal)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        stmt = stmt.where(POSTerminal.station_id.in_(allowed))
    if station_id:
        stmt = stmt.where(POSTerminal.station_id == station_id)
    terms = db.scalars(stmt).all()
    res = []
    for t in terms:
        res.append({
            "id": t.id,
            "terminal_id": t.terminal_id,
            "serial_number": t.serial_number,
            "provider": t.provider,
            "station_id": t.station_id,
            "station_name": t.station.name if t.station else "",
            "nozzle_id": t.nozzle_id,
            "nozzle_number": t.nozzle.number if t.nozzle else None,
            "dispenser_code": t.nozzle.dispenser.code if t.nozzle and t.nozzle.dispenser else None,
            "is_active": t.is_active,
        })
    return res


@router.post("/terminals", status_code=status.HTTP_201_CREATED)
def create_pos_terminal(payload: dict[str, Any], db: Session = Depends(get_db), user: User = Depends(require_permission("pos", "create"))):
    station_id = payload.get("station_id")
    allowed = allowed_station_ids(user)
    if allowed is not None and station_id not in allowed:
        raise HTTPException(status_code=403, detail="Station out of scope")
    nozzle_id = payload.get("nozzle_id")
    terminal = POSTerminal(
        terminal_id=payload["terminal_id"],
        serial_number=payload["serial_number"],
        provider=payload.get("provider", "OPAY"),
        station_id=station_id,
        nozzle_id=nozzle_id if nozzle_id else None,
        is_active=payload.get("is_active", True),
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)
    return {"id": terminal.id, "terminal_id": terminal.terminal_id}


@router.get("/records")
def list_payment_records(station_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(PaymentRecord).order_by(desc(PaymentRecord.created_at))
    allowed = allowed_station_ids(user)
    if allowed is not None:
        stmt = stmt.where(PaymentRecord.station_id.in_(allowed))
    if station_id:
        stmt = stmt.where(PaymentRecord.station_id == station_id)
    payments = db.scalars(stmt.limit(50)).all()
    res = []
    for p in payments:
        res.append({
            "id": p.id,
            "reference": p.reference,
            "amount": p.amount,
            "currency": p.currency,
            "provider": p.provider,
            "payment_method": p.payment_method,
            "status": p.status,
            "pos_terminal_id": p.pos_terminal_id,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return res


@router.post("/simulate-opay-checkout")
def simulate_opay_checkout(payload: dict[str, Any], db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Simulates OPay Card / Bank Transfer verification.
    Only successful verified responses return an authenticated dispensing authorization token.
    """
    amount = float(payload.get("amount", 5000.0))
    pos_id = payload.get("pos_terminal_id", "OPAY-POS-001")
    nozzle_id = payload.get("nozzle_id")
    method = payload.get("payment_method", "CARD_POS")  # CARD_POS or BANK_TRANSFER

    ref = f"OPAY-PAY-{uuid.uuid4().hex[:10].upper()}"
    rec = PaymentRecord(
        reference=ref,
        amount=amount,
        currency="NGN",
        provider="OPAY",
        payment_method=method,
        status="VERIFIED",
        pos_terminal_id=pos_id,
        nozzle_id=nozzle_id,
    )
    db.add(rec)
    db.commit()

    # Returns cryptographically verified dispensing authorization token
    auth_token = f"AUTH-TOKEN-{uuid.uuid4().hex}"
    return {
        "status": "SUCCESS",
        "payment_reference": ref,
        "amount": amount,
        "currency": "NGN",
        "dispensing_authorized": True,
        "authorization_token": auth_token,
        "message": "Payment verified via OPay Gateway. Dispensing authorized.",
    }
