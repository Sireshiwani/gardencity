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
        CUSTOMER = "customer", "Customer"

    email = models.EmailField(unique=True, blank=True, null=True)
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

    STAFF_ROLES = (
        Roles.ADMIN,
        Roles.MANAGER,
        Roles.STAFF,
    )

    @classmethod
    def assignable_staff(cls):
        """Active team members who can be booked or assigned to sales."""
        return cls.objects.filter(role__in=cls.STAFF_ROLES, is_active=True).order_by("full_name")

    @classmethod
    def roster(cls, *, include_inactive: bool = False):
        """Staff/admin/manager accounts for the team list."""
        qs = cls.objects.filter(role__in=cls.STAFF_ROLES)
        if not include_inactive:
            qs = qs.filter(is_active=True)
        return qs.order_by("role", "full_name")

    def save(self, *args, **kwargs):
        if self.role in {self.Roles.ADMIN, self.Roles.MANAGER}:
            self.is_staff = True
        if self.role == self.Roles.CUSTOMER:
            self.is_staff = False
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

    customer = models.ForeignKey(
        "Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    customer_name = models.CharField(max_length=150)
    customer_email = models.EmailField(blank=True)
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
    staff_snapshot_name = models.CharField(max_length=255, blank=True, help_text="Preserved if staff account is removed.")
    appointment_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["appointment_at"]

    def save(self, *args, **kwargs):
        if self.status == self.Status.COMPLETED and self.completed_at is None:
            self.completed_at = timezone.now()
        if self.staff_id and self.staff:
            self.staff_snapshot_name = self.staff.full_name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer_name} - {self.service.name}"


class Sale(models.Model):
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="sales")
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
    )
    appointment = models.ForeignKey(
        "Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
    )
    staff = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
        limit_choices_to={"role__in": [User.Roles.ADMIN, User.Roles.MANAGER, User.Roles.STAFF]},
    )
    staff_snapshot_name = models.CharField(max_length=255, blank=True, help_text="Preserved if staff account is removed.")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def save(self, *args, **kwargs):
        if self.staff_id and self.staff:
            self.staff_snapshot_name = self.staff.full_name
        super().save(*args, **kwargs)

    @property
    def commission_amount(self):
        if not self.staff_id:
            return Decimal("0.00")
        return (self.price * self.staff.commission_rate) / Decimal("100.00")

    @property
    def shop_net(self):
        return self.price - self.commission_amount

    def __str__(self):
        who = self.staff.full_name if self.staff_id else self.staff_snapshot_name or "Staff"
        return f"{self.service.name} - {who}"


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
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    advance_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    date = models.DateField(default=timezone.localdate)
    period_start = models.DateField()
    period_end = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.staff} payout - {self.amount}"


class Customer(models.Model):
    class Tier(models.TextChoices):
        BRONZE = "bronze", "Bronze"
        SILVER = "silver", "Silver"
        GOLD = "gold", "Gold"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="customer_profile",
    )
    email = models.EmailField(unique=True, db_index=True, blank=True, null=True)
    phone = models.CharField(max_length=50)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    birthday_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    birthday_day = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
    )
    referral_code = models.CharField(max_length=32, unique=True, db_index=True)
    referred_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referrals",
    )
    sms_opt_out = models.BooleanField(default=False)
    points_balance = models.IntegerField(default=0)
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.BRONZE)
    last_visit_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        name = f"{self.first_name} {self.last_name}".strip()
        if name:
            return name
        if self.email:
            return self.email
        return self.phone or "Customer"


class LoyaltySettings(models.Model):
    id = models.PositiveIntegerField(primary_key=True, default=1, editable=False)
    points_per_visit = models.PositiveIntegerField(default=50)
    points_per_dollar = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.00"))
    referral_bonus_referrer = models.PositiveIntegerField(default=100)
    referral_bonus_referee = models.PositiveIntegerField(default=50)
    shop_display_name = models.CharField(max_length=120, default="Garden City Fine Cuts")
    booking_base_url = models.URLField(blank=True)
    sms_retention_enabled = models.BooleanField(default=True)
    sms_retention_days = models.PositiveIntegerField(default=21)
    review_request_enabled = models.BooleanField(default=True)
    review_request_hours_after = models.PositiveIntegerField(default=24)
    review_bonus_points = models.PositiveIntegerField(default=25)
    at_risk_days = models.PositiveIntegerField(
        default=45,
        help_text="Customers with no visit in this many days are flagged as at-risk.",
    )
    retention_sms_template = models.TextField(
        default=(
            "Hi {first_name}, it's been {weeks} weeks since your last visit at {shop_name}! "
            "Book your next fresh cut here: {booking_link}"
        ),
        help_text="Placeholders: {first_name}, {shop_name}, {booking_link}, {weeks}, {retention_days}",
    )
    review_sms_template = models.TextField(
        default=(
            "Hi {first_name}, thanks for visiting {shop_name}. "
            "Leave a Google or Yelp review — {review_bonus_points} bonus points on your next visit."
        ),
        help_text="Placeholders: {first_name}, {shop_name}, {review_bonus_points}",
    )

    def __str__(self):
        return "Loyalty settings"


