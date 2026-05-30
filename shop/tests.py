from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from shop.models import Appointment, Sale, SaleChangeRequest, Service, StaffNotification, User
from shop.services.sale_changes import approve_change_request, manager_may_edit_sale_directly
from shop.views import appointments_for_user


class AppointmentsForUserTests(TestCase):
    def setUp(self):
        self.service = Service.objects.create(
            name="Classic Cut",
            category="haircut",
            price="500.00",
        )
        self.admin = User.objects.create_user(
            username="admin2",
            password="Admin123!",
            full_name="Admin User",
            email="admin2@example.com",
            role=User.Roles.ADMIN,
        )
        self.manager = User.objects.create_user(
            username="manager2",
            password="Manager123!",
            full_name="Manager User",
            email="manager2@example.com",
            role=User.Roles.MANAGER,
        )
        self.staff_a = User.objects.create_user(
            username="barber_a",
            password="Barber123!",
            full_name="Barber A",
            email="barbera@example.com",
            role=User.Roles.STAFF,
        )
        self.staff_b = User.objects.create_user(
            username="barber_b",
            password="Barber123!",
            full_name="Barber B",
            email="barberb@example.com",
            role=User.Roles.STAFF,
        )
        when = timezone.now() + timedelta(days=1)
        self.appt_a = Appointment.objects.create(
            customer_name="Client A",
            customer_phone="0700000001",
            service=self.service,
            staff=self.staff_a,
            appointment_at=when,
        )
        self.appt_b = Appointment.objects.create(
            customer_name="Client B",
            customer_phone="0700000002",
            service=self.service,
            staff=self.staff_b,
            appointment_at=when + timedelta(hours=1),
        )

    def test_admin_sees_all_appointments(self):
        ids = set(appointments_for_user(self.admin).values_list("pk", flat=True))
        self.assertEqual(ids, {self.appt_a.pk, self.appt_b.pk})

    def test_manager_sees_all_appointments(self):
        ids = set(appointments_for_user(self.manager).values_list("pk", flat=True))
        self.assertEqual(ids, {self.appt_a.pk, self.appt_b.pk})

    def test_staff_sees_only_own_appointments(self):
        ids = set(appointments_for_user(self.staff_a).values_list("pk", flat=True))
        self.assertEqual(ids, {self.appt_a.pk})

    def test_staff_booking_page_lists_only_own_appointments(self):
        self.client.force_login(self.staff_a)
        response = self.client.get(reverse("book-now"))
        self.assertContains(response, "Client A")
        self.assertNotContains(response, "Client B")
        self.assertContains(response, "Appointments assigned to you")

    def test_manager_booking_page_lists_all_appointments(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("book-now"))
        self.assertContains(response, "Client A")
        self.assertContains(response, "Client B")
        self.assertContains(response, "All scheduled appointments across the shop")


