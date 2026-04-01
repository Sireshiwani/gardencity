from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Appointment, Expense, Payment, Sale, Service, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ("username", "full_name", "email", "role", "commission_rate", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Barbershop", {"fields": ("full_name", "role", "commission_rate")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Barbershop", {"fields": ("full_name", "email", "role", "commission_rate")}),
    )


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "duration_minutes", "is_active")
    list_filter = ("category", "is_active")


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("service", "staff", "price", "payment_method", "date")
    list_filter = ("payment_method", "service__category")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("category", "amount", "date")
    list_filter = ("category",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("staff", "amount", "date", "period_start", "period_end")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("customer_name", "service", "staff", "appointment_at", "status")
    list_filter = ("status", "service")
