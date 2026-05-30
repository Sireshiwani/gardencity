from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from shop.models import Customer, Sale, SaleChangeRequest, StaffNotification, User
from shop.services.loyalty import generate_referral_code


def sale_manager_edit_window() -> timedelta:
    hours = getattr(settings, "SALE_MANAGER_EDIT_WINDOW_HOURS", 72)
    return timedelta(hours=hours)


def manager_may_edit_sale_directly(sale: Sale) -> bool:
    if not sale.created_at:
        return True
    return timezone.now() < sale.created_at + sale_manager_edit_window()


def manager_edit_deadline(sale: Sale):
    if not sale.created_at:
        return timezone.now() + sale_manager_edit_window()
    return sale.created_at + sale_manager_edit_window()


def get_pending_change_request(sale: Sale):
    return (
        sale.change_requests.filter(status=SaleChangeRequest.Status.PENDING)
        .select_related("requested_by")
        .first()
    )


def create_notification(user, message, *, link="", change_request=None):
    return StaffNotification.objects.create(
        user=user,
        message=message,
        link=link,
        change_request=change_request,
    )


def notify_admins_change_submitted(change_request: SaleChangeRequest):
    sale = change_request.sale
    link = reverse("sale-change-review", kwargs={"pk": change_request.pk})
    message = (
        f"{change_request.requested_by.full_name} submitted a change request "
        f"for sale #{sale.pk} ({sale.service.name})."
    )
    admins = User.objects.filter(role=User.Roles.ADMIN, is_active=True)
    for admin in admins:
        create_notification(admin, message, link=link, change_request=change_request)


def notify_requester_decision(change_request: SaleChangeRequest, *, approved: bool):
    sale = change_request.sale
    link = reverse("sale-update", kwargs={"pk": sale.pk})
    if approved:
        message = f"Your change request for sale #{sale.pk} was approved."
    else:
        detail = change_request.admin_notes.strip() or "No reason provided."
        message = f"Your change request for sale #{sale.pk} was rejected. {detail}"
    create_notification(change_request.requested_by, message, link=link, change_request=change_request)


def notify_requester_cancelled(change_request: SaleChangeRequest, *, note: str):
    sale = change_request.sale
    link = reverse("sale-list")
    message = f"Your pending change request for sale #{sale.pk} was cancelled. {note}".strip()
    create_notification(change_request.requested_by, message, link=link, change_request=change_request)


def _close_pending_requests(sale, *, by_user, status, note, notify_requester=False):
    pending = sale.change_requests.filter(status=SaleChangeRequest.Status.PENDING)
    for req in pending:
        req.status = status
        req.reviewed_by = by_user if by_user.role == User.Roles.ADMIN else None
        req.reviewed_at = timezone.now()
        req.admin_notes = note
        req.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_notes"])
        if notify_requester and req.requested_by_id != getattr(by_user, "id", None):
            notify_requester_cancelled(req, note=note)


def supersede_pending_requests(sale, by_user):
    _close_pending_requests(
        sale,
        by_user=by_user,
        status=SaleChangeRequest.Status.SUPERSEDED,
        note="Replaced by a newer change request.",
        notify_requester=True,
    )


def cancel_pending_requests_for_admin_edit(sale, admin_user):
    _close_pending_requests(
        sale,
        by_user=admin_user,
        status=SaleChangeRequest.Status.CANCELLED,
        note="An admin updated the sale directly.",
        notify_requester=True,
    )


def _apply_customer_from_request(sale: Sale, change_request: SaleChangeRequest):
    if change_request.customer_id:
        sale.customer = change_request.customer
        return
    fn = (change_request.new_first_name or "").strip()
    ph = (change_request.new_phone or "").strip()
    em = (change_request.new_email or "").strip()
    if fn and ph:
        sale.customer = Customer.objects.create(
            email=em.lower() if em else None,
            phone=ph,
            first_name=fn,
            last_name=(change_request.new_last_name or "").strip(),
            referral_code=generate_referral_code(),
        )


