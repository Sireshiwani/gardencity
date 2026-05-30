from django.conf import settings

from shop.models import SaleChangeRequest, StaffNotification, User


def currency(request):
    return {"CURRENCY": getattr(settings, "SITE_CURRENCY", "Kshs")}


def notifications(request):
    unread_notification_count = 0
    pending_sale_change_count = 0
    if request.user.is_authenticated:
        unread_notification_count = StaffNotification.objects.filter(
            user=request.user,
            read_at__isnull=True,
        ).count()
        if getattr(request.user, "role", None) == User.Roles.ADMIN:
            pending_sale_change_count = SaleChangeRequest.objects.filter(
                status=SaleChangeRequest.Status.PENDING,
            ).count()
    return {
        "unread_notification_count": unread_notification_count,
        "pending_sale_change_count": pending_sale_change_count,
    }
