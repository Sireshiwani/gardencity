import csv
import json
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.db.models import Count, F, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from .forms import (
    ExpenseForm,
    LoginForm,
    PublicBookingForm,
    SaleForm,
    ServicePhotoUpdateForm,
    ServiceForm,
    StaffPhotoUpdateForm,
    StaffUserCreationForm,
    StaffUserUpdateForm,
)
from .models import Appointment, Expense, Payment, Sale, Service, User


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = []

    def test_func(self):
        return self.request.user.role in self.allowed_roles


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = [User.Roles.ADMIN]


class ManagerOrAdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = [User.Roles.ADMIN, User.Roles.MANAGER]


class FormTitleMixin:
    form_title = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.form_title:
            context["form_title"] = self.form_title
        else:
            context["form_title"] = f"{self.model._meta.verbose_name.title()} Form"
        return context


def daterange_from_request(request):
    today = timezone.localdate()
    filter_type = request.GET.get("range", "month")
    start_raw = request.GET.get("start")
    end_raw = request.GET.get("end")

    if filter_type == "daily":
        start = end = today
    elif filter_type == "weekly":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif filter_type == "custom" and start_raw and end_raw:
        start = datetime.fromisoformat(start_raw).date()
        end = datetime.fromisoformat(end_raw).date()
    else:
        start = today.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1) - timedelta(days=1)
        else:
            end = start.replace(month=start.month + 1) - timedelta(days=1)
    return filter_type, start, end


class StaffLoginView(LoginView):
    template_name = "shop/login.html"
    authentication_form = LoginForm

    def get_success_url(self):
        if getattr(self.request.user, "role", None) == User.Roles.CUSTOMER:
            return reverse("customer-dashboard")
        return reverse("dashboard")

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username or password. Please try again.")
        return super().form_invalid(form)


def home(request):
    services = Service.objects.filter(is_active=True)[:6]
    team = User.objects.filter(role=User.Roles.STAFF)[:4]
    form = PublicBookingForm()
    return render(request, "shop/home.html", {"services": services, "team": team, "form": form})


def book_now(request):
    if request.method == "POST":
        form = PublicBookingForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Your appointment request has been submitted.")
            return redirect("home")
    else:
        form = PublicBookingForm()
    return render(request, "shop/booking.html", {"form": form})


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "shop/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        month_start = today.replace(day=1)

        sales = Sale.objects.select_related("staff", "service")
        expenses = Expense.objects.all()
        appointments = Appointment.objects.select_related("service", "staff")

        if user.role == User.Roles.STAFF:
            sales = sales.filter(staff=user)
            appointments = appointments.filter(staff=user)

        today_sales = sales.filter(date__date=today).aggregate(total=Coalesce(Sum("price"), Decimal("0.00")))["total"]
        month_sales = sales.filter(date__date__gte=month_start).aggregate(total=Coalesce(Sum("price"), Decimal("0.00")))["total"]
        month_expenses = expenses.filter(date__gte=month_start).aggregate(total=Coalesce(Sum("amount"), Decimal("0.00")))[
            "total"
        ]

        leaderboard = (
            Sale.objects.values("staff__full_name")
            .annotate(total_sales=Coalesce(Sum("price"), Decimal("0.00")), transactions=Count("id"))
            .order_by("-total_sales")[:5]
        )

        category_sales = (
            sales.values("service__category")
            .annotate(total=Coalesce(Sum("price"), Decimal("0.00")))
            .order_by("-total")
        )
        daily_sales = (
            sales.filter(date__date__gte=month_start)
            .annotate(day=TruncDate("date"))
            .values("day")
            .annotate(total=Coalesce(Sum("price"), Decimal("0.00")))
            .order_by("day")
        )

        personal_sales = sales.aggregate(total=Coalesce(Sum("price"), Decimal("0.00")))["total"]
        personal_commission = sum((sale.commission_amount for sale in sales), Decimal("0.00"))
        payouts = Payment.objects.filter(staff=user).aggregate(total=Coalesce(Sum("amount"), Decimal("0.00")))["total"]

        context.update(
            {
                "today_sales": today_sales,
                "month_sales": month_sales,
                "month_expenses": month_expenses,
                "leaderboard": leaderboard,
                "upcoming_appointments": appointments.filter(appointment_at__date__gte=today)[:8],
                "recent_sales": sales[:8],
                "personal_sales": personal_sales,
                "personal_commission": personal_commission,
                "payouts": payouts,
                "category_chart": json.dumps(
                    {
                        "labels": [item["service__category"].title() for item in category_sales],
                        "values": [float(item["total"]) for item in category_sales],
                    }
                ),
                "daily_chart": json.dumps(
                    {
                        "labels": [item["day"].strftime("%b %d") for item in daily_sales],
                        "values": [float(item["total"]) for item in daily_sales],
                    }
                ),
            }
        )
        return context


class StaffListView(ManagerOrAdminRequiredMixin, ListView):
    model = User
    template_name = "shop/staff_list.html"
    context_object_name = "staff_members"

    def get_queryset(self):
        return User.objects.order_by("role", "full_name")


class StaffCreateView(AdminRequiredMixin, FormTitleMixin, CreateView):
    model = User
    form_class = StaffUserCreationForm
    template_name = "shop/form.html"
    success_url = reverse_lazy("staff-list")
    form_title = "Add Staff Member"


class StaffUpdateView(ManagerOrAdminRequiredMixin, FormTitleMixin, UpdateView):
    model = User
    template_name = "shop/form.html"
    success_url = reverse_lazy("staff-list")
    form_title = "Edit Staff Member"

    def get_form_class(self):
        if self.request.user.role == User.Roles.MANAGER:
            return StaffPhotoUpdateForm
        return StaffUserUpdateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role == User.Roles.MANAGER:
            context["form_title"] = "Update Staff Profile"
        return context


