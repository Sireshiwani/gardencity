"""Customer get/create helpers for bookings and registration."""
from __future__ import annotations

from shop.models import Customer
from shop.services.loyalty import generate_referral_code


def split_name(full_name: str) -> tuple[str, str]:
    parts = (full_name or "").strip().split(None, 1)
    if not parts:
        return "Guest", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def get_or_create_from_booking(
    *, full_name: str, email: str | None, phone: str, referral_code: str | None = None
) -> Customer:
    phone_norm = phone.strip()
    first, last = split_name(full_name)

    referrer = None
    code = (referral_code or "").strip().upper()
    if code:
        referrer = Customer.objects.filter(referral_code__iexact=code).first()

    raw_email = (email or "").strip()
    email_norm = raw_email.lower() if raw_email else ""

    if email_norm:
        customer, created = Customer.objects.get_or_create(
            email=email_norm,
            defaults={
                "phone": phone_norm,
                "first_name": first,
                "last_name": last,
                "referral_code": generate_referral_code(),
                "referred_by": referrer,
            },
        )
    else:
        existing = Customer.objects.filter(phone=phone_norm).first()
        if existing:
            customer = existing
            created = False
        else:
            customer = Customer.objects.create(
                email=None,
                phone=phone_norm,
                first_name=first,
                last_name=last,
                referral_code=generate_referral_code(),
                referred_by=referrer,
            )
            created = True

    if not created:
        Customer.objects.filter(pk=customer.pk).update(
            phone=phone_norm or customer.phone,
            first_name=first or customer.first_name,
            last_name=last or customer.last_name,
        )
        customer.refresh_from_db()
    return customer
