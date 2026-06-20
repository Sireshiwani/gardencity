from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0009_sale_change_requests"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="specialty",
            field=models.CharField(
                blank=True,
                help_text="Short public bio shown on the website (e.g. Precision fade specialist).",
                max_length=200,
            ),
        ),
    ]
