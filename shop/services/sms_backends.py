"""
Pluggable SMS backends. Point settings.SMS_BACKEND to a dotted path.

Built-in options:
  - shop.services.sms_backends.ConsoleSMSBackend — logs only (safe default)
  - shop.services.sms_backends.TwilioSMSBackend — Twilio (install: pip install twilio)

Add your own backend by subclassing BaseSMSBackend and implementing send().
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

# (success, error_message_for_log)
SendResult = Tuple[bool, Optional[str]]


class BaseSMSBackend(ABC):
    """Override send() to integrate any provider (MessageBird, Vonage, HTTP webhook, etc.)."""

    def __init__(self, **options):
        self.options = options

    @abstractmethod
    def send(self, phone: str, body: str) -> SendResult:
        """Send SMS. Return (True, None) on success, (False, err) on failure."""


class ConsoleSMSBackend(BaseSMSBackend):
    """Development/default: does not send; logs the payload."""

    def send(self, phone: str, body: str) -> SendResult:
        logger.info("[SMS console] to=%s body=%s", phone, body[:200])
        return True, None


class TwilioSMSBackend(BaseSMSBackend):
    """Optional Twilio implementation. Requires: pip install twilio and TWILIO_* settings."""

    def send(self, phone: str, body: str) -> SendResult:
        sid = getattr(settings, "TWILIO_ACCOUNT_SID", "") or ""
        token = getattr(settings, "TWILIO_AUTH_TOKEN", "") or ""
        from_num = getattr(settings, "TWILIO_FROM_NUMBER", "") or ""

        if not (sid and token and from_num):
            return False, "Twilio credentials not configured (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER)"

        try:
            from twilio.rest import Client
        except ImportError:
            return False, "twilio package not installed (pip install twilio)"

        try:
            client = Client(sid, token)
            client.messages.create(body=body, from_=from_num, to=phone)
            return True, None
        except Exception as exc:  # noqa: BLE001
            logger.exception("Twilio SMS send failed")
            return False, str(exc)[:500]


def get_backend():
    """Instantiate the configured backend."""
    path = getattr(
        settings,
        "SMS_BACKEND",
        "shop.services.sms_backends.ConsoleSMSBackend",
    )
    opts = getattr(settings, "SMS_BACKEND_OPTIONS", None) or {}
    from django.utils.module_loading import import_string

    backend_cls = import_string(path)
    return backend_cls(**opts)
