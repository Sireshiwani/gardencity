import csv
import json
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.db.models import Count, F, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from .site_urls import public_site_url, redirect_to_public_site
from .forms import (
    ExpenseForm,
    LoginForm,
    PaymentCreateForm,
    PublicBookingForm,
    SaleChangeReviewForm,
    SaleEditForm,
    SaleForm,
    SalaryAdvanceDecisionForm,
    SalaryAdvanceRequestForm,
    ServicePhotoUpdateForm,
    ServiceForm,
    StaffPhotoUpdateForm,
    StaffUserCreationForm,
    StaffUserUpdateForm,
)
from .models import Appointment, Expense, Payment, Sale, SaleChangeRequest, SalaryAdvance, SalaryAdvanceRepayment, Service, StaffNotification, User
from .services.sale_changes import (
    approve_change_request,
    cancel_pending_requests_for_admin_edit,
    create_change_request_from_form,
    get_pending_change_request,
    manager_edit_deadline,
    manager_may_edit_sale_directly,
    reject_change_request,
)


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = []

    def test_func(self):
        return self.request.user.role in self.allowed_roles


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = [User.Roles.ADMIN]


class ManagerOrAdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = [User.Roles.ADMIN, User.Roles.MANAGER]


class StaffOrAboveRequiredMixin(RoleRequiredMixin):
    allowed_roles = [User.Roles.ADMIN, User.Roles.MANAGER, User.Roles.STAFF]


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


def apply_salary_advance_deductions(payment: Payment, gross_amount: Decimal) -> Decimal:
    outstanding = SalaryAdvance.objects.select_for_update().filter(
        staff=payment.staff,
        status__in=[SalaryAdvance.Status.APPROVED, SalaryAdvance.Status.PARTIALLY_REPAID],
        outstanding_balance__gt=Decimal("0.00"),
    )
    deduction_remaining = gross_amount
    total_deducted = Decimal("0.00")
    for advance in outstanding.order_by("approved_at", "requested_at"):
        if deduction_remaining <= Decimal("0.00"):
            break
        to_apply = min(advance.outstanding_balance, deduction_remaining)
        if to_apply <= Decimal("0.00"):
            continue
        SalaryAdvanceRepayment.objects.create(advance=advance, payment=payment, amount=to_apply)
        advance.outstanding_balance -= to_apply
        advance.status = (
            SalaryAdvance.Status.REPAID
            if advance.outstanding_balance <= Decimal("0.00")
            else SalaryAdvance.Status.PARTIALLY_REPAID
        )
        advance.save(update_fields=["outstanding_balance", "status"])
        deduction_remaining -= to_apply
        total_deducted += to_apply
    return total_deducted


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


class StaffLogoutView(LogoutView):
    """Redirect to login with a same-site relative URL (avoids PUBLIC_SITE_URL logout issues)."""

    next_page = reverse_lazy("login")
    http_method_names = ["post", "options"]


def home(request):
    services = Service.objects.filter(is_active=True).order_by("category", "name")[:3]
    team = User.objects.filter(role=User.Roles.STAFF, is_active=True).order_by("full_name")[:3]
    team_all = User.objects.filter(role=User.Roles.STAFF, is_active=True).order_by("full_name")
    booking_services = Service.objects.filter(is_active=True).order_by("category", "name")
    services_payload = [
        {
            "id": s.id,
            "name": s.name,
            "price": str(s.price),
            "description": s.description,
        }
        for s in booking_services
    ]
    team_payload = [{"id": u.id, "name": u.full_name} for u in team_all]
    return render(
        request,
        "shop/home.html",
        {
            "services": services,
            "team": team,
            "team_all": team_all,
            "services_payload": services_payload,
            "team_payload": team_payload,
        },
    )


def appointments_for_user(user):
    qs = Appointment.objects.select_related("service", "staff").exclude(
        status=Appointment.Status.CANCELLED
    )
    if user.role == User.Roles.STAFF:
        qs = qs.filter(staff=user)
    return qs


def book_now(request):
    user = request.user
    staff_view = user.is_authenticated and user.role in (
        User.Roles.ADMIN,
        User.Roles.MANAGER,
        User.Roles.STAFF,
    )

    if request.method == "POST":
        form = PublicBookingForm(
            request.POST,
            acting_user=user if staff_view else None,
        )
        if form.is_valid():
            form.save()
            if staff_view:
                messages.success(request, "Appointment scheduled successfully.")
                return redirect("book-now")
            messages.success(request, "Your appointment request has been submitted.")
            return redirect(reverse("home") + "#booking")
    else:
        form = PublicBookingForm(acting_user=user if staff_view else None)

    context = {"form": form, "staff_view": staff_view}
    if staff_view:
        context["appointments"] = appointments_for_user(user)
        context["show_all_appointments"] = user.role in (User.Roles.ADMIN, User.Roles.MANAGER)
    return render(request, "shop/booking.html", context)


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
        show_archived = self.request.GET.get("archived") == "1"
        return User.roster(include_inactive=show_archived)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_archived"] = self.request.GET.get("archived") == "1"
        return context


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


