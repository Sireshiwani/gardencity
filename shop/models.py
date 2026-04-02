from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        STAFF = "staff", "Staff"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.STAFF)
    photo_url = models.URLField(blank=True, help_text="Public URL for this staff member's profile photo.")
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("40.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Commission percentage paid to this staff member.",
    )

    REQUIRED_FIELDS = ["email", "full_name"]

    def save(self, *args, **kwargs):
        if self.role in {self.Roles.ADMIN, self.Roles.MANAGER}:
            self.is_staff = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or self.username


class ServiceCategory(models.TextChoices):
    HAIRCUT = "haircut", "Haircut"
    BEARD = "beard", "Beard Trim"
    GROOMING = "grooming", "Grooming"
    PRODUCT = "product", "Products"
    OTHER = "other", "Other"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    CARD = "card", "Card"
    TRANSFER = "transfer", "Transfer"
    MOBILE = "mobile", "Mobile Money"


class Service(models.Model):
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=ServiceCategory.choices)
    photo_url = models.URLField(blank=True, help_text="Public URL for the service photo.")
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.PositiveIntegerField(default=45)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    customer_name = models.CharField(max_length=150)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=50)
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="appointments")
    staff = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="appointments",
        null=True,
        blank=True,
        limit_choices_to={"role__in": [User.Roles.ADMIN, User.Roles.MANAGER, User.Roles.STAFF]},
    )
    appointment_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["appointment_at"]

    def __str__(self):
        return f"{self.customer_name} - {self.service.name}"


class Sale(models.Model):
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="sales")
    staff = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="sales",
        limit_choices_to={"role__in": [User.Roles.ADMIN, User.Roles.MANAGER, User.Roles.STAFF]},
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]

    @property
    def commission_amount(self):
        return (self.price * self.staff.commission_rate) / Decimal("100.00")

    @property
    def shop_net(self):
        return self.price - self.commission_amount

    def __str__(self):
        return f"{self.service.name} - {self.staff}"


class Expense(models.Model):
    category = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    date = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.category} - {self.amount}"


class Payment(models.Model):
    staff = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="payments",
        limit_choices_to={"role__in": [User.Roles.ADMIN, User.Roles.MANAGER, User.Roles.STAFF]},
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.localdate)
    period_start = models.DateField()
    period_end = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.staff} payout - {self.amount}"
