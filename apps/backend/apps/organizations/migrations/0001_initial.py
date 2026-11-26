from decimal import Decimal
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(db_index=True, max_length=32, unique=True)),
                ("name", models.CharField(max_length=200)),
                (
                    "org_type",
                    models.CharField(
                        choices=[("PLATFORM_OWNER", "Platform Sahibi (Merkez)"), ("DEALER", "B2B Bayi Firma")],
                        default="DEALER",
                        max_length=24,
                    ),
                ),
                ("tax_office_and_no", models.CharField(blank=True, default="", max_length=120)),
                ("contact_name", models.CharField(blank=True, default="", max_length=120)),
                ("city", models.CharField(blank=True, default="", max_length=100)),
                ("default_consignment_days", models.PositiveSmallIntegerField(default=45)),
                ("is_active", models.BooleanField(default=True)),
                ("credit_limit_usd", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("used_credit_usd", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("has_limit_gram", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=12)),
                ("used_has_gram", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=12)),
            ],
            options={
                "db_table": "organizations_organization",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Branch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=160)),
                ("city", models.CharField(max_length=100)),
                ("address", models.TextField(blank=True, default="")),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="branches",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "db_table": "organizations_branch",
                "ordering": ["-is_default", "name"],
            },
        ),
        migrations.CreateModel(
            name="OrganizationMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "role_key",
                    models.CharField(
                        choices=[
                            ("SUPER_ADMIN", "Süper Admin"),
                            ("ORG_ADMIN", "Firma Yöneticisi"),
                            ("OPS", "Operasyon / Fiyatlama"),
                            ("B2B_BUYER", "B2B Satın Alma Yetkilisi"),
                            ("B2C_CUSTOMER", "Perakende Müşteri"),
                        ],
                        max_length=24,
                    ),
                ),
                ("custom_permissions", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("branches", models.ManyToManyField(blank=True, related_name="memberships", to="organizations.branch")),
                (
                    "default_branch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="organizations.branch",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="organizations.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "organizations_membership",
            },
        ),
        migrations.AddConstraint(
            model_name="branch",
            constraint=models.UniqueConstraint(
                fields=("organization", "code"), name="uniq_branch_code_per_organization"
            ),
        ),
        migrations.AddConstraint(
            model_name="organizationmembership",
            constraint=models.UniqueConstraint(
                fields=("user", "organization", "role_key"), name="uniq_user_org_role_membership"
            ),
        ),
    ]
