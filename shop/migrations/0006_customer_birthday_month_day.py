from django.core import validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0005_customer_email_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="birthday_day",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[validators.MinValueValidator(1), validators.MaxValueValidator(31)],
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="birthday_month",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[validators.MinValueValidator(1), validators.MaxValueValidator(12)],
            ),
        ),
    ]
