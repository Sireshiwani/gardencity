from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0006_customer_birthday_month_day"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="advance_deduction",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10),
        ),
        migrations.AddField(
            model_name="payment",
            name="gross_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.CreateModel(
            name="SalaryAdvance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("requested_amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("approved_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("outstanding_balance", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("partially_repaid", "Partially Repaid"),
                            ("repaid", "Repaid"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("reason", models.TextField(blank=True)),
                ("manager_notes", models.TextField(blank=True)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_salary_advances",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        limit_choices_to={"role__in": ["admin", "manager", "staff"]},
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="salary_advances",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-requested_at"]},
        ),
        migrations.CreateModel(
            name="SalaryAdvanceRepayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("applied_at", models.DateTimeField(auto_now_add=True)),
                (
                    "advance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="repayments",
                        to="shop.salaryadvance",
                    ),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="advance_repayments",
                        to="shop.payment",
                    ),
                ),
            ],
            options={"ordering": ["-applied_at"]},
        ),
    ]
