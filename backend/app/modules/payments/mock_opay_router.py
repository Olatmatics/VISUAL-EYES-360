"""Local OPay gateway simulator for the hardware prototype.

Mirrors the endpoints in the Sunbeth test project: payment/create, a delayed
webhook with an HMAC-SHA512 signature, and cashier/status polling. Enable with
USE_MOCK_OPAY_GATEWAY=true and MOCK_OPAY_URL pointing at this server.
"""

import asyncio
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request
import httpx

from app.core.config import settings
from app.modules.payments.opay_service import sign

router = APIRouter(prefix="/mock-opay", tags=["opay-mock"])

_orders: dict[str, dict[str, Any]] = {}


@router.post("/api/v1/international/payment/create")
async def create_payment(payload: dict[str, Any], request: Request):
    reference = str(payload.get("reference") or "")
    amount = payload.get("amount") or {}
    method = str(payload.get("payMethod") or "")
    if not reference or method not in {"Pos", "BankTransfer"}:
        return {"code": "02003", "message": "invalid request"}

    order_no = f"220{int(time.time() * 1000)}"
    record = {
        "reference": reference,
        "orderNo": order_no,
        "status": "PENDING",
        "amount": amount,
        "payMethod": method,
        "sn": payload.get("sn"),
        "callbackUrl": payload.get("callbackUrl") or settings.OPAY_WEBHOOK_URL,
    }
    _orders[reference] = record

    next_action = {"actionType": "SWIPE_CARD"}
    if method == "BankTransfer":
        next_action = {
            "actionType": "TRANSFER_ACCOUNT",
            "transferAccountNumber": "78" + str(int(time.time()))[-9:],
            "transferBankName": "WEMA BANK",
            "expiredTimestamp": int(time.time()) + 1200,
        }

    asyncio.create_task(_fire_webhook(record))
    return {
        "code": "00000",
        "message": "SUCCESSFUL",
        "data": {
            "reference": reference,
            "orderNo": order_no,
            "status": "PENDING",
            "amount": amount,
            "nextAction": next_action,
        },
    }


async def _fire_webhook(record: dict[str, Any]) -> None:
    await asyncio.sleep(3.5)
    amount = record.get("amount") or {}
    payload = {
        "reference": record["reference"],
        "transactionId": f"MOCK-{uuid.uuid4().hex[:12].upper()}",
        "orderNo": record["orderNo"],
        "amount": str(amount.get("total", 0)),
        "currency": "NGN",
        "status": "SUCCESS",
        "channel": "POS" if record.get("payMethod") == "Pos" else "BANK_TRANSFER",
        "country": "NG",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "refunded": False,
    }
    body = {"payload": payload, "sha512": sign(payload), "type": "transaction-status"}
    url = record.get("callbackUrl")
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=body)
    except Exception:
        pass
    record["status"] = "SUCCESS"


@router.post("/api/v1/international/cashier/status")
def cashier_status(payload: dict[str, Any]):
    order = _orders.get(str(payload.get("reference") or ""))
    if not order:
        return {"code": "02006", "message": "payment not found."}
    return {
        "code": "00000",
        "message": "SUCCESSFUL",
        "data": {
            "reference": order["reference"],
            "orderNo": order["orderNo"],
            "status": order["status"],
            "amount": order["amount"],
        },
    }