def apply_sale_cleaned_data(sale: Sale, cleaned_data):
    sale.service = cleaned_data["service"]
    sale.appointment = cleaned_data.get("appointment")
    sale.staff = cleaned_data.get("staff")
    sale.price = cleaned_data["price"]
    sale.payment_method = cleaned_data["payment_method"]
    sale.date = cleaned_data["date"]
    sale.notes = cleaned_data.get("notes") or ""

    existing = cleaned_data.get("customer")
    fn = (cleaned_data.get("new_first_name") or "").strip()
    ph = (cleaned_data.get("new_phone") or "").strip()
    em = (cleaned_data.get("new_email") or "").strip()
    if existing:
        sale.customer = existing
    elif fn and ph:
        sale.customer = Customer.objects.create(
            email=em.lower() if em else None,
            phone=ph,
            first_name=fn,
            last_name=(cleaned_data.get("new_last_name") or "").strip(),
            referral_code=generate_referral_code(),
        )
    sale.save()


def create_change_request_from_form(sale, form, user, reason):
    supersede_pending_requests(sale, user)
    change_request = SaleChangeRequest.objects.create(
        sale=sale,
        requested_by=user,
        reason=reason.strip(),
        sale_updated_at_snapshot=sale.updated_at,
        service=form.cleaned_data["service"],
        customer=form.cleaned_data.get("customer"),
        appointment=form.cleaned_data.get("appointment"),
        staff=form.cleaned_data.get("staff"),
        price=form.cleaned_data["price"],
        payment_method=form.cleaned_data["payment_method"],
        date=form.cleaned_data["date"],
        notes=form.cleaned_data.get("notes") or "",
        new_first_name=(form.cleaned_data.get("new_first_name") or "").strip(),
        new_last_name=(form.cleaned_data.get("new_last_name") or "").strip(),
        new_email=(form.cleaned_data.get("new_email") or "").strip(),
        new_phone=(form.cleaned_data.get("new_phone") or "").strip(),
    )
    notify_admins_change_submitted(change_request)
    return change_request


@transaction.atomic
def approve_change_request(change_request: SaleChangeRequest, admin_user):
    sale = Sale.objects.select_for_update().get(pk=change_request.sale_id)
    if change_request.status != SaleChangeRequest.Status.PENDING:
        return False, "This request is no longer pending."
    if sale.updated_at != change_request.sale_updated_at_snapshot:
        change_request.status = SaleChangeRequest.Status.REJECTED
        change_request.reviewed_by = admin_user
        change_request.reviewed_at = timezone.now()
        change_request.admin_notes = "Approval failed because the sale changed after this request was submitted."
        change_request.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "admin_notes"]
        )
        notify_requester_decision(change_request, approved=False)
        return False, change_request.admin_notes

    sale.service = change_request.service
    sale.appointment = change_request.appointment
    sale.staff = change_request.staff
    sale.price = change_request.price
    sale.payment_method = change_request.payment_method
    sale.date = change_request.date
    sale.notes = change_request.notes
    _apply_customer_from_request(sale, change_request)
    sale.save()

    change_request.status = SaleChangeRequest.Status.APPROVED
    change_request.reviewed_by = admin_user
    change_request.reviewed_at = timezone.now()
    change_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    notify_requester_decision(change_request, approved=True)
    return True, None


@transaction.atomic
def reject_change_request(change_request: SaleChangeRequest, admin_user, admin_notes=""):
    if change_request.status != SaleChangeRequest.Status.PENDING:
        return False, "This request is no longer pending."
    change_request.status = SaleChangeRequest.Status.REJECTED
    change_request.reviewed_by = admin_user
    change_request.reviewed_at = timezone.now()
    change_request.admin_notes = admin_notes.strip()
    change_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_notes"])
    notify_requester_decision(change_request, approved=False)
    return True, None
