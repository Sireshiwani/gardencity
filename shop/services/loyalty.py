"""Loyalty points, referrals, slow-hour multipliers, and tier updates."""
from __future__ import annotations

import secrets
import string
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from shop.models import (
    Appointment,
    Customer,
    LoyaltySettings,
    PointsLedger,
    ReferralCredit,
    Sale,
    SlowHourWindow,
)


def format_sms_template(template: str, **kwargs) -> str:
    """Fill {placeholders} in template; unknown keys left as literal."""
    try:
        return template.format(**kwargs)
    except Exception:  # noqa: BLE001
        return template


def get_loyalty_settings() -> LoyaltySettings:
    obj, _ = LoyaltySettings.objects.get_or_create(
        pk=1,
        defaults={
            "points_per_visit": 50,
            "points_per_dollar": Decimal("1.00"),
            "referral_bonus_referrer": 100,
            "referral_bonus_referee": 50,
        },
    )
    return obj


def generate_referral_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        if not Customer.objects.filter(referral_code=code).exists():
            return code
    return secrets.token_hex(4).upper()


def tier_for_points(points: int) -> str:
    if points >= 5000:
        return Customer.Tier.GOLD
    if points >= 1500:
        return Customer.Tier.SILVER
    return Customer.Tier.BRONZE


def _weekday_local(dt) -> int:
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return timezone.localtime(dt).weekday()


def _time_local(dt):
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return timezone.localtime(dt).time()


def slow_hour_multiplier_for_datetime(dt) -> Decimal:
    wd = _weekday_local(dt)
    t = _time_local(dt)
    best = Decimal("1.00")
    for window in SlowHourWindow.objects.filter(enabled=True):
        if window.weekday_start <= wd <= window.weekday_end:
            if window.time_start <= t <= window.time_end:
                if window.multiplier > best:
                    best = window.multiplier
    return best


@transaction.atomic
def append_ledger(
    customer: Customer,
    *,
    points_delta: int,
    entry_type: str,
    description: str = "",
    appointment=None,
    sale=None,
    multiplier_applied: Decimal = Decimal("1.000"),
) -> PointsLedger:
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    new_balance = max(0, customer.points_balance + points_delta)
    entry = PointsLedger.objects.create(
        customer=customer,
        points_delta=points_delta,
        balance_after=new_balance,
        entry_type=entry_type,
        description=description[:500],
        appointment=appointment,
        sale=sale,
        multiplier_applied=multiplier_applied,
    )
    customer.points_balance = new_balance
    customer.tier = tier_for_points(new_balance)
    customer.save(update_fields=["points_balance", "tier", "updated_at"])
    return entry


def award_points_for_completed_appointment(appointment: Appointment) -> None:
    if appointment.status != Appointment.Status.COMPLETED:
        return
    if not appointment.customer_id:
        return
    if PointsLedger.objects.filter(appointment=appointment, entry_type=PointsLedger.EntryType.VISIT).exists():
        return

    settings = get_loyalty_settings()
    customer = appointment.customer
    linked_sale = Sale.objects.filter(appointment=appointment).order_by("-date").first()
    spend_amount = linked_sale.price if linked_sale else appointment.service.price

    mult = slow_hour_multiplier_for_datetime(appointment.appointment_at)

    visit_pts = int(settings.points_per_visit * mult)
    spend_pts = int((spend_amount * settings.points_per_dollar) * mult)

    append_ledger(
        customer,
        points_delta=visit_pts,
        entry_type=PointsLedger.EntryType.VISIT,
        description=f"Visit bonus (x{mult})",
        appointment=appointment,
        multiplier_applied=mult,
    )
    append_ledger(
        customer,
        points_delta=spend_pts,
        entry_type=PointsLedger.EntryType.SPEND,
        description=f"Spend bonus on Kshs {spend_amount} (x{mult})",
        appointment=appointment,
        sale=linked_sale,
        multiplier_applied=mult,
    )

    now = timezone.now()
    customer.last_visit_at = now
    customer.save(update_fields=["last_visit_at", "updated_at"])

    _maybe_award_referral_bonus(customer, appointment)


def _maybe_award_referral_bonus(customer: Customer, appointment: Appointment) -> None:
    if not customer.referred_by_id:
        return
    if ReferralCredit.objects.filter(referee=customer).exists():
        return

    settings = get_loyalty_settings()
    referrer = customer.referred_by
    append_ledger(
        referrer,
        points_delta=settings.referral_bonus_referrer,
        entry_type=PointsLedger.EntryType.REFERRAL_REFERRER,
        description="Referral bonus (referrer)",
        appointment=appointment,
    )
    append_ledger(
        customer,
        points_delta=settings.referral_bonus_referee,
        entry_type=PointsLedger.EntryType.REFERRAL_REFEREE,
        description="Referral bonus (new customer)",
        appointment=appointment,
    )
    ReferralCredit.objects.create(
        referrer=referrer,
        referee=customer,
        appointment=appointment,
    )


def award_points_for_sale(sale: Sale) -> None:
    """Walk-in / sale-only: no linked appointment."""
    if not sale.customer_id:
        return
    if sale.appointment_id:
        return
    if PointsLedger.objects.filter(sale=sale).exists():
        return

    settings = get_loyalty_settings()
    mult = slow_hour_multiplier_for_datetime(sale.date)
    spend_pts = int((sale.price * settings.points_per_dollar) * mult)
    append_ledger(
        sale.customer,
        points_delta=spend_pts,
        entry_type=PointsLedger.EntryType.SPEND,
        description=f"Walk-in sale Kshs {sale.price} (x{mult})",
        sale=sale,
        multiplier_applied=mult,
    )


def customers_for_retention_sms(*, days: int):
    today = timezone.localdate()
    target = today - timedelta(days=days)
    qs = Customer.objects.filter(sms_opt_out=False, last_visit_at__date=target)
    upcoming_ids = set(
        Appointment.objects.filter(
            status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED],
            appointment_at__gte=timezone.now(),
            customer_id__isnull=False,
        ).values_list("customer_id", flat=True)
    )
    return [c for c in qs if c.pk not in upcoming_ids]


def send_retention_sms_for_customer(customer: Customer) -> bool:
    from shop.services import sms as sms_mod

    settings = get_loyalty_settings()
    if not settings.sms_retention_enabled:
        return False
    link = settings.booking_base_url or "/book/"
    weeks = max(1, settings.sms_retention_days // 7)
    body = format_sms_template(
        settings.retention_sms_template,
        first_name=customer.first_name,
        shop_name=settings.shop_display_name,
        booking_link=link,
        weeks=weeks,
        retention_days=settings.sms_retention_days,
    )
    return sms_mod.send_sms(customer.phone, body, customer=customer, kind="retention")


def send_review_nudge_for_appointment(appointment: Appointment) -> bool:
    from shop.models import ReviewNudge
    from shop.services import sms as sms_mod

    settings = get_loyalty_settings()
    if not settings.review_request_enabled or not appointment.customer_id:
        return False
    if hasattr(appointment, "review_nudge"):
        return False

    cust = appointment.customer
    bonus = settings.review_bonus_points
    body = format_sms_template(
        settings.review_sms_template,
        first_name=cust.first_name,
        shop_name=settings.shop_display_name,
        review_bonus_points=bonus,
    )
    ok = sms_mod.send_sms(cust.phone, body, customer=cust, kind="review")
    if ok:
        ReviewNudge.objects.create(appointment=appointment, customer=cust, channel="sms")
    return ok