class StaffDeactivateView(AdminRequiredMixin, View):
    """Deactivate instead of delete — keeps sales and reports linked to this user."""

    template_name = "shop/confirm_deactivate.html"

    def get(self, request, pk):
        member = get_object_or_404(User, pk=pk, role__in=User.STAFF_ROLES)
        return render(request, self.template_name, {"object": member})

    def post(self, request, pk):
        member = get_object_or_404(User, pk=pk, role__in=User.STAFF_ROLES)
        if member.pk == request.user.pk:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect("staff-list")
        if not member.is_active:
            messages.info(request, f"{member.full_name} is already inactive.")
            return redirect("staff-list")
        member.is_active = False
        member.save(update_fields=["is_active"])
        messages.success(
            request,
            f"{member.full_name} was deactivated. Past sales stay on their record; they cannot log in or be assigned new work.",
        )
        return redirect("staff-list")


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sale_ids = [sale.pk for sale in context["sales"]]
        pending = {
            req.sale_id: req
            for req in SaleChangeRequest.objects.filter(
                sale_id__in=sale_ids,
                status=SaleChangeRequest.Status.PENDING,
            ).select_related("requested_by")
        }
        context["pending_change_requests"] = pending
        context["pending_change_request_ids"] = set(pending.keys())
        context["manager_may_edit"] = {
            sale.pk: manager_may_edit_sale_directly(sale) for sale in context["sales"]
        }
        context["direct_edit_sale_ids"] = {
            sale_id for sale_id, allowed in context["manager_may_edit"].items() if allowed
        }
        return context


class SaleCreateView(ManagerOrAdminRequiredMixin, FormTitleMixin, CreateView):
    model = Sale
    form_class = SaleForm
    template_name = "shop/sale_form.html"
    success_url = reverse_lazy("sale-list")
    form_title = "Log Sale"


class SaleUpdateView(ManagerOrAdminRequiredMixin, FormTitleMixin, UpdateView):
    model = Sale
    template_name = "shop/sale_form.html"
    success_url = reverse_lazy("sale-list")
    form_title = "Edit Sale"

    def get_form_class(self):
        return SaleEditForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.user.role == User.Roles.MANAGER:
            kwargs["requires_approval"] = not manager_may_edit_sale_directly(self.get_object())
        else:
            kwargs["requires_approval"] = False
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sale = self.object
        user = self.request.user
        requires_approval = user.role == User.Roles.MANAGER and not manager_may_edit_sale_directly(sale)
        context["requires_approval"] = requires_approval
        context["pending_change_request"] = get_pending_change_request(sale)
        context["manager_edit_deadline"] = manager_edit_deadline(sale)
        if requires_approval:
            context["form_title"] = "Request Sale Change"
        return context

    def form_valid(self, form):
        sale = self.get_object()
        user = self.request.user

        if user.role == User.Roles.ADMIN:
            cancel_pending_requests_for_admin_edit(sale, user)
            messages.success(self.request, "Sale updated.")
            return super().form_valid(form)

        if manager_may_edit_sale_directly(sale):
            messages.success(self.request, "Sale updated.")
            return super().form_valid(form)

        create_change_request_from_form(
            sale,
            form,
            user,
            form.cleaned_data["change_reason"],
        )
        messages.success(
            self.request,
            "Change request submitted. An admin must approve it before the sale is updated.",
        )
        return redirect(self.success_url)


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


class PaymentListView(ManagerOrAdminRequiredMixin, ListView):
    model = Payment
    template_name = "shop/payment_list.html"
    context_object_name = "payments"

    def get_queryset(self):
        return Payment.objects.select_related("staff").order_by("-date")


class PaymentCreateView(ManagerOrAdminRequiredMixin, FormTitleMixin, CreateView):
    model = Payment
    form_class = PaymentCreateForm
    template_name = "shop/form.html"
    success_url = reverse_lazy("payment-list")
    form_title = "Log Payout"

    @transaction.atomic
    def form_valid(self, form):
        gross_amount = form.cleaned_data["amount"]
        payment = form.save(commit=False)
        payment.gross_amount = gross_amount
        payment.advance_deduction = Decimal("0.00")
        payment.amount = gross_amount
        payment.save()
        deducted = apply_salary_advance_deductions(payment, gross_amount)
        if deducted > Decimal("0.00"):
            payment.advance_deduction = deducted
            payment.amount = gross_amount - deducted
            payment.save(update_fields=["advance_deduction", "amount"])
            messages.success(
                self.request,
                f"Payout saved. {deducted} was auto-deducted for salary advance repayment.",
            )
        else:
            messages.success(self.request, "Payout saved.")
        return redirect(self.success_url)


class SalaryAdvanceListView(StaffOrAboveRequiredMixin, ListView):
    model = SalaryAdvance
    template_name = "shop/salary_advance_list.html"
    context_object_name = "advances"

    def get_queryset(self):
        qs = SalaryAdvance.objects.select_related("staff", "approved_by")
        if self.request.user.role == User.Roles.STAFF:
            qs = qs.filter(staff=self.request.user)
        return qs


