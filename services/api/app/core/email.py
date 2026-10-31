"""Outgoing email. SMTP in real deployments (Mailpit in development)."""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

import anyio

from app.core.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class SentEmail:
    to: str
    subject: str
    body: str


# Filled only by the "memory" backend, which the tests use.
outbox: list[SentEmail] = []


def _send_smtp(message: EmailMessage) -> None:
    settings = get_settings()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


async def send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if settings.email_backend == "memory":
        outbox.append(SentEmail(to, subject, body))
        return
    if settings.email_backend == "console":
        log.info("email to=%s subject=%s\n%s", to, subject, body)
        return

    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    await anyio.to_thread.run_sync(_send_smtp, message)
