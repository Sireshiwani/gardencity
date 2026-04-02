from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models import Appointment
from shop.services.loyalty import get_loyalty_settings, send_review_nudge_for_appointment


class Command(BaseCommand):
    help = "Send review reminder SMS ~24h after completed appointments (run hourly or daily)."

    def handle(self, *args, **options):
        settings = get_loyalty_settings()
        if not settings.review_request_enabled:
            self.stdout.write(self.style.WARNING("Review nudges are disabled in Loyalty settings."))
            return

        hours = settings.review_request_hours_after
        now = timezone.now()
        window_start = now - timedelta(hours=hours + 1)
        window_end = now - timedelta(hours=max(hours - 1, 0))

        qs = Appointment.objects.filter(
            status=Appointment.Status.COMPLETED,
            completed_at__isnull=False,
            completed_at__gte=window_start,
            completed_at__lte=window_end,
        ).select_related("customer")

        sent = 0
        for appt in qs:
            if send_review_nudge_for_appointment(appt):
                sent += 1
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} review reminder(s)."))