class StaffDeleteView(AdminRequiredMixin, DeleteView):
    model = User
    template_name = "shop/confirm_delete.html"
    success_url = reverse_lazy("staff-list")


class ServiceListView(ManagerOrAdminRequiredMixin, ListView):
    model = Service
    template_name = "shop/service_list.html"
    context_object_name = "services"


class ServiceCreateView(AdminRequiredMixin, FormTitleMixin, CreateView):
    model = Service
    form_class = ServiceForm
    template_name = "shop/form.html"
    success_url = reverse_lazy("service-list")
    form_title = "Add Service"


class ServiceUpdateView(ManagerOrAdminRequiredMixin, FormTitleMixin, UpdateView):
    model = Service
    template_name = "shop/form.html"
    success_url = reverse_lazy("service-list")
    form_title = "Edit Service"

    def get_form_class(self):
        if self.request.user.role == User.Roles.MANAGER:
            return ServicePhotoUpdateForm
        return ServiceForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role == User.Roles.MANAGER:
            context["form_title"] = "Update Service Profile"
        return context


class ServiceDeleteView(AdminRequiredMixin, DeleteView):
    model = Service
    template_name = "shop/confirm_delete.html"
    success_url = reverse_lazy("service-list")


class SaleListView(ManagerOrAdminRequiredMixin, ListView):
    model = Sale
    template_name = "shop/sale_list.html"
    context_object_name = "sales"

    def get_queryset(self):
        return Sale.objects.select_related("service", "staff", "customer")


class SaleCreateView(ManagerOrAdminRequiredMixin, FormTitleMixin, CreateView):
    model = Sale
    form_class = SaleForm
    template_name = "shop/sale_form.html"
    success_url = reverse_lazy("sale-list")
    form_title = "Log Sale"


class SaleUpdateView(ManagerOrAdminRequiredMixin, FormTitleMixin, UpdateView):
    model = Sale
    form_class = SaleForm
    template_name = "shop/sale_form.html"
    success_url = reverse_lazy("sale-list")
    form_title = "Edit Sale"


class SaleDeleteView(AdminRequiredMixin, DeleteView):
    model = Sale
    template_name = "shop/confirm_delete.html"
    success_url = reverse_lazy("sale-list")


class ExpenseListView(ManagerOrAdminRequiredMixin, ListView):
    model = Expense
    template_name = "shop/expense_list.html"
    context_object_name = "expenses"


class ExpenseCreateView(ManagerOrAdminRequiredMixin, FormTitleMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "shop/form.html"
    success_url = reverse_lazy("expense-list")
    form_title = "Log Expense"


class ExpenseUpdateView(ManagerOrAdminRequiredMixin, FormTitleMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "shop/form.html"
    success_url = reverse_lazy("expense-list")
    form_title = "Edit Expense"


class ExpenseDeleteView(AdminRequiredMixin, DeleteView):
    model = Expense
    template_name = "shop/confirm_delete.html"
    success_url = reverse_lazy("expense-list")


def sales_report(request):
    if not request.user.is_authenticated or request.user.role not in [User.Roles.ADMIN, User.Roles.MANAGER]:
        return redirect("login")

    _, start, end = daterange_from_request(request)
    sales = (
        Sale.objects.select_related("staff", "service")
        .filter(date__date__range=(start, end))
        .order_by("-date")
    )

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="sales-report.csv"'
        writer = csv.writer(response)
        writer.writerow(["Date", "Staff", "Service", "Category", "Gross Sale", "Commission", "Shop Net", "Payment"])
        for sale in sales:
            staff_name = sale.staff.full_name if sale.staff_id else sale.staff_snapshot_name
            writer.writerow(
                [
                    sale.date.strftime("%Y-%m-%d %H:%M"),
                    staff_name,
                    sale.service.name,
                    sale.service.category,
                    sale.price,
                    sale.commission_amount,
                    sale.shop_net,
                    sale.payment_method,
                ]
            )
        return response

    by_staff_raw = (
        sales.values("staff__full_name", "staff__commission_rate")
        .annotate(total_sales=Coalesce(Sum("price"), Decimal("0.00")))
        .order_by("-total_sales")
    )
    by_category = sales.values("service__category").annotate(total=Coalesce(Sum("price"), Decimal("0.00"))).order_by("-total")
    by_staff = []
    for item in by_staff_raw:
        earnings = (item["total_sales"] * item["staff__commission_rate"]) / Decimal("100.00")
        by_staff.append(
            {
                "name": item["staff__full_name"],
                "total_sales": item["total_sales"],
                "commission_rate": item["staff__commission_rate"],
                "staff_earnings": earnings,
                "shop_net": item["total_sales"] - earnings,
            }
        )

    return render(
        request,
        "shop/sales_report.html",
        {"sales": sales, "by_staff": by_staff, "by_category": by_category, "start": start, "end": end},
    )


def expense_report(request):
    if not request.user.is_authenticated or request.user.role not in [User.Roles.ADMIN, User.Roles.MANAGER]:
        return redirect("login")

    _, start, end = daterange_from_request(request)
    expenses = Expense.objects.filter(date__range=(start, end)).order_by("-date")

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="expense-report.csv"'
        writer = csv.writer(response)
        writer.writerow(["Date", "Category", "Amount", "Description"])
        for expense in expenses:
            writer.writerow([expense.date, expense.category, expense.amount, expense.description])
        return response

    by_category = expenses.values("category").annotate(total=Coalesce(Sum("amount"), Decimal("0.00"))).order_by("-total")
    return render(
        request,
        "shop/expense_report.html",
        {"expenses": expenses, "by_category": by_category, "start": start, "end": end},
    )
