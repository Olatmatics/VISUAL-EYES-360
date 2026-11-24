import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.core.deps import allowed_station_ids, get_current_user, require_permission, write_audit
from app.core.config import settings
from app.core.validation import parse_float, validate_station
from app.db.base import get_db
from app.models.auth import User
from app.models.core import Nozzle, PaymentRecord, POSTerminal

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.get("/terminals")
def list_pos_terminals(station_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.has_permission("pos", "view") and not user.has_permission("payments", "view"):
        raise HTTPException(status_code=403, detail="Permission denied")
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
def create_pos_terminal(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("pos", "create")),
):
    station_id = str(payload.get("station_id") or "")
    station = validate_station(db, station_id)
    allowed = allowed_station_ids(user)
    if allowed is not None and station_id not in allowed:
        raise HTTPException(status_code=403, detail="Station out of scope")
    terminal_id = str(payload.get("terminal_id") or "").strip()
    serial_number = str(payload.get("serial_number") or "").strip()
    if not terminal_id or not serial_number:
        raise HTTPException(status_code=400, detail="Terminal ID and serial number are required")
    if db.scalar(select(POSTerminal.id).where(POSTerminal.terminal_id == terminal_id)):
        raise HTTPException(status_code=409, detail="Terminal ID already registered")
    if db.scalar(select(POSTerminal.id).where(POSTerminal.serial_number == serial_number)):
        raise HTTPException(status_code=409, detail="Terminal serial number already registered")
    nozzle_id = payload.get("nozzle_id")
    nozzle = None
    if nozzle_id:
        nozzle = db.scalar(select(Nozzle).where(Nozzle.id == nozzle_id))
        if nozzle is None:
            raise HTTPException(status_code=404, detail="Nozzle not found")
        if nozzle.dispenser.station_id != station.id:
            raise HTTPException(status_code=400, detail="Nozzle belongs to a different station")
        if nozzle.pos is not None:
            raise HTTPException(status_code=409, detail="Nozzle already has an assigned POS terminal")
    terminal = POSTerminal(
        terminal_id=terminal_id,
        serial_number=serial_number,
        provider=str(payload.get("provider") or "OPAY").strip().upper(),
        station_id=station.id,
        nozzle_id=nozzle_id if nozzle_id else None,
        is_active=bool(payload.get("is_active", True)),
    )
    db.add(terminal)
    db.flush()
    write_audit(db, user, "REGISTER_POS_TERMINAL", "POSTerminal", terminal.id, after={
        "terminal_id": terminal.terminal_id,
        "serial_number": terminal.serial_number,
        "provider": terminal.provider,
        "station_id": terminal.station_id,
        "nozzle_id": terminal.nozzle_id,
    }, request=request)
    db.commit()
    db.refresh(terminal)
    return {"id": terminal.id, "terminal_id": terminal.terminal_id}


@router.get("/records")
def list_payment_records(station_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.has_permission("payments", "view"):
        raise HTTPException(status_code=403, detail="Permission denied")
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
def simulate_opay_checkout(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payments", "create")),
):
    """Development-only sandbox. This endpoint never creates a verified payment."""
    if settings.ENVIRONMENT.lower() in {"production", "prod", "live"}:
        raise HTTPException(status_code=404, detail="Sandbox endpoint unavailable")
    amount = parse_float(payload.get("amount"), "amount", minimum=0.01)
    pos_id = payload.get("pos_terminal_id", "OPAY-POS-001")
    nozzle_id = payload.get("nozzle_id")
    method = str(payload.get("payment_method") or "CARD_POS").upper()
    if method not in {"CARD_POS", "BANK_TRANSFER"}:
        raise HTTPException(status_code=400, detail="Unsupported sandbox payment method")

    ref = f"OPAY-PAY-{uuid.uuid4().hex[:10].upper()}"
    rec = PaymentRecord(
        reference=ref,
        amount=amount,
        currency="NGN",
        provider="OPAY",
        payment_method=method,
        status="INITIATED",
        pos_terminal_id=pos_id,
        nozzle_id=nozzle_id,
    )
    db.add(rec)
    db.commit()

    return {
        "status": "SANDBOX_INITIATED",
        "sandbox": True,
        "payment_reference": ref,
        "amount": amount,
        "currency": "NGN",
        "dispensing_authorized": False,
        "authorization_token": None,
        "message": "Development sandbox only. No real payment was verified.",
    }


@router.post("/sandbox/verify")
def verify_sandbox_payment(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payments", "approve")),
):
    """Development-only: mark a sandbox payment VERIFIED for end-to-end testing.

    Production rejects this endpoint. Real provider callbacks are added when
    the OPay/bank integration documentation is supplied (see 08-open-items.md).
    """
    if settings.ENVIRONMENT.lower() in {"production", "prod", "live"}:
        raise HTTPException(status_code=404, detail="Sandbox endpoint unavailable")
    reference = str(payload.get("payment_reference") or payload.get("reference") or "")
    record = db.scalar(select(PaymentRecord).where(PaymentRecord.reference == reference))
    if record is None:
        raise HTTPException(status_code=404, detail="Payment record not found")
    if record.status == "VERIFIED":
        return {"status": "VERIFIED", "payment_reference": record.reference, "already_verified": True}
    if record.status != "INITIATED":
        raise HTTPException(status_code=409, detail=f"Payment is {record.status}, cannot verify")
    before = {"status": record.status}
    record.status = "VERIFIED"
    record.authorized_at = datetime.now(timezone.utc).replace(tzinfo=None)
    write_audit(db, user, "SANDBOX_VERIFY_PAYMENT", "PaymentRecord", record.id,
                before=before, after={"status": "VERIFIED"}, request=request)
    db.commit()
    return {"status": "VERIFIED", "payment_reference": record.reference,
            "amount": record.amount, "dispensing_authorized": True,
            "message": "Development sandbox verification only."}
