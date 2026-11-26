"""Prototype device ↔ backend protocol.

HTTP JSON is used deliberately for the bench build so every ESP32 can be driven
from the Serial Monitor. Commands are queued in `device_commands` and collected
by the controller with a poll. This is a prototype transport, not the final
MQTT/WebSocket design.
"""

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.id_resolve import resolve_by_id_or_code
from app.core.validation import utcnow
from app.db.base import get_db
from app.models.auth import User
from app.models.core import (
    DeviceCommand,
    DeviceEvent,
    Dispenser,
    FCCDevice,
    FuelTransaction,
    Nozzle,
    PaymentRecord,
    POSTerminal,
    Tank,
)
from app.modules.alerts.service import create_alert
from app.modules.hardware.service import record_exchange
from app.modules.payments import opay_service

router = APIRouter(prefix="/api/v1", tags=["prototype"])


def _utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post("/fcc/transaction/initiate")
def initiate_transaction(payload: dict[str, Any], db: Session = Depends(get_db)):
    """Called by the pump controller after the customer enters an amount."""
    reference = str(payload.get("client_tx_ref") or "").strip()
    if not reference:
        raise HTTPException(400, "client_tx_ref is required")
    if db.scalar(select(PaymentRecord).where(PaymentRecord.reference == reference)):
        raise HTTPException(409, "client_tx_ref already exists")

    nozzle = resolve_by_id_or_code(db, Nozzle, payload.get("nozzle_id"))
    if nozzle is None:
        raise HTTPException(404, "Nozzle not found — check the short code in the sketch")
    dispenser = db.scalar(select(Dispenser).where(Dispenser.id == nozzle.dispenser_id))
    if dispenser is None:
        raise HTTPException(404, "Dispenser not found")

    amount = float(payload.get("target_amount_ngn") or 0)
    if amount <= 0:
        raise HTTPException(400, "target_amount_ngn must be positive")
    price = float(nozzle.price or 0)
    if price <= 0:
        raise HTTPException(400, "Nozzle has no price configured")
    authorized_liters = round(amount / price, 2)

    pos = db.scalar(select(POSTerminal).where(POSTerminal.nozzle_id == nozzle.id, POSTerminal.is_active.is_(True)))
    pos_sn = str(payload.get("pos_sn") or (pos.terminal_id if pos else ""))
    if not pos_sn:
        raise HTTPException(400, "No POS terminal assigned to this nozzle")

    method = "BANK_TRANSFER" if str(payload.get("payment_preference", "")).upper() == "BANK_TRANSFER" else "POS_TERMINAL"
    payment = PaymentRecord(
        reference=reference,
        amount=amount,
        currency="NGN",
        provider="OPAY",
        payment_method=method,
        status="INITIATED",
        pos_terminal_id=pos_sn,
        station_id=dispenser.station_id,
        nozzle_id=nozzle.id,
        purpose="FUEL",
    )
    db.add(payment)
    db.flush()

    callback = settings.OPAY_WEBHOOK_URL or None
    description = f"{dispenser.code} / nozzle {nozzle.number}"
    if method == "BANK_TRANSFER":
        response = opay_service.create_bank_transfer(
            reference, int(round(amount * 100)), callback,
            product_name="Fuel Dispense", description=description,
        )
    else:
        response = opay_service.create_pos_payment(
            reference, int(round(amount * 100)), pos_sn, callback,
            product_name="Fuel Dispense", description=description,
        )

    data = response.get("data") or {}
    if response.get("code") != "00000":
        payment.status = "FAILED"
        db.commit()
        raise HTTPException(502, f"OPay create failed: {response.get('message', 'unknown')}")

    payment.transaction_id = data.get("orderNo")
    db.commit()
    response = {
        "reference": reference,
        "order_no": data.get("orderNo"),
        "status": data.get("status", "PENDING"),
        "next_action": data.get("nextAction", {}),
        "authorized_liters": authorized_liters,
        "unit_price_ngn": price,
        "opay_pos_sn": pos_sn,
        "amount_ngn": amount,
    }
    record_exchange(
        direction="IN", endpoint="/api/v1/fcc/transaction/initiate",
        device_uid=str(payload.get("device_uid") or ""),
        request=payload, response=response,
    )
    return response


