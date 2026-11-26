import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Customer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "customer_type",
                    models.CharField(
                        choices=[("INDIVIDUAL", "Bireysel Müşteri"), ("CORPORATE", "Kurumsal Müşteri")],
                        default="INDIVIDUAL",
                        max_length=16,
                    ),
                ),
                ("full_name", models.CharField(max_length=160)),
                ("phone", models.CharField(blank=True, default="", max_length=32)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("identity_or_tax_no", models.CharField(blank=True, default="", max_length=32)),
                ("city", models.CharField(blank=True, default="", max_length=100)),
                ("address", models.TextField(blank=True, default="")),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="customers",
                        to="organizations.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="customer_profiles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "customers_customer",
                "ordering": ["-created_at"],
            },
        ),
    ]
