# Generated manually for optional Customer.email (multiple walk-ins without email).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0004_loyalty_sms_templates"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appointment",
            name="customer_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AlterField(
            model_name="customer",
            name="email",
            field=models.EmailField(blank=True, db_index=True, max_length=254, null=True, unique=True),
        ),
    ]
