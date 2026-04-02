from django.core.management.base import BaseCommand

from shop.services.loyalty import (
    customers_for_retention_sms,
    get_loyalty_settings,
    send_retention_sms_for_customer,
)


class Command(BaseCommand):
    help = "Send 3-week retention SMS to eligible customers (schedule daily via cron/Task Scheduler)."

    def handle(self, *args, **options):
        settings = get_loyalty_settings()
        if not settings.sms_retention_enabled:
            self.stdout.write(self.style.WARNING("SMS retention is disabled in Loyalty settings."))
            return

        days = settings.sms_retention_days
        sent = 0
        for customer in customers_for_retention_sms(days=days):
            if send_retention_sms_for_customer(customer):
                sent += 1
        self.stdout.write(self.style.SUCCESS(f"Processed retention SMS for {sent} customers (window: last visit {days} days ago)."))
