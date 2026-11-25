"""OPay POS gateway integration, ported from the working Sunbeth prototype.

Signing contract (verified in that project):
  - recursively sort every object key alphabetically
  - JSON-serialize compactly (no whitespace)
  - HMAC-SHA512 with the OPay private key, lowercase hex
  - send as `Authorization: Bearer <signature>` with `MerchantId`

Secrets come only from environment-backed settings. Nothing sensitive is logged.
"""

import hashlib
import hmac
import json
from typing import Any

import httpx

from app.core.config import settings


def sort_keys(value: Any) -> Any:
    if value is None or not isinstance(value, (dict, list)):
        return value
    if isinstance(value, list):
        return [sort_keys(item) for item in value]
    return {key: sort_keys(value[key]) for key in sorted(value)}


def sign(payload: Any) -> str:
    serialized = json.dumps(sort_keys(payload), separators=(",", ":"), ensure_ascii=False)
    return hmac.new(
        settings.OPAY_PRIVATE_KEY.encode(), serialized.encode("utf-8"), hashlib.sha512
    ).hexdigest()


def _base_url() -> str:
    return settings.MOCK_OPAY_URL if settings.USE_MOCK_OPAY_GATEWAY else settings.OPAY_BASE_URL


def _post(path: str, body: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
        "MerchantId": settings.OPAY_MERCHANT_ID,
        "Authorization": f"Bearer {sign(body)}",
    }
    with httpx.Client(timeout=15.0) as client:
        response = client.post(f"{_base_url()}{path}", json=body, headers=headers)
    try:
        return response.json()
    except ValueError:
        return {"code": str(response.status_code), "message": "Non-JSON response", "raw": response.text[:200]}


def create_pos_payment(
    reference: str,
    amount_kobo: int,
    pos_sn: str,
    callback_url: str | None = None,
    product_name: str = "Fuel Dispense",
    description: str = "Fuel station transaction",
    expire_minutes: int = 15,
    customer_name: str = "Pump Customer",
) -> dict:
    body = {
        "reference": reference,
        "amount": {"currency": "NGN", "total": amount_kobo},
        "payMethod": "Pos",
        "sn": pos_sn,
        "country": "NG",
        "customerName": customer_name,
        "callbackUrl": callback_url or settings.OPAY_WEBHOOK_URL,
        "product": {"name": product_name, "description": description},
        "expireAt": expire_minutes,
    }
    return _post("/api/v1/international/payment/create", body)


def create_bank_transfer(
    reference: str,
    amount_kobo: int,
    callback_url: str | None = None,
    product_name: str = "Fuel Dispense",
    description: str = "Fuel station transaction",
    expire_minutes: int = 20,
) -> dict:
    body = {
        "reference": reference,
        "amount": {"currency": "NGN", "total": amount_kobo},
        "payMethod": "BankTransfer",
        "country": "NG",
        "callbackUrl": callback_url or settings.OPAY_WEBHOOK_URL,
        "product": {"name": product_name, "description": description},
        "expireAt": expire_minutes,
    }
    return _post("/api/v1/international/payment/create", body)


def query_status(reference: str) -> dict:
    return _post("/api/v1/international/cashier/status", {"reference": reference, "country": "NG"})


def verify_webhook(payload: dict, received_signature: str) -> tuple[bool, dict]:
    """Return (is_valid, authoritative_payload).

    Signature is checked first. If it fails or the gateway is unavailable, the
    status API is queried directly, as the prototype did.
    """
    authoritative = dict(payload)
    computed = sign(payload)
    valid = hmac.compare_digest(computed.lower(), (received_signature or "").lower())

    if not valid and payload.get("reference"):
        try:
            status = query_status(payload["reference"])
            data = status.get("data") or {}
            if status.get("code") == "00000" and (data.get("orderNo") or data.get("status")):
                authoritative["status"] = data.get("status", authoritative.get("status"))
                authoritative["orderNo"] = data.get("orderNo", authoritative.get("orderNo"))
                if data.get("displayedFailure") or data.get("errorMsg"):
                    authoritative["displayedFailure"] = data.get("displayedFailure") or data.get("errorMsg")
                valid = True
        except Exception:
            valid = False
    return valid, authoritative
