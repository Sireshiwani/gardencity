from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models import Appointment, Expense, Payment, Sale, Service, User


class Command(BaseCommand):
    help = "Create demo users, services, sales, expenses, and appointments."

    def handle(self, *args, **options):
        admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "full_name": "Garden City Fine Cuts Admin",
                "email": "admin@gardencity.local",
                "role": User.Roles.ADMIN,
                "commission_rate": Decimal("0.00"),
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin.set_password("Admin123!")
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()

        manager, _ = User.objects.get_or_create(
            username="manager",
            defaults={
                "full_name": "Operations Manager",
                "email": "manager@gardencity.local",
                "role": User.Roles.MANAGER,
                "commission_rate": Decimal("10.00"),
                "is_staff": True,
            },
        )
        manager.set_password("Manager123!")
        manager.is_staff = True
        manager.save()

        barber, _ = User.objects.get_or_create(
            username="barber",
            defaults={
                "full_name": "Marcus Cole",
                "email": "barber@gardencity.local",
                "role": User.Roles.STAFF,
                "commission_rate": Decimal("40.00"),
            },
        )
        barber.set_password("Barber123!")
        barber.save()

        services = [
            {"name": "Signature Fade", "category": "haircut", "price": Decimal("35.00"), "duration_minutes": 45},
            {"name": "Beard Sculpt", "category": "beard", "price": Decimal("20.00"), "duration_minutes": 30},
            {"name": "Executive Grooming", "category": "grooming", "price": Decimal("55.00"), "duration_minutes": 60},
        ]
        service_objects = []
        for item in services:
            service, _ = Service.objects.get_or_create(
                name=item["name"],
                defaults={
                    "category": item["category"],
                    "description": "Premium precision service tailored to the client.",
                    "price": item["price"],
                    "duration_minutes": item["duration_minutes"],
                    "is_active": True,
                },
            )
            service_objects.append(service)

        now = timezone.now()
        Sale.objects.get_or_create(
            service=service_objects[0],
            staff=barber,
            price=Decimal("35.00"),
            payment_method="card",
            date=now - timedelta(hours=3),
        )
        Sale.objects.get_or_create(
            service=service_objects[1],
            staff=barber,
            price=Decimal("20.00"),
            payment_method="cash",
            date=now - timedelta(days=1),
        )
        Sale.objects.get_or_create(
            service=service_objects[2],
            staff=manager,
            price=Decimal("55.00"),
            payment_method="transfer",
            date=now - timedelta(days=2),
        )

        Expense.objects.get_or_create(
            category="Supplies",
            amount=Decimal("80.00"),
            description="Clippers, blades, and sanitizing materials",
            date=timezone.localdate() - timedelta(days=1),
        )
        Expense.objects.get_or_create(
            category="Utilities",
            amount=Decimal("140.00"),
            description="Electricity and water",
            date=timezone.localdate() - timedelta(days=3),
        )

        Payment.objects.get_or_create(
            staff=barber,
            amount=Decimal("120.00"),
            period_start=timezone.localdate() - timedelta(days=14),
            period_end=timezone.localdate(),
        )

        Appointment.objects.get_or_create(
            customer_name="Daniel Brooks",
            customer_email="daniel@example.com",
            customer_phone="+27 82 555 0001",
            service=service_objects[0],
            staff=barber,
            appointment_at=now + timedelta(days=1, hours=2),
            defaults={"status": "confirmed"},
        )

        self.stdout.write(self.style.SUCCESS("Demo data created."))
