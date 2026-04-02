from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError

from .customers import get_or_create_from_booking
from .models import Appointment, Customer, CustomerBarberNote, Expense, LoyaltySettings, Sale, Service, SlowHourWindow, User
from .services.loyalty import generate_referral_code


class TailwindMixin:
    def apply_tailwind(self):
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (
                f"{existing} mt-2 w-full rounded-xl border border-zinc-700 bg-zinc-950 "
                "px-4 py-3 text-zinc-100 placeholder:text-zinc-500 focus:border-amber-500 "
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

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget = forms.HiddenInput()
        self.fields["username"].required = False
        self.fields["email"].required = True
        self.apply_tailwind()

    def clean(self):
        data = super().clean()
        email = (data.get("email") or "").strip().lower()
        if email:
            data["username"] = email
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"].strip().lower()
        user.email = user.username
        user.full_name = f"{self.cleaned_data['first_name']} {self.cleaned_data.get('last_name', '')}".strip()
        user.role = User.Roles.CUSTOMER
        user.is_staff = False
        if commit:
            user.save()
            Customer.objects.create(
                user=user,
                email=user.email,
                phone=self.cleaned_data["phone"].strip(),
                first_name=self.cleaned_data["first_name"].strip(),
                last_name=(self.cleaned_data.get("last_name") or "").strip(),
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
    new_email = forms.EmailField(required=False, label="New customer — email")
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
            if not fn or not em or not ph:
                raise ValidationError("To add a new customer, provide first name, email, and phone.")
            if Customer.objects.filter(email__iexact=em).exists():
                raise ValidationError(
                    "A customer with this email already exists. Choose them under Existing customer."
                )
        return cleaned

    def save(self, commit=True):
        sale = super().save(commit=False)
        em = (self.cleaned_data.get("new_email") or "").strip()
        if not sale.customer_id and em:
            sale.customer = Customer.objects.create(
                email=em.lower(),
                phone=self.cleaned_data["new_phone"].strip(),
                first_name=self.cleaned_data["new_first_name"].strip(),
                last_name=(self.cleaned_data.get("new_last_name") or "").strip(),
                referral_code=generate_referral_code(),
            )
        if commit:
            sale.save()
        return sale


class ExpenseForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = Expense
        fields = ("category", "amount", "description", "date")
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class LoyaltySettingsDashboardForm(TailwindMixin, forms.ModelForm):
    """Owner dashboard: points rules, SMS copy, scheduling hints."""

    class Meta:
        model = LoyaltySettings
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["staff"].required = False
        self.apply_tailwind()

    def save(self, commit=True):
        inst = super().save(commit=False)
        cust = get_or_create_from_booking(
            full_name=inst.customer_name,
            email=inst.customer_email,
            phone=inst.customer_phone,
            referral_code=self.cleaned_data.get("referral_code"),
        )
        inst.customer = cust
        if commit:
            inst.save()
            self.save_m2m()
        return inst
