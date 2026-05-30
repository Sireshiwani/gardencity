from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from shop.forms import (
    CustomerBarberNoteForm,
    CustomerRegistrationForm,
    LoyaltySettingsDashboardForm,
    SlowHourWindowForm,
)
from shop.models import Appointment, Customer, CustomerBarberNote, LoyaltySettings, PointsLedger, ReferralCredit, Sale, SlowHourWindow, User
from shop.services.loyalty import get_loyalty_settings, slow_hour_multiplier_for_datetime
from shop.views import AdminRequiredMixin, FormTitleMixin, ManagerOrAdminRequiredMixin


class CustomerRoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return getattr(self.request.user, "role", None) == User.Roles.CUSTOMER


class StaffBarberMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role in {
            User.Roles.ADMIN,
            User.Roles.MANAGER,
            User.Roles.STAFF,
        }


def customer_register(request):
    if request.user.is_authenticated:
        role = getattr(request.user, "role", None)
        if role == User.Roles.CUSTOMER:
            return redirect("customer-dashboard")
        if role == User.Roles.ADMIN:
            return redirect("loyalty-manage")
        if role == User.Roles.MANAGER:
            return redirect("dashboard")
        return redirect("dashboard")
    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to Garden City Fine Cuts rewards.")
            return redirect("customer-dashboard")
    else:
        form = CustomerRegistrationForm()
    return render(request, "shop/customer_register.html", {"form": form})


class CustomerDashboardView(CustomerRoleRequiredMixin, TemplateView):
    template_name = "shop/customer_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if getattr(request.user, "role", None) != User.Roles.CUSTOMER:
            return redirect("dashboard")
        if not hasattr(request.user, "customer_profile"):
            messages.error(request, "Customer profile not found. Please complete registration.")
            return redirect("customer-register")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.request.user.customer_profile
        ctx["profile"] = profile
        ctx["ledger"] = PointsLedger.objects.filter(customer=profile).order_by("-created_at")[:50]
        return ctx


@login_required
def loyalty_manage(request):
    if request.user.role not in {User.Roles.ADMIN, User.Roles.MANAGER}:
        return redirect("login")
    obj = LoyaltySettings.objects.get_or_create(pk=1)[0]
    if request.method == "POST":
        form = LoyaltySettingsDashboardForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Rewards settings updated.")
            return redirect("loyalty-manage")
    else:
        form = LoyaltySettingsDashboardForm(instance=obj)
    windows = SlowHourWindow.objects.all().order_by("name")
    return render(request, "shop/loyalty_manage.html", {"form": form, "windows": windows})


class SlowHourCreateView(ManagerOrAdminRequiredMixin, FormTitleMixin, CreateView):
    model = SlowHourWindow
    form_class = SlowHourWindowForm
    template_name = "shop/form.html"
    success_url = reverse_lazy("loyalty-manage")
    form_title = "Add slow-hour window"

    def form_valid(self, form):
        messages.success(self.request, "Slow-hour window saved.")
        return super().form_valid(form)


class SlowHourUpdateView(ManagerOrAdminRequiredMixin, FormTitleMixin, UpdateView):
    model = SlowHourWindow
    form_class = SlowHourWindowForm
    template_name = "shop/form.html"
    success_url = reverse_lazy("loyalty-manage")
    form_title = "Edit slow-hour window"

    def form_valid(self, form):
        messages.success(self.request, "Slow-hour window updated.")
        return super().form_valid(form)


class SlowHourDeleteView(ManagerOrAdminRequiredMixin, DeleteView):
    model = SlowHourWindow
    template_name = "shop/confirm_delete.html"
    success_url = reverse_lazy("loyalty-manage")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Slow-hour window removed.")
        return super().delete(request, *args, **kwargs)


class LoyaltyOwnerReportView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "shop/loyalty_reports.html"

    def test_func(self):
        return self.request.user.role in {User.Roles.ADMIN, User.Roles.MANAGER}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        settings = get_loyalty_settings()
        today = timezone.localdate()
        cutoff_date = today - timedelta(days=settings.at_risk_days)

        at_risk = Customer.objects.filter(
            Q(last_visit_at__date__lt=cutoff_date) | Q(last_visit_at__isnull=True)
        ).order_by("last_visit_at")[:200]

        referral_count = ReferralCredit.objects.count()

        slow_revenue = Decimal("0.00")
        for sale in Sale.objects.select_related("appointment").filter(appointment__isnull=False):
            if not sale.appointment:
                continue
            ap = sale.appointment
            mult = slow_hour_multiplier_for_datetime(ap.appointment_at)
            if mult > Decimal("1.00"):
                slow_revenue += sale.price

        ctx.update(
            {
                "settings": settings,
                "at_risk": at_risk,
                "referral_count": referral_count,
                "slow_hour_revenue": slow_revenue,
            }
        )
        return ctx


class CustomerListView(AdminRequiredMixin, ListView):
    model = Customer
    template_name = "shop/customer_list.html"
    context_object_name = "customers"
    paginate_by = 50


class BarberNoteListView(StaffBarberMixin, ListView):
    model = CustomerBarberNote
    template_name = "shop/barber_notes.html"
    context_object_name = "notes"

    def get_queryset(self):
        return CustomerBarberNote.objects.select_related("customer", "author").order_by("-created_at")[:100]


class BarberNoteCreateView(StaffBarberMixin, CreateView):
    model = CustomerBarberNote
    form_class = CustomerBarberNoteForm
    template_name = "shop/barber_note_form.html"
    success_url = reverse_lazy("barber-notes")

    def dispatch(self, request, *args, **kwargs):
        self.customer = get_object_or_404(Customer, pk=kwargs["customer_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.customer = self.customer
        form.instance.author = self.request.user
        messages.success(self.request, "Note saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = f"Barber note — {self.customer}"
        return ctx