class SaleChangeWorkflowTests(TestCase):
    def setUp(self):
        self.service = Service.objects.create(
            name="Fade",
            category="haircut",
            price=Decimal("800.00"),
        )
        self.admin = User.objects.create_user(
            username="admin",
            password="Admin123!",
            full_name="Admin User",
            email="admin@example.com",
            role=User.Roles.ADMIN,
        )
        self.manager = User.objects.create_user(
            username="manager",
            password="Manager123!",
            full_name="Manager User",
            email="manager@example.com",
            role=User.Roles.MANAGER,
        )
        self.staff = User.objects.create_user(
            username="barber",
            password="Barber123!",
            full_name="Barber User",
            email="barber@example.com",
            role=User.Roles.STAFF,
        )
        self.sale = Sale.objects.create(
            service=self.service,
            staff=self.staff,
            price=Decimal("800.00"),
            payment_method="cash",
        )

    def _post_sale_update(self, user, sale, **extra):
        data = {
            "service": self.service.pk,
            "staff": self.staff.pk,
            "price": "900.00",
            "payment_method": "cash",
            "date": timezone.localtime(sale.date).strftime("%Y-%m-%dT%H:%M"),
            "notes": "Updated",
            "customer": "",
            "appointment": "",
            "new_first_name": "",
            "new_last_name": "",
            "new_email": "",
            "new_phone": "",
        }
        data.update(extra)
        self.client.force_login(user)
        return self.client.post(reverse("sale-update", kwargs={"pk": sale.pk}), data)

    def test_manager_can_edit_within_72_hours(self):
        response = self._post_sale_update(self.manager, self.sale)
        self.assertRedirects(response, reverse("sale-list"))
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.price, Decimal("900.00"))
        self.assertFalse(
            SaleChangeRequest.objects.filter(sale=self.sale, status=SaleChangeRequest.Status.PENDING).exists()
        )

    def test_manager_after_72_hours_creates_change_request(self):
        Sale.objects.filter(pk=self.sale.pk).update(
            created_at=timezone.now() - timedelta(hours=73),
            updated_at=timezone.now() - timedelta(hours=73),
        )
        self.sale.refresh_from_db()
        self.assertFalse(manager_may_edit_sale_directly(self.sale))

        response = self._post_sale_update(
            self.manager,
            self.sale,
            change_reason="Correcting price after client dispute",
        )
        self.assertRedirects(response, reverse("sale-list"))
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.price, Decimal("800.00"))

        change = SaleChangeRequest.objects.get(sale=self.sale, status=SaleChangeRequest.Status.PENDING)
        self.assertEqual(change.price, Decimal("900.00"))
        self.assertEqual(change.reason, "Correcting price after client dispute")
        self.assertTrue(
            StaffNotification.objects.filter(user=self.admin, change_request=change).exists()
        )

    def test_new_request_supersedes_previous_pending_request(self):
        Sale.objects.filter(pk=self.sale.pk).update(
            created_at=timezone.now() - timedelta(hours=80),
            updated_at=timezone.now() - timedelta(hours=80),
        )
        self.sale.refresh_from_db()
        self._post_sale_update(self.manager, self.sale, change_reason="First request", price="910.00")
        first = SaleChangeRequest.objects.get(sale=self.sale, status=SaleChangeRequest.Status.PENDING)
        self._post_sale_update(self.manager, self.sale, change_reason="Second request", price="920.00")
        first.refresh_from_db()
        self.assertEqual(first.status, SaleChangeRequest.Status.SUPERSEDED)
        second = SaleChangeRequest.objects.get(sale=self.sale, status=SaleChangeRequest.Status.PENDING)
        self.assertEqual(second.price, Decimal("920.00"))

    def test_stale_approval_fails_if_sale_changed(self):
        Sale.objects.filter(pk=self.sale.pk).update(
            created_at=timezone.now() - timedelta(hours=80),
            updated_at=timezone.now() - timedelta(hours=80),
        )
        self.sale.refresh_from_db()
        self._post_sale_update(self.manager, self.sale, change_reason="Need correction", price="950.00")
        change = SaleChangeRequest.objects.get(sale=self.sale, status=SaleChangeRequest.Status.PENDING)

        Sale.objects.filter(pk=self.sale.pk).update(
            price=Decimal("850.00"),
            updated_at=change.sale_updated_at_snapshot + timedelta(seconds=5),
        )

        ok, error = approve_change_request(change, self.admin)
        self.assertFalse(ok)
        change.refresh_from_db()
        self.assertEqual(change.status, SaleChangeRequest.Status.REJECTED)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.price, Decimal("850.00"))
        self.assertIn("changed after", error)

    def test_admin_direct_edit_cancels_pending_request(self):
        Sale.objects.filter(pk=self.sale.pk).update(
            created_at=timezone.now() - timedelta(hours=80),
            updated_at=timezone.now() - timedelta(hours=80),
        )
        self.sale.refresh_from_db()
        self._post_sale_update(self.manager, self.sale, change_reason="Waiting for admin", price="990.00")
        pending = SaleChangeRequest.objects.get(sale=self.sale, status=SaleChangeRequest.Status.PENDING)

        self.client.force_login(self.admin)
        self.client.post(
            reverse("sale-update", kwargs={"pk": self.sale.pk}),
            {
                "service": self.service.pk,
                "staff": self.staff.pk,
                "price": "875.00",
                "payment_method": "cash",
                "date": timezone.localtime(self.sale.date).strftime("%Y-%m-%dT%H:%M"),
                "notes": "",
                "customer": "",
                "appointment": "",
                "new_first_name": "",
                "new_last_name": "",
                "new_email": "",
                "new_phone": "",
            },
        )

        pending.refresh_from_db()
        self.assertEqual(pending.status, SaleChangeRequest.Status.CANCELLED)
        self.assertTrue(
            StaffNotification.objects.filter(
                user=self.manager,
                message__icontains="cancelled",
            ).exists()
        )

    def test_staff_cannot_access_sale_edit(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("sale-list"))
        self.assertEqual(response.status_code, 403)

    def test_admin_can_approve_pending_request(self):
        Sale.objects.filter(pk=self.sale.pk).update(
            created_at=timezone.now() - timedelta(hours=80),
            updated_at=timezone.now() - timedelta(hours=80),
        )
        self.sale.refresh_from_db()
        self._post_sale_update(self.manager, self.sale, change_reason="Approve me", price="975.00")
        change = SaleChangeRequest.objects.get(sale=self.sale, status=SaleChangeRequest.Status.PENDING)

        ok, error = approve_change_request(change, self.admin)
        self.assertTrue(ok)
        self.assertIsNone(error)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.price, Decimal("975.00"))
        change.refresh_from_db()
        self.assertEqual(change.status, SaleChangeRequest.Status.APPROVED)
        self.assertTrue(
            StaffNotification.objects.filter(
                user=self.manager,
                message__icontains="approved",
            ).exists()
        )
