from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Appointment, Expense, Sale, Service, User


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
        fields = ("username", "full_name", "email", "role", "commission_rate", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class StaffUserUpdateForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "full_name", "email", "role", "commission_rate", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class LoginForm(TailwindMixin, AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Password"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class ServiceForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = ("name", "category", "description", "price", "duration_minutes", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class SaleForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = Sale
        fields = ("service", "staff", "price", "payment_method", "date", "notes")
        widgets = {"date": forms.DateTimeInput(attrs={"type": "datetime-local"})}

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


class PublicBookingForm(TailwindMixin, forms.ModelForm):
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
