"""Notification queue and SMTP delivery.

Credentials are read exclusively from environment-backed settings. If SMTP is
not configured the message stays queued (PENDING) and the reason is recorded —
the system never reports a delivery that did not happen.
"""

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.validation import utcnow
from app.models.core import Notification

logger = logging.getLogger("ve360.mailer")


def queue_email(
    db: Session,
    *,
    recipient: str,
    subject: str,
    body: str,
    alert_id: str | None = None,
    dedupe_key: str | None = None,
) -> Notification | None:
    if dedupe_key:
        existing = db.scalar(select(Notification).where(Notification.dedupe_key == dedupe_key))
        if existing is not None:
            return existing
    notification = Notification(
        alert_id=alert_id,
        channel="EMAIL",
        recipient=recipient,
        subject=subject,
        body=body,
        status="PENDING",
        dedupe_key=dedupe_key,
    )
    db.add(notification)
    return notification


def _send_via_smtp(notification: Notification) -> None:
    message = EmailMessage()
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    message["To"] = notification.recipient
    message["Subject"] = notification.subject
    message.set_content(notification.body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        smtp.ehlo()
        if settings.SMTP_USE_TLS:
            smtp.starttls()
            smtp.ehlo()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)


def process_pending(db: Session, limit: int = 50) -> dict:
    """Attempt delivery of queued email notifications.

    Returns a summary so callers can show exactly what happened.
    """
    pending = db.scalars(
        select(Notification)
        .where(Notification.channel == "EMAIL", Notification.status == "PENDING")
        .order_by(Notification.created_at)
        .limit(limit)
    ).all()

    summary = {"attempted": len(pending), "sent": 0, "failed": 0, "skipped": 0}
    if not pending:
        return summary

    if not settings.smtp_configured:
        for item in pending:
            item.status = "SKIPPED"
            item.last_error = "SMTP is not configured (set SMTP_HOST and SMTP_FROM_EMAIL)"
            summary["skipped"] += 1
        db.commit()
        return summary

    for item in pending:
        item.attempts = (item.attempts or 0) + 1
        try:
            _send_via_smtp(item)
            item.status = "SENT"
            item.sent_at = utcnow()
            item.last_error = None
            summary["sent"] += 1
        except Exception as exc:  # pragma: no cover - depends on external SMTP
            logger.warning("Email delivery failed for %s: %s", item.id, exc)
            item.status = "FAILED"
            item.last_error = str(exc)[:1000]
            summary["failed"] += 1
    db.commit()
    return summary
