from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0007_salary_advance_and_payment_deduction"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
    ]
