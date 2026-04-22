"""SMTP delivery with in-memory test double."""
from __future__ import annotations

import base64
import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol, runtime_checkable

from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

_SMTP_RETRY_WAIT = None  # tests monkeypatch to tenacity.wait_none() to skip sleeps


def _smtp_retry() -> Retrying:
    wait = _SMTP_RETRY_WAIT if _SMTP_RETRY_WAIT is not None else wait_exponential(
        multiplier=1, min=1, max=16,
    )
    return Retrying(
        retry=retry_if_exception_type((smtplib.SMTPException, OSError)),
        stop=stop_after_attempt(3),
        wait=wait,
        reraise=True,
    )


def _encode_subject(subject: str) -> str:
    if subject.isascii():
        return subject
    encoded = base64.b64encode(subject.encode("utf-8")).decode("ascii")
    return f"=?utf-8?b?{encoded}?="


def build_message(*, sender: str, to: str, subject: str, html: str) -> bytes:
    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = _encode_subject(subject)
    plain = MIMEText(
        "This is an HTML email. Please view it in an HTML-capable client.",
        "plain",
        "utf-8",
    )
    html_part = MIMEText(html, "html", "utf-8")
    msg.attach(plain)
    msg.attach(html_part)
    return msg.as_bytes()


@runtime_checkable
class Mailer(Protocol):
    def send(self, *, sender: str, to: str, subject: str, html: str) -> None: ...


@dataclass
class SentMessage:
    sender: str
    to: str
    subject: str
    html: str


@dataclass
class InMemoryMailer:
    sent: list[SentMessage] = field(default_factory=list)

    def send(self, *, sender: str, to: str, subject: str, html: str) -> None:
        self.sent.append(SentMessage(sender, to, subject, html))


class SMTPMailer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        use_ssl: bool | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_ssl = bool(port == 465) if use_ssl is None else use_ssl

    def send(self, *, sender: str, to: str, subject: str, html: str) -> None:
        for attempt in _smtp_retry():
            with attempt:
                self._send_once(sender=sender, to=to, subject=subject, html=html)
                return

    def _send_once(self, *, sender: str, to: str, subject: str, html: str) -> None:
        payload = build_message(sender=sender, to=to, subject=subject, html=html)
        ctx = ssl.create_default_context()
        if self.use_ssl:
            with smtplib.SMTP_SSL(self.host, self.port, context=ctx, timeout=30) as s:
                s.login(self.user, self.password)
                s.sendmail(sender, [to], payload)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=30) as s:
                s.starttls(context=ctx)
                s.login(self.user, self.password)
                s.sendmail(sender, [to], payload)
        logger.info("email sent to=%s subject=%s", to, subject)
