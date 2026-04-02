"""SMS facade: delegates to settings.SMS_BACKEND (pluggable providers)."""
from __future__ import annotations

import logging

from shop.models import SMSLog
from shop.services.sms_backends import get_backend

logger = logging.getLogger(__name__)


def send_sms(phone: str, body: str, *, customer=None, kind: str = "general") -> bool:
    phone = (phone or "").strip()
    if not phone:
        return False

    backend = get_backend()
    success, err = backend.send(phone, body)

    SMSLog.objects.create(
        customer=customer,
        kind=kind,
        message_body=body,
        success=success,
        error_message=(err or "")[:500] if not success else "",
    )

    if not success and err:
        logger.warning("SMS not sent (%s): %s", kind, err)

    return success
