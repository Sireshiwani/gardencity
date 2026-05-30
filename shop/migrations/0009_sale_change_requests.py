import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def backfill_sale_timestamps(apps, schema_editor):
    Sale = apps.get_model("shop", "Sale")
    for sale in Sale.objects.all().iterator():
        anchor = sale.date or django.utils.timezone.now()
        if not sale.created_at:
            sale.created_at = anchor
        if not sale.updated_at:
            sale.updated_at = anchor
        sale.save(update_fields=["created_at", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0008_user_email_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="created_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="sale",
            name="updated_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_sale_timestamps, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="sale",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="sale",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.CreateModel(
            name="SaleChangeRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("cancelled", "Cancelled"), ("superseded", "Superseded")], db_index=True, default="pending", max_length=20)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("reason", models.TextField()),
                ("sale_updated_at_snapshot", models.DateTimeField(help_text="Sale.updated_at when this request was submitted; used to detect stale approvals.")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("admin_notes", models.TextField(blank=True)),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("payment_method", models.CharField(choices=[("cash", "Cash"), ("card", "Card"), ("transfer", "Transfer"), ("mobile", "Mobile Money")], max_length=20)),
                ("date", models.DateTimeField()),
                ("notes", models.TextField(blank=True)),
                ("new_first_name", models.CharField(blank=True, max_length=100)),
                ("new_last_name", models.CharField(blank=True, max_length=100)),
                ("new_email", models.EmailField(blank=True, max_length=254)),
                ("new_phone", models.CharField(blank=True, max_length=50)),
                ("appointment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="shop.appointment")),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="shop.customer")),
                ("requested_by", models.ForeignKey(limit_choices_to={"role__in": ["manager"]}, on_delete=django.db.models.deletion.CASCADE, related_name="sale_change_requests", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, limit_choices_to={"role__in": ["admin"]}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_sale_change_requests", to=settings.AUTH_USER_MODEL)),
                ("sale", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="change_requests", to="shop.sale")),
                ("service", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="shop.service")),
                ("staff", models.ForeignKey(blank=True, limit_choices_to={"role__in": ["admin", "manager", "staff"]}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-requested_at"],
            },
        ),
        migrations.CreateModel(
            name="StaffNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.CharField(max_length=500)),
                ("link", models.CharField(blank=True, max_length=255)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("change_request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="shop.salechangerequest")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