@router.get("/fcc/commands/poll")
def poll_commands(device_uid: str, limit: int = 10, db: Session = Depends(get_db)):
    commands = db.scalars(
        select(DeviceCommand).where(
            DeviceCommand.device_uid == device_uid,
            DeviceCommand.status == "PENDING",
        ).order_by(DeviceCommand.created_at).limit(limit)
    ).all()
    response = [
        {
            "id": c.id,
            "type": c.command_type,
            "payload": json.loads(c.payload_json or "{}"),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in commands
    ]
    record_exchange(
        direction="OUT", endpoint="/api/v1/fcc/commands/poll", method="GET",
        device_uid=device_uid, request={"limit": limit}, response=response,
    )
    return response


@router.post("/fcc/commands/ack")
def ack_command(payload: dict[str, Any], db: Session = Depends(get_db)):
    command = db.scalar(select(DeviceCommand).where(DeviceCommand.id == payload.get("command_id")))
    if command is None:
        raise HTTPException(404, "Command not found")
    command.status = "ACKED"
    command.ack_at = _utc()
    db.commit()
    response = {"id": command.id, "status": "ACKED"}
    record_exchange(
        direction="IN", endpoint="/api/v1/fcc/commands/ack",
        device_uid=command.device_uid, request=payload, response=response,
    )
    return response


@router.post("/fcc/transaction/complete")
def complete_transaction(payload: dict[str, Any], db: Session = Depends(get_db)):
    """Final dispensing telemetry from the controller (or Serial simulation)."""
    reference = str(payload.get("client_tx_ref") or "")
    payment = db.scalar(select(PaymentRecord).where(PaymentRecord.reference == reference))
    if payment is None:
        raise HTTPException(404, "Payment record not found")
    if payment.status != "VERIFIED":
        raise HTTPException(409, "Payment is not verified — dispensing must not be reported")

    dispensed = float(payload.get("dispensed_liters") or 0)
    cpu = float(payload.get("cpu_volume_l") or dispensed)
    pulser = float(payload.get("pulser_volume_l") or dispensed)
    difference = round(cpu - pulser, 3)

    dispenser = resolve_by_id_or_code(db, Dispenser, payload.get("dispenser_id"))

    tx = FuelTransaction(
        transaction_ref=reference,
        station_id=payment.station_id,
        dispenser_id=dispenser.id if dispenser else None,
        nozzle_id=payment.nozzle_id,
        payment_channel=payment.payment_method,
        payment_ref=payment.transaction_id,
        unit_price=float(payload.get("unit_price_ngn") or 0),
        requested_amount=payment.amount,
        requested_volume=round(payment.amount / (payload.get("unit_price_ngn") or 1), 2),
        dispenser_cpu_volume=cpu,
        independent_pulser_volume=pulser,
        raw_pulse_count=int(payload.get("raw_pulse_count") or 0),
        volume_difference=difference,
        discrepancy_alert=abs(difference) >= settings.PUMP_DISCREPANCY_THRESHOLD_L,
        total_amount_billed=float(payload.get("total_charged_ngn") or payment.amount),
        status="COMPLETED",
        started_at=_utc(),
        completed_at=_utc(),
    )
    db.add(tx)
    if tx.discrepancy_alert:
        create_alert(
            db,
            alert_type="CPU_PULSER_DISCREPANCY",
            category="FUEL_DISCREPANCY",
            severity="HIGH",
            title=f"CPU/pulser discrepancy on transaction {reference}",
            description=f"CPU {cpu} L, pulser {pulser} L, difference {difference} L.",
            station_id=payment.station_id,
            entity_type="fuel_transaction",
            entity_id=tx.id,
            expected_value=cpu,
            actual_value=pulser,
            discrepancy=difference,
        )
    db.commit()
    response = {
        "transaction_ref": reference,
        "dispensed_liters": dispensed,
        "difference_l": difference,
        "discrepancy": tx.discrepancy_alert,
    }
    record_exchange(
        direction="IN", endpoint="/api/v1/fcc/transaction/complete",
        device_uid=str(payload.get("device_uid") or ""),
        request=payload, response=response,
    )
    return response


@router.post("/device/prototype/telemetry")
def prototype_telemetry(payload: dict[str, Any], db: Session = Depends(get_db)):
    """Generic Serial-friendly telemetry intake for the prototype boards."""
    uid = str(payload.get("device_uid") or "")
    if not uid:
        raise HTTPException(400, "device_uid is required")
    event_key = str(payload.get("event_id") or uuid_hex())
    payload_hash = json.dumps(payload.get("readings") or {}, sort_keys=True)
    key = f"prototype:{uid}:{event_key}"
    existing = db.scalar(select(DeviceEvent).where(DeviceEvent.event_key == key))
    if existing is None:
        kind = str(payload.get("kind") or "PROTOTYPE").upper()
        station = db.scalar(select(FCCDevice).where(FCCDevice.device_uid == uid))
        tank = db.scalar(select(Tank).where(Tank.id == payload.get("tank_id"))) if payload.get("tank_id") else None
        if tank is None:
            controller = None
        else:
            controller = None
        db.add(DeviceEvent(
            device_uid=uid,
            device_type=kind,
            event_key=key,
            station_id=station.station_id if station else (tank.station_id if tank else None),
            event_type=kind,
            payload_hash=payload_hash,
            processing_status="ACCEPTED",
            device_timestamp=_utc(),
            detail=json.dumps(payload.get("readings") or {}),
        ))
        if tank and isinstance((payload.get("readings") or {}).get("fuel_volume_l"), (int, float)):
            tank.current_volume_l = float(payload["readings"]["fuel_volume_l"])
        db.commit()
    response = {"accepted": True, "duplicate": existing is not None, "device_uid": uid}
    record_exchange(
        direction="IN", endpoint="/api/v1/device/prototype/telemetry",
        device_uid=uid, request=payload, response=response,
    )
    return response


@router.post("/fcc/prototype/heartbeat")
def prototype_fcc_heartbeat(payload: dict[str, Any], db: Session = Depends(get_db)):
    """Bench heartbeat for the ticker. Production uses /device-ingest with a key."""
    uid = str(payload.get("device_uid") or "").strip()
    if not uid:
        raise HTTPException(400, "device_uid is required")
    device = db.scalar(select(FCCDevice).where(FCCDevice.device_uid == uid))
    if device is None:
        raise HTTPException(404, "FCC controller not found")

    now = _utc()
    device.last_heartbeat = now
    device.last_communication_at = now
    if device.status == "ACTIVE":
        device.is_online = True
    if payload.get("firmware_version"):
        device.firmware_version = str(payload["firmware_version"])[:40]
    try:
        rssi = int(payload.get("signal_strength_dbm"))
        if -150 <= rssi <= 0:
            device.signal_strength_dbm = rssi
    except (TypeError, ValueError):
        pass
    db.commit()
    response = {
        "accepted": True, "device_uid": uid, "is_online": bool(device.is_online),
        "last_seen": now.isoformat(),
    }
    record_exchange(
        direction="IN", endpoint="/api/v1/fcc/prototype/heartbeat",
        device_uid=uid, request=payload, response=response,
    )
    return response


@router.get("/fcc/calibration")
def get_fcc_calibration(device_uid: str, db: Session = Depends(get_db)):
    """Let a separate pulser ESP32 fetch pulses-per-litre set in the web MATH screen."""
    device = db.scalar(select(FCCDevice).where(FCCDevice.device_uid == device_uid))
    if device is None:
        raise HTTPException(404, "FCC controller not found")
    return {
        "device_uid": device.device_uid,
        "pulses_per_litre": float(device.calibration_factor or 0),
        "station_id": device.station_id,
        "nozzle_id": device.nozzle_id,
        "dispenser_id": device.dispenser_id,
    }


@router.patch("/fcc/calibration")
def set_fcc_calibration(payload: dict[str, Any], db: Session = Depends(get_db)):
    """Set pulses-per-litre from the Serial Monitor or the web MATH screen."""
    uid = str(payload.get("device_uid") or "").strip()
    if not uid:
        raise HTTPException(400, "device_uid is required")
    try:
        ppl = float(payload.get("pulses_per_litre"))
    except (TypeError, ValueError):
        raise HTTPException(400, "pulses_per_litre must be a number")
    if ppl <= 0:
        raise HTTPException(400, "pulses_per_litre must be greater than zero")
    device = db.scalar(select(FCCDevice).where(FCCDevice.device_uid == uid))
    if device is None:
        raise HTTPException(404, "FCC controller not found")
    device.calibration_factor = ppl
    db.commit()
    response = {
        "device_uid": uid, "pulses_per_litre": ppl,
        "formula": "litres = raw_pulse_count / pulses_per_litre",
    }
    record_exchange(
        direction="IN", endpoint="/api/v1/fcc/calibration", method="PATCH",
        device_uid=uid, request=payload, response=response,
    )
    return response


def uuid_hex() -> str:
    import uuid

    return uuid.uuid4().hex[:12]