class SalaryAdvanceCreateView(StaffOrAboveRequiredMixin, FormTitleMixin, CreateView):
    model = SalaryAdvance
    form_class = SalaryAdvanceRequestForm
    template_name = "shop/form.html"
    success_url = reverse_lazy("salary-advance-list")
    form_title = "Request Salary Advance"

    def form_valid(self, form):
        advance = form.save(commit=False)
        advance.staff = self.request.user
        advance.status = SalaryAdvance.Status.PENDING
        advance.outstanding_balance = Decimal("0.00")
        advance.save()
        messages.success(self.request, "Salary advance request submitted.")
        return redirect(self.success_url)


class SalaryAdvanceReviewView(ManagerOrAdminRequiredMixin, FormTitleMixin, UpdateView):
    model = SalaryAdvance
    form_class = SalaryAdvanceDecisionForm
    template_name = "shop/form.html"
    success_url = reverse_lazy("salary-advance-list")
    form_title = "Review Salary Advance"

    @transaction.atomic
    def form_valid(self, form):
        advance = form.save(commit=False)
        status = form.cleaned_data["status"]
        approved_amount = form.cleaned_data.get("approved_amount")
        if status == SalaryAdvance.Status.APPROVED:
            advance.approved_amount = approved_amount
            if advance.status == SalaryAdvance.Status.PENDING:
                advance.outstanding_balance = approved_amount
            advance.approved_by = self.request.user
            advance.approved_at = timezone.now()
        elif status in [SalaryAdvance.Status.REJECTED, SalaryAdvance.Status.CANCELLED]:
            advance.approved_amount = None
            advance.outstanding_balance = Decimal("0.00")
            advance.approved_by = self.request.user
            advance.approved_at = timezone.now()
        advance.save()
        messages.success(self.request, "Salary advance updated.")
        return redirect(self.success_url)


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
        rate = item["staff__commission_rate"]
        if rate is None:
            rate = Decimal("0.00")
        total = item["total_sales"] or Decimal("0.00")
        earnings = (total * rate) / Decimal("100.00")
        by_staff.append(
            {
                "name": item["staff__full_name"] or "Unassigned",
                "total_sales": total,
                "commission_rate": rate,
                "staff_earnings": earnings,
                "shop_net": total - earnings,
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


class SaleChangeRequestListView(AdminRequiredMixin, ListView):
    model = SaleChangeRequest
    template_name = "shop/sale_change_list.html"
    context_object_name = "change_requests"

    def get_queryset(self):
        return (
            SaleChangeRequest.objects.filter(status=SaleChangeRequest.Status.PENDING)
            .select_related("sale", "sale__service", "requested_by")
            .order_by("requested_at")
        )


class SaleChangeRequestReviewView(AdminRequiredMixin, TemplateView):
    template_name = "shop/sale_change_review.html"

    def get_change_request(self):
        return get_object_or_404(
            SaleChangeRequest.objects.select_related(
                "sale",
                "sale__service",
                "sale__staff",
                "sale__customer",
                "requested_by",
                "service",
                "staff",
                "customer",
            ),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["change_request"] = self.get_change_request()
        context["review_form"] = SaleChangeReviewForm()
        context["sale_is_stale"] = (
            context["change_request"].sale.updated_at != context["change_request"].sale_updated_at_snapshot
        )
        return context

    def post(self, request, *args, **kwargs):
        change_request = self.get_change_request()
        action = request.POST.get("action")
        review_form = SaleChangeReviewForm(request.POST)

        if action == "approve":
            ok, error = approve_change_request(change_request, request.user)
            if ok:
                messages.success(request, "Sale change approved and applied.")
            else:
                messages.error(request, error)
            return redirect("sale-change-list")

        if action == "reject":
            if not review_form.is_valid():
                messages.error(request, "Could not reject this request.")
                return redirect("sale-change-review", pk=change_request.pk)
            ok, error = reject_change_request(
                change_request,
                request.user,
                review_form.cleaned_data.get("admin_notes", ""),
            )
            if ok:
                messages.success(request, "Sale change request rejected.")
            else:
                messages.error(request, error)
            return redirect("sale-change-list")

        messages.error(request, "Unknown action.")
        return redirect("sale-change-review", pk=change_request.pk)


class NotificationListView(LoginRequiredMixin, ListView):
    model = StaffNotification
    template_name = "shop/notifications.html"
    context_object_name = "notifications"
    paginate_by = 25

    def get_queryset(self):
        return StaffNotification.objects.filter(user=self.request.user).select_related("change_request")


def notification_open(request, pk):
    if not request.user.is_authenticated:
        return redirect("login")
    notification = get_object_or_404(StaffNotification, pk=pk, user=request.user)
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    if notification.link:
        return redirect(notification.link)
    return redirect("dashboard")
