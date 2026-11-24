import random
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.core.deps import allowed_station_ids, get_current_user, require_permission
from app.core.config import settings
from app.core.validation import parse_float
from app.db.base import get_db
from app.models.auth import User
from app.models.core import (
    Dispenser,
    FuelTransaction,
    Nozzle,
    PaymentRecord,
    SystemAlert,
    Tank,
    Wallet,
    WalletLedgerEntry,
)

router = APIRouter(prefix="/api/v1", tags=["transactions"])


@router.get("/transactions")
def list_transactions(
    station_id: str | None = None,
    nozzle_id: str | None = None,
    discrepancy_only: bool = False,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(FuelTransaction).order_by(desc(FuelTransaction.started_at))
    allowed = allowed_station_ids(user)
    if allowed is not None:
        stmt = stmt.where(FuelTransaction.station_id.in_(allowed))
    if station_id:
        stmt = stmt.where(FuelTransaction.station_id == station_id)
    if nozzle_id:
        stmt = stmt.where(FuelTransaction.nozzle_id == nozzle_id)
    if discrepancy_only:
        stmt = stmt.where(FuelTransaction.discrepancy_alert.is_(True))

    txs = db.scalars(stmt.limit(limit)).all()
    res = []
    for t in txs:
        res.append({
            "id": t.id,
            "transaction_ref": t.transaction_ref,
            "station_id": t.station_id,
            "station_name": t.station.name if t.station else "",
            "dispenser_code": t.dispenser.code if t.dispenser else "",
            "nozzle_number": t.nozzle.number if t.nozzle else 1,
            "product_code": t.nozzle.product.code if t.nozzle and t.nozzle.product else "PMS",
            "unit_price": t.unit_price,
            "requested_amount": t.requested_amount,
            "requested_volume": t.requested_volume,
            "dispenser_cpu_volume": t.dispenser_cpu_volume,
            "independent_pulser_volume": t.independent_pulser_volume,
            "raw_pulse_count": t.raw_pulse_count,
            "volume_difference": t.volume_difference,
            "discrepancy_alert": t.discrepancy_alert,
            "investigation_status": t.investigation_status,
            "investigation_notes": t.investigation_notes,
            "total_amount_billed": t.total_amount_billed,
            "payment_channel": t.payment_channel,
            "payment_ref": t.payment_ref,
            "status": t.status,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        })
    return res


@router.post("/transactions/simulate-dispense", status_code=status.HTTP_201_CREATED)
def simulate_dispense(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("transactions", "create")),
):
    """
    Executes a realistic physical dispensing cycle:
    1. Validates Payment (Rule: NO VERIFIED PAYMENT, NO DISPENSING)
    2. Sends preset to Wayne Dispenser CPU (simulated)
    3. Concurrently counts physical pulses from independent optical/magnetic pulser
    4. Computes Delta = |CPU - Pulser|
    5. Flags CRITICAL_DISCREPANCY if Delta >= 0.49 Litres
    """
    if settings.ENVIRONMENT.lower() in {"production", "prod", "live"}:
        raise HTTPException(status_code=404, detail="Sandbox dispensing unavailable")
    nozzle_id = payload.get("nozzle_id")
    nozzle = db.scalar(select(Nozzle).where(Nozzle.id == nozzle_id))
    if not nozzle:
        raise HTTPException(status_code=404, detail="Nozzle not found")

    allowed = allowed_station_ids(user)
    if allowed is not None and nozzle.dispenser.station_id not in allowed:
        raise HTTPException(status_code=403, detail="Station out of scope")

    payment_channel = str(payload.get("payment_channel") or "").upper()
    if payment_channel == "RFID_WALLET":
        raise HTTPException(
            status_code=409,
            detail="RFID dispensing requires secure card authentication and is not enabled in the sandbox",
        )
    if payment_channel not in {"OPAY_POS", "BANK_TRANSFER"}:
        raise HTTPException(status_code=400, detail="Unsupported payment channel")
    if nozzle.status != "ACTIVE" or nozzle.dispenser.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Nozzle or dispenser is not active")
    if nozzle.price <= 0:
        raise HTTPException(status_code=409, detail="Nozzle price must be configured before dispensing")
    requested_amount = parse_float(payload.get("requested_amount"), "requested_amount", minimum=0.01)
    unit_price = nozzle.price
    requested_volume = round(requested_amount / unit_price, 3)
    payment_ref = str(payload.get("payment_ref") or "").strip()
    if not payment_ref:
        raise HTTPException(status_code=400, detail="Verified payment reference is required")
    payment = db.scalar(
        select(PaymentRecord)
        .where(PaymentRecord.reference == payment_ref)
        .with_for_update()
    )
    if payment is None or payment.status != "VERIFIED" or payment.purpose != "FUEL":
        raise HTTPException(status_code=400, detail="Payment is not verified")
    if payment.transaction_id:
        raise HTTPException(status_code=409, detail="Payment reference is already linked to a transaction")
    if abs(payment.amount - requested_amount) > 0.01:
        raise HTTPException(status_code=400, detail="Payment amount does not match the preset amount")
    if payment.station_id != nozzle.dispenser.station_id:
        raise HTTPException(status_code=400, detail="Payment is not assigned to this station")
    if payment.nozzle_id is not None and payment.nozzle_id != nozzle.id:
        raise HTTPException(status_code=400, detail="Payment is not assigned to this nozzle")
    expected_methods = {
        "OPAY_POS": {"CARD_POS", "OPAY_POS"},
        "BANK_TRANSFER": {"BANK_TRANSFER"},
    }
    if payment.payment_method not in expected_methods[payment_channel]:
        raise HTTPException(status_code=400, detail="Payment method does not match the dispensing channel")

    # Simulation parameter: simulate discrepancy or normal flow
    force_discrepancy = payload.get("simulate_discrepancy", False)

    cpu_volume = requested_volume
    if force_discrepancy:
        # Physical pulser registers less than CPU (fuel diversion or meter slip)
        pulser_volume = round(cpu_volume - random.uniform(0.55, 1.25), 3)
    else:
        # Realistic sensor noise: delta within legal ±0.03 L
        pulser_volume = round(cpu_volume + random.uniform(-0.04, 0.04), 3)

    cal_factor = nozzle.fcc.calibration_factor if nozzle.fcc else 100.0
    raw_pulses = int(pulser_volume * cal_factor)
    volume_diff = round(abs(cpu_volume - pulser_volume), 3)
    has_discrepancy = volume_diff >= 0.490

    total_billed = round(cpu_volume * unit_price, 2)
    tx_ref = f"TXN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

    tx = FuelTransaction(
        transaction_ref=tx_ref,
        station_id=nozzle.dispenser.station_id,
        dispenser_id=nozzle.dispenser_id,
        nozzle_id=nozzle.id,
        fcc_device_id=nozzle.fcc.id if nozzle.fcc else None,
        payment_channel=payment_channel,
        payment_ref=payment_ref,
        unit_price=unit_price,
        requested_amount=requested_amount,
        requested_volume=requested_volume,
        dispenser_cpu_volume=cpu_volume,
        independent_pulser_volume=pulser_volume,
        raw_pulse_count=raw_pulses,
        volume_difference=volume_diff,
        discrepancy_alert=has_discrepancy,
        investigation_status="UNDER_REVIEW" if has_discrepancy else "NORMAL",
        total_amount_billed=total_billed,
        status="COMPLETED",
    )
    db.add(tx)
    db.flush()
    payment.transaction_id = tx.id
    payment.station_id = nozzle.dispenser.station_id
    payment.nozzle_id = nozzle.id

    if payment_channel == "RFID_WALLET":
        customer_id = payload.get("customer_id")
        if not customer_id:
            raise HTTPException(status_code=400, detail="Customer is required for RFID wallet dispensing")
        wallet = db.scalar(select(Wallet).where(Wallet.customer_id == customer_id))
        if wallet is None:
            raise HTTPException(status_code=404, detail="Customer wallet not found")
        if wallet.balance - wallet.reserved_balance < total_billed:
            raise HTTPException(status_code=400, detail="Insufficient verified wallet balance")
        balance_before = wallet.balance
        wallet.balance -= total_billed
        db.add(WalletLedgerEntry(
            wallet_id=wallet.id,
            reference=f"SALE-{tx.transaction_ref}",
            entry_type="SALE_DEBIT",
            amount=-round(total_billed, 2),
            balance_before=balance_before,
            balance_after=wallet.balance,
            payment_reference=payment_ref,
            created_by=user.user_id,
        ))

    # Update Dispenser & Nozzle totalizers
    nozzle.totalizer_l += cpu_volume
    nozzle.dispenser.totalizer_l += cpu_volume

    # Decrement Tank Volume if assigned
    if nozzle.tank_id:
        tank = db.scalar(select(Tank).where(Tank.id == nozzle.tank_id))
        if tank:
            tank.current_volume_l = max(0.0, round(tank.current_volume_l - cpu_volume, 2))

    # Trigger Critical Alert if discrepancy exceeds 0.49L threshold
    if has_discrepancy:
        alert = SystemAlert(
            station_id=nozzle.dispenser.station_id,
            alert_type="PULSER_DISCREPANCY",
            severity="CRITICAL",
            title=f"Pulser Measurement Discrepancy on {nozzle.dispenser.code} (Nozzle {nozzle.number})",
            description=f"Transaction {tx_ref}: Dispenser CPU reported {cpu_volume:.3f} L, but Independent Pulser verified only {pulser_volume:.3f} L. Delta: {volume_diff:.3f} L (Threshold 0.490 L exceeded).",
            entity_type="transaction",
            entity_id=tx.id,
        )
        db.add(alert)

    db.commit()
    db.refresh(tx)
    return {
        "id": tx.id,
        "transaction_ref": tx.transaction_ref,
        "cpu_volume": tx.dispenser_cpu_volume,
        "pulser_volume": tx.independent_pulser_volume,
        "difference": tx.volume_difference,
        "discrepancy_alert": tx.discrepancy_alert,
        "total_amount_billed": tx.total_amount_billed,
    }


@router.patch("/transactions/{tx_id}/investigate")
def update_investigation(
    tx_id: str,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("transactions", "view")),
):
    tx = db.scalar(select(FuelTransaction).where(FuelTransaction.id == tx_id))
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if "investigation_status" in payload:
        tx.investigation_status = payload["investigation_status"]
    if "investigation_notes" in payload:
        tx.investigation_notes = payload["investigation_notes"]
    db.commit()
    return {"id": tx.id, "status": tx.investigation_status}
