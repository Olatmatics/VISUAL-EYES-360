"""OPay webhook and status endpoints for VISUAL EYES 360."""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.validation import utcnow
from app.db.base import get_db
from app.models.auth import User
from app.models.core import DeviceCommand, FCCDevice, PaymentRecord
from app.modules.hardware.service import record_exchange
from app.modules.payments.opay_service import verify_webhook

router = APIRouter(prefix="/api/v1/opay", tags=["opay"])


@router.post("/webhook")
def opay_webhook(payload: dict[str, Any], db: Session = Depends(get_db)):
    """OPay callback. No login required — authenticity is proven by signature."""
    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else None
    signature = str(payload.get("sha512") or "")
    outbound: dict[str, Any] | None = None
    result = {"code": "00000", "message": "Webhook processed", "status": ""}

    if not body:
        result = {"code": "00000", "message": "Acknowledged (malformed)"}
        record_exchange(direction="IN", endpoint="/api/v1/opay/webhook", request=payload, response=result)
        return result

    valid, authoritative = verify_webhook(body, signature)
    if not valid:
        record_exchange(
            direction="IN", endpoint="/api/v1/opay/webhook",
            request=payload, response={"detail": "Signature verification failed"}, status_code=401,
        )
        raise HTTPException(status_code=401, detail="Signature verification failed")

    reference = str(authoritative.get("reference") or "")
    payment = db.scalar(select(PaymentRecord).where(PaymentRecord.reference == reference))
    if payment is None:
        result = {"code": "00000", "message": "Acknowledged (unknown reference)"}
        record_exchange(direction="IN", endpoint="/api/v1/opay/webhook", request=payload, response=result)
        return result

    status = str(authoritative.get("status") or "").upper()
    result["status"] = status
    if status == "SUCCESS" and payment.status != "VERIFIED":
        payment.status = "VERIFIED"
        payment.authorized_at = utcnow()
        if payment.nozzle_id:
            fcc = db.scalar(select(FCCDevice).where(FCCDevice.nozzle_id == payment.nozzle_id))
            if fcc:
                command_payload = {
                    "reference": reference,
                    "status": "APPROVED",
                    "amount_ngn": payment.amount,
                    "payment_method": payment.payment_method,
                    "gateway_ref": authoritative.get("transactionId") or authoritative.get("orderNo"),
                    "timestamp": utcnow().isoformat(),
                    "message": "Payment confirmed. Open valve.",
                }
                db.add(DeviceCommand(
                    device_uid=fcc.device_uid,
                    command_type="PAYMENT_SUCCESS",
                    payload_json=json.dumps(command_payload),
                ))
                outbound = {"device_uid": fcc.device_uid, "type": "PAYMENT_SUCCESS", "payload": command_payload}
    elif status in {"FAIL", "FAILED", "CANCELLED"} and payment.status not in {"FAILED", "REFUNDED"}:
        payment.status = "FAILED"
        if payment.nozzle_id:
            fcc = db.scalar(select(FCCDevice).where(FCCDevice.nozzle_id == payment.nozzle_id))
            if fcc:
                command_payload = {
                    "reference": reference,
                    "status": "DECLINED",
                    "error": authoritative.get("displayedFailure") or "Payment declined",
                }
                db.add(DeviceCommand(
                    device_uid=fcc.device_uid,
                    command_type="PAYMENT_FAILED",
                    payload_json=json.dumps(command_payload),
                ))
                outbound = {"device_uid": fcc.device_uid, "type": "PAYMENT_FAILED", "payload": command_payload}

    db.commit()
    record_exchange(direction="IN", endpoint="/api/v1/opay/webhook", request=payload, response=result)
    if outbound:
        record_exchange(
            direction="OUT", endpoint="/api/v1/opay/webhook → device command",
            device_uid=outbound["device_uid"], request=outbound,
            response={"queued": True, "collected_by": "GET /api/v1/fcc/commands/poll"},
        )
    return result


@router.get("/status")
def opay_status(reference: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from app.modules.payments.opay_service import query_status

    local = db.scalar(select(PaymentRecord).where(PaymentRecord.reference == reference))
    gateway = query_status(reference)
    return {
        "local_status": local.status if local else None,
        "gateway": gateway.get("data") or {"code": gateway.get("code")},
    }
