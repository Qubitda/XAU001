from decimal import Decimal
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import uuid


def seed_initial_matrix(apps, schema_editor):
    ExchangeMetalMatrix = apps.get_model("market", "ExchangeMetalMatrix")
    ExchangeMetalRate = apps.get_model("market", "ExchangeMetalRate")
    RateSnapshot = apps.get_model("market", "RateSnapshot")

    if ExchangeMetalMatrix.objects.filter(organization__isnull=True).exists():
        return

    defaults = {
        "TRY": "1.0000",
        "USD": "42.0000",
        "EUR": "48.5000",
        "JPY": "0.2800",
        "GBP": "56.0000",
        "CNY": "5.8000",
        "AUD": "27.3000",
        "CAD": "30.4000",
        "CHF": "52.0000",
        "XAU": "168000.0000",
        "XAG": "1470.0000",
        "XPT": "42000.0000",
        "XPD": "44100.0000",
    }
    snap = RateSnapshot.objects.filter(is_current=True).order_by("-created_at").first()
    if snap and isinstance(snap.fx_base_rates, dict):
        for k, v in snap.fx_base_rates.items():
            code = str(k).upper()
            if code in defaults:
                try:
                    val = Decimal(str(v))
                    if val > 0:
                        defaults[code] = str(val)
                except Exception:
                    pass

    matrix = ExchangeMetalMatrix.objects.create(
        id=uuid.uuid4(),
        organization=None,
        version=1,
        status="ACTIVE",
        effective_at=snap.created_at if snap else None,
        note="Initial migration from active RateSnapshot",
    )
    metal_codes = {"XAU", "XAG", "XPT", "XPD"}
    for code, val_str in defaults.items():
        ExchangeMetalRate.objects.create(
            id=uuid.uuid4(),
            matrix=matrix,
            currency_code=code,
            base_value_try=Decimal(val_str),
            unit="TROY_OZ" if code in metal_codes else "UNIT",
            precision=4,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0001_initial"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExchangeMetalMatrix",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("version", models.PositiveIntegerField(default=1)),
                (
                    "status",
                    models.CharField(
                        choices=[("DRAFT", "Taslak"), ("ACTIVE", "Aktif"), ("ARCHIVED", "Arşivlendi")],
                        db_index=True,
                        default="DRAFT",
                        max_length=16,
                    ),
                ),
                ("effective_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.CharField(blank=True, default="", max_length=240)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="exchange_metal_matrices",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "db_table": "market_exchange_metal_matrix",
                "ordering": ["-version", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ExchangeMetalRate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("currency_code", models.CharField(db_index=True, max_length=8)),
                ("base_value_try", models.DecimalField(decimal_places=4, max_digits=16)),
                (
                    "unit",
                    models.CharField(
                        choices=[("UNIT", "1 Birim / TRY"), ("TROY_OZ", "1 Troy Ons / TRY")],
                        default="UNIT",
                        max_length=16,
                    ),
                ),
                ("precision", models.PositiveSmallIntegerField(default=4)),
                (
                    "matrix",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rates",
                        to="market.exchangemetalmatrix",
                    ),
                ),
            ],
            options={
                "db_table": "market_exchange_metal_rate",
                "ordering": ["currency_code"],
            },
        ),
        migrations.AddConstraint(
            model_name="exchangemetalmatrix",
            constraint=models.UniqueConstraint(
                condition=models.Q(("organization__isnull", False)),
                fields=("organization", "version"),
                name="uniq_org_exchange_metal_matrix_version",
            ),
        ),
        migrations.AddConstraint(
            model_name="exchangemetalmatrix",
            constraint=models.UniqueConstraint(
                condition=models.Q(("organization__isnull", True)),
                fields=("version",),
                name="uniq_global_exchange_metal_matrix_version",
            ),
        ),
        migrations.AddConstraint(
            model_name="exchangemetalrate",
            constraint=models.UniqueConstraint(
                fields=("matrix", "currency_code"),
                name="uniq_exchange_metal_rate_code",
            ),
        ),
        migrations.RunPython(seed_initial_matrix, migrations.RunPython.noop),
    ]
