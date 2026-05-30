from datetime import datetime

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .customers import customer_username_from_phone, get_or_create_from_booking, normalize_phone
from .models import (
    Appointment,
    Customer,
    CustomerBarberNote,
    Expense,
    LoyaltySettings,
    Payment,
    Sale,
    SalaryAdvance,
    Service,
    SlowHourWindow,
    User,
)
from .services.loyalty import generate_referral_code


class TailwindMixin:
    def apply_tailwind(self):
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (
                f"{existing} mt-2 w-full rounded-xl border border-white/10 bg-black/30 "
                "px-4 py-3 text-[#f5f5f5] placeholder:text-gray-500 focus:border-yellow-500 "
                "focus:outline-none"
            ).strip()


class StaffUserCreationForm(TailwindMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "full_name", "email", "role", "photo_url", "commission_rate", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [c for c in User.Roles.choices if c[0] != User.Roles.CUSTOMER]
        self.apply_tailwind()


class StaffUserUpdateForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "full_name", "email", "role", "photo_url", "commission_rate", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [c for c in User.Roles.choices if c[0] != User.Roles.CUSTOMER]
        self.apply_tailwind()


class CustomerRegistrationForm(TailwindMixin, UserCreationForm):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100, required=False)
    phone = forms.CharField(max_length=50)
    birthday = forms.CharField(
        required=False,
        label="Birthday (MM-DD)",
        help_text="Optional. Month and day only (example: 08-21).",
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget = forms.HiddenInput()
        self.fields["username"].required = False
        self.fields["email"].required = False
        self.fields["email"].label = "Email (optional)"
        self.fields["phone"].required = True
        self.fields["birthday"].widget.attrs.update(
            {"placeholder": "MM-DD", "inputmode": "numeric", "autocomplete": "bday-day"}
        )
        self.order_fields(
            ["first_name", "last_name", "phone", "birthday", "email", "password1", "password2", "username"]
        )
        self.apply_tailwind()

    def clean(self):
        data = super().clean()
        email = (data.get("email") or "").strip().lower()
        phone = normalize_phone((data.get("phone") or "").strip())
        birthday = (data.get("birthday") or "").strip()
        if not phone:
            raise ValidationError({"phone": "Phone number is required."})
        if email:
            data["username"] = email
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError({"email": "An account with this email already exists."})
        else:
            data["username"] = customer_username_from_phone(phone)
        if Customer.objects.filter(phone=phone).exists():
            raise ValidationError({"phone": "An account with this phone number already exists."})
        data["phone"] = phone
        if birthday:
            try:
                parsed = datetime.strptime(birthday, "%m-%d")
            except ValueError as exc:
                raise ValidationError("Enter birthday as MM-DD (for example: 08-21).") from exc
            data["birthday_month"] = parsed.month
            data["birthday_day"] = parsed.day
        else:
            data["birthday_month"] = None
            data["birthday_day"] = None
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        email = (self.cleaned_data.get("email") or "").strip().lower()
        phone = self.cleaned_data["phone"]
        user.username = self.cleaned_data["username"]
        user.email = email or None
        user.full_name = f"{self.cleaned_data['first_name']} {self.cleaned_data.get('last_name', '')}".strip()
        user.role = User.Roles.CUSTOMER
        user.is_staff = False
        if commit:
            user.save()
            Customer.objects.create(
                user=user,
                email=email or None,
                phone=phone,
                first_name=self.cleaned_data["first_name"].strip(),
                last_name=(self.cleaned_data.get("last_name") or "").strip(),
                birthday_month=self.cleaned_data.get("birthday_month"),
                birthday_day=self.cleaned_data.get("birthday_day"),
                referral_code=generate_referral_code(),
            )
        return user


class CustomerBarberNoteForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = CustomerBarberNote
        fields = ("note", "previous_cut_photo")


class LoginForm(TailwindMixin, AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Password"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class PasswordResetRequestForm(TailwindMixin, PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs["placeholder"] = "Email address"
        self.apply_tailwind()


class PasswordResetConfirmStyledForm(TailwindMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].widget.attrs["placeholder"] = "New password"
        self.fields["new_password2"].widget.attrs["placeholder"] = "Confirm new password"
        self.apply_tailwind()


class ServiceForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = ("name", "category", "photo_url", "description", "price", "duration_minutes", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class StaffPhotoUpdateForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("full_name", "photo_url")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class ServicePhotoUpdateForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = ("name", "photo_url", "description")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class SaleForm(TailwindMixin, forms.ModelForm):
    """Log a sale: pick an existing customer or enter details to create one on save."""

    new_first_name = forms.CharField(required=False, label="New customer — first name")
    new_last_name = forms.CharField(required=False, label="New customer — last name")
    new_email = forms.EmailField(required=False, label="New customer — email (optional)")
    new_phone = forms.CharField(required=False, label="New customer — phone")

    class Meta:
        model = Sale
        fields = ("service", "customer", "appointment", "staff", "price", "payment_method", "date", "notes")
        widgets = {"date": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cust = self.fields["customer"]
        cust.required = False
        cust.empty_label = "— Select existing customer (optional) —"
        cust.queryset = Customer.objects.all().order_by("last_name", "first_name", "email")
        self.apply_tailwind()

    def clean(self):
        cleaned = super().clean()
        existing = cleaned.get("customer")
        fn = (cleaned.get("new_first_name") or "").strip()
        em = (cleaned.get("new_email") or "").strip()
        ph = (cleaned.get("new_phone") or "").strip()
        ln = (cleaned.get("new_last_name") or "").strip()
        has_new = bool(fn or em or ph or ln)

        if existing and has_new:
            raise ValidationError(
                "Use either an existing customer or the new customer fields — not both. "
                "Clear one side to continue."
            )
        if has_new:
            if not fn or not ph:
                raise ValidationError("To add a new customer, provide first name and phone.")
            if em and Customer.objects.filter(email__iexact=em).exists():
                raise ValidationError(
                    "A customer with this email already exists. Choose them under Existing customer."
                )
            if not em and Customer.objects.filter(phone=ph).exists():
                raise ValidationError(
                    "A customer with this phone already exists. Choose them under Existing customer."
                )
        return cleaned

    def save(self, commit=True):
        sale = super().save(commit=False)
        fn = (self.cleaned_data.get("new_first_name") or "").strip()
        ph = (self.cleaned_data.get("new_phone") or "").strip()
        em = (self.cleaned_data.get("new_email") or "").strip()
        if not sale.customer_id and fn and ph:
            sale.customer = Customer.objects.create(
                email=em.lower() if em else None,
                phone=ph,
                first_name=fn,
                last_name=(self.cleaned_data.get("new_last_name") or "").strip(),
                referral_code=generate_referral_code(),
            )
        if commit:
            sale.save()
        return sale


class SaleEditForm(SaleForm):
    change_reason = forms.CharField(
        required=False,
        label="Reason for change",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Explain why this sale record needs to be updated."}),
    )

    def __init__(self, *args, requires_approval=False, **kwargs):
        self.requires_approval = requires_approval
        super().__init__(*args, **kwargs)
        if requires_approval:
            self.fields["change_reason"].required = True
        else:
            del self.fields["change_reason"]


class SaleChangeReviewForm(TailwindMixin, forms.Form):
    admin_notes = forms.CharField(
        required=False,
        label="Admin notes",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Optional notes for the manager if rejecting."}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class ExpenseForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = Expense
        fields = ("category", "amount", "description", "date")
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class PaymentCreateForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = Payment
        fields = ("staff", "amount", "date", "period_start", "period_end", "notes")
        labels = {"amount": "Gross payout before advance deductions"}
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "period_start": forms.DateInput(attrs={"type": "date"}),
            "period_end": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["staff"].queryset = User.objects.filter(
            role__in=[User.Roles.ADMIN, User.Roles.MANAGER, User.Roles.STAFF]
        ).order_by("full_name")
        self.fields["date"].initial = timezone.localdate
        self.apply_tailwind()

    def clean_amount(self):
        value = self.cleaned_data["amount"]
        if value <= 0:
            raise ValidationError("Payout amount must be greater than zero.")
        return value

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("period_start")
        end = cleaned.get("period_end")
        if start and end and start > end:
            raise ValidationError("Period start cannot be later than period end.")
        return cleaned


class SalaryAdvanceRequestForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = SalaryAdvance
        fields = ("requested_amount", "reason")
        widgets = {"reason": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()

    def clean_requested_amount(self):
        value = self.cleaned_data["requested_amount"]
        if value <= 0:
            raise ValidationError("Requested amount must be greater than zero.")
        return value


class SalaryAdvanceDecisionForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = SalaryAdvance
        fields = ("status", "approved_amount", "manager_notes")
        widgets = {"manager_notes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [
            (SalaryAdvance.Status.APPROVED, "Approve"),
            (SalaryAdvance.Status.REJECTED, "Reject"),
            (SalaryAdvance.Status.CANCELLED, "Cancel"),
        ]
        self.apply_tailwind()

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        approved_amount = cleaned.get("approved_amount")
        if status == SalaryAdvance.Status.APPROVED:
            if approved_amount is None or approved_amount <= 0:
                raise ValidationError("Enter an approved amount greater than zero.")
        return cleaned


class LoyaltySettingsDashboardForm(TailwindMixin, forms.ModelForm):
    """Owner dashboard: points rules, SMS copy, scheduling hints."""

    class Meta:
        model = LoyaltySettings
        labels = {
            "points_per_dollar": "Points per Kshs",
        }
        fields = [
            "points_per_visit",
            "points_per_dollar",
            "referral_bonus_referrer",
            "referral_bonus_referee",
            "shop_display_name",
            "booking_base_url",
            "sms_retention_enabled",
            "sms_retention_days",
            "retention_sms_template",
            "review_request_enabled",
            "review_request_hours_after",
            "review_bonus_points",
            "review_sms_template",
            "at_risk_days",
        ]
        widgets = {
            "retention_sms_template": forms.Textarea(attrs={"rows": 5, "class": "font-mono text-sm"}),
            "review_sms_template": forms.Textarea(attrs={"rows": 5, "class": "font-mono text-sm"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class SlowHourWindowForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = SlowHourWindow
        fields = ("name", "enabled", "weekday_start", "weekday_end", "time_start", "time_end", "multiplier")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["weekday_start"].help_text = "0 = Monday … 6 = Sunday"
        self.fields["weekday_end"].help_text = "Inclusive (e.g. Tue–Wed: start 1, end 2)."
        self.apply_tailwind()


class PublicBookingForm(TailwindMixin, forms.ModelForm):
    referral_code = forms.CharField(required=False, max_length=32, label="Referral code (optional)")

    class Meta:
        model = Appointment
        fields = (
            "customer_name",
            "customer_email",
            "customer_phone",
            "service",
            "staff",
            "appointment_at",
            "notes",
        )
        widgets = {"appointment_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, acting_user=None, **kwargs):
        self.acting_user = acting_user
        super().__init__(*args, **kwargs)
        self.fields["staff"].required = False
        ce = self.fields["customer_email"]
        ce.required = False
        ce.label = "Email (optional)"
        if acting_user and acting_user.role == User.Roles.STAFF:
            self.fields["staff"].widget = forms.HiddenInput()
            self.fields["staff"].initial = acting_user.pk
            self.fields.pop("referral_code", None)
        self.apply_tailwind()

    def save(self, commit=True):
        inst = super().save(commit=False)
        if self.acting_user and self.acting_user.role == User.Roles.STAFF:
            inst.staff = self.acting_user
        cust = get_or_create_from_booking(
            full_name=inst.customer_name,
            email=inst.customer_email or "",
            phone=inst.customer_phone,
            referral_code=self.cleaned_data.get("referral_code", ""),
        )
        inst.customer = cust
        if commit:
            inst.save()
            self.save_m2m()
        return inst