class SlowHourWindow(models.Model):
    name = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    weekday_start = models.PositiveSmallIntegerField(help_text="0=Monday ... 6=Sunday")
    weekday_end = models.PositiveSmallIntegerField(help_text="Inclusive; same as start for single day.")
    time_start = models.TimeField()
    time_end = models.TimeField()
    multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("2.00"))

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PointsLedger(models.Model):
    class EntryType(models.TextChoices):
        VISIT = "visit", "Visit"
        SPEND = "spend", "Spend"
        REFERRAL_REFERRER = "referral_referrer", "Referral (Referrer)"
        REFERRAL_REFEREE = "referral_referee", "Referral (New Customer)"
        REVIEW_BONUS = "review_bonus", "Review Bonus"
        ADJUSTMENT = "adjustment", "Adjustment"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="ledger_entries")
    points_delta = models.IntegerField()
    balance_after = models.IntegerField()
    entry_type = models.CharField(max_length=30, choices=EntryType.choices)
    description = models.CharField(max_length=500, blank=True)
    appointment = models.ForeignKey("Appointment", null=True, blank=True, on_delete=models.SET_NULL)
    sale = models.ForeignKey("Sale", null=True, blank=True, on_delete=models.SET_NULL)
    multiplier_applied = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("1.000"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer} {self.points_delta:+d}"


class ReferralCredit(models.Model):
    referrer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="referrals_paid")
    referee = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name="referral_credit")
    appointment = models.ForeignKey("Appointment", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)


class CustomerBarberNote(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="barber_notes")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="barber_notes")
    note = models.TextField()
    previous_cut_photo = models.ImageField(upload_to="ledger_cuts/%Y/%m/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ReviewNudge(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name="review_nudge")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    channel = models.CharField(max_length=20, default="sms")
    sent_at = models.DateTimeField(auto_now_add=True)


class SMSLog(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="sms_logs", null=True, blank=True)
    kind = models.CharField(max_length=30)
    message_body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    error_message = models.CharField(max_length=500, blank=True)


class SalaryAdvance(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PARTIALLY_REPAID = "partially_repaid", "Partially Repaid"
        REPAID = "repaid", "Repaid"
        CANCELLED = "cancelled", "Cancelled"

    staff = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="salary_advances",
        limit_choices_to={"role__in": [User.Roles.ADMIN, User.Roles.MANAGER, User.Roles.STAFF]},
    )
    requested_amount = models.DecimalField(max_digits=10, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    outstanding_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    reason = models.TextField(blank=True)
    manager_notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_salary_advances",
    )

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.staff.full_name} advance {self.requested_amount}"


class SalaryAdvanceRepayment(models.Model):
    advance = models.ForeignKey(SalaryAdvance, on_delete=models.CASCADE, related_name="repayments")
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="advance_repayments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-applied_at"]

    def __str__(self):
        return f"{self.advance.staff.full_name} repayment {self.amount}"


class SaleChangeRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        SUPERSEDED = "superseded", "Superseded"

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="change_requests")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sale_change_requests",
        limit_choices_to={"role__in": [User.Roles.MANAGER]},
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()
    sale_updated_at_snapshot = models.DateTimeField(
        help_text="Sale.updated_at when this request was submitted; used to detect stale approvals.",
    )
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_sale_change_requests",
        limit_choices_to={"role__in": [User.Roles.ADMIN]},
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="+")
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    appointment = models.ForeignKey(
        "Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    staff = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        limit_choices_to={"role__in": [User.Roles.ADMIN, User.Roles.MANAGER, User.Roles.STAFF]},
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    date = models.DateTimeField()
    notes = models.TextField(blank=True)
    new_first_name = models.CharField(max_length=100, blank=True)
    new_last_name = models.CharField(max_length=100, blank=True)
    new_email = models.EmailField(blank=True)
    new_phone = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Change request for sale #{self.sale_id} ({self.get_status_display()})"


class StaffNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=500)
    link = models.CharField(max_length=255, blank=True)
    change_request = models.ForeignKey(
        SaleChangeRequest,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message[:80]

    @property
    def is_read(self):
        return self.read_at is not None
