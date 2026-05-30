from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Appointment,
    Customer,
    CustomerBarberNote,
    Expense,
    LoyaltySettings,
    Payment,
    PointsLedger,
    ReferralCredit,
    ReviewNudge,
    SMSLog,
    Sale,
    SalaryAdvance,
    SalaryAdvanceRepayment,
    SaleChangeRequest,
    Service,
    SlowHourWindow,
    StaffNotification,
    User,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ("username", "full_name", "email", "role", "commission_rate", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Barbershop", {"fields": ("full_name", "role", "commission_rate", "photo_url")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Barbershop", {"fields": ("full_name", "email", "role", "commission_rate", "photo_url")}),
    )


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "duration_minutes", "is_active")
    list_filter = ("category", "is_active")


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("service", "customer", "staff", "price", "payment_method", "date", "created_at")
    list_filter = ("payment_method", "service__category")
    raw_id_fields = ("customer", "appointment", "staff")


@admin.register(SaleChangeRequest)
class SaleChangeRequestAdmin(admin.ModelAdmin):
    list_display = ("sale", "status", "requested_by", "requested_at", "reviewed_by", "reviewed_at")
    list_filter = ("status",)
    raw_id_fields = ("sale", "requested_by", "reviewed_by", "service", "customer", "appointment", "staff")


@admin.register(StaffNotification)
class StaffNotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "read_at", "created_at")
    list_filter = ("read_at",)
    raw_id_fields = ("user", "change_request")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("category", "amount", "date")
    list_filter = ("category",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("staff", "gross_amount", "advance_deduction", "amount", "date", "period_start", "period_end")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("customer_name", "customer", "service", "staff", "appointment_at", "status", "completed_at")
    list_filter = ("status", "service")
    raw_id_fields = ("customer", "staff", "service")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "phone",
        "birthday_month",
        "birthday_day",
        "points_balance",
        "tier",
        "referral_code",
        "sms_opt_out",
    )
    search_fields = ("email", "phone", "first_name", "last_name", "referral_code")
    raw_id_fields = ("user", "referred_by")


@admin.register(LoyaltySettings)
class LoyaltySettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Points", {"fields": ("points_per_visit", "points_per_dollar", "referral_bonus_referrer", "referral_bonus_referee")}),
        ("Shop", {"fields": ("shop_display_name", "booking_base_url")}),
        ("Retention SMS", {"fields": ("sms_retention_enabled", "sms_retention_days", "retention_sms_template")}),
        ("Review SMS", {"fields": ("review_request_enabled", "review_request_hours_after", "review_bonus_points", "review_sms_template")}),
        ("Reports", {"fields": ("at_risk_days",)}),
    )

    def has_add_permission(self, request):
        return not LoyaltySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SlowHourWindow)
class SlowHourWindowAdmin(admin.ModelAdmin):
    list_display = ("name", "enabled", "weekday_start", "weekday_end", "time_start", "time_end", "multiplier")


@admin.register(PointsLedger)
class PointsLedgerAdmin(admin.ModelAdmin):
    list_display = ("customer", "points_delta", "balance_after", "entry_type", "created_at")
    list_filter = ("entry_type",)
    raw_id_fields = ("customer", "appointment", "sale")


@admin.register(ReferralCredit)
class ReferralCreditAdmin(admin.ModelAdmin):
    list_display = ("referrer", "referee", "created_at")


@admin.register(CustomerBarberNote)
class CustomerBarberNoteAdmin(admin.ModelAdmin):
    list_display = ("customer", "author", "created_at")
    raw_id_fields = ("customer", "author")


@admin.register(ReviewNudge)
class ReviewNudgeAdmin(admin.ModelAdmin):
    list_display = ("appointment", "customer", "sent_at", "channel")


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ("kind", "customer", "success", "sent_at")
    list_filter = ("kind", "success")


@admin.register(SalaryAdvance)
class SalaryAdvanceAdmin(admin.ModelAdmin):
    list_display = ("staff", "requested_amount", "approved_amount", "outstanding_balance", "status", "requested_at")
    list_filter = ("status",)
    raw_id_fields = ("staff", "approved_by")


@admin.register(SalaryAdvanceRepayment)
class SalaryAdvanceRepaymentAdmin(admin.ModelAdmin):
    list_display = ("advance", "payment", "amount", "applied_at")
    raw_id_fields = ("advance", "payment")
