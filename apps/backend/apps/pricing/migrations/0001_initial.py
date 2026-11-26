from decimal import Decimal
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0001_initial"),
        ("market", "0001_initial"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PricingRecipe",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("version", models.PositiveIntegerField(default=1)),
                (
                    "status",
                    models.CharField(
                        choices=[("TASLAK", "Taslak"), ("YAYINLANDI", "Yayında"), ("PASIF", "Pasif")],
                        db_index=True,
                        default="TASLAK",
                        max_length=16,
                    ),
                ),
                (
                    "pricing_mode",
                    models.CharField(
                        choices=[
                            ("1", "Model 1 — Detaylı (Maden + İşçilik + Taş + Montür + Diğer)"),
                            ("2", "Model 2 — Sade (Tedarikçi Hazır Fiyatı)"),
                        ],
                        default="1",
                        max_length=2,
                    ),
                ),
                ("lc_currency", models.CharField(default="TRY", max_length=8)),
                ("cached_total_cost_lc", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("cached_b2b_try", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("cached_b2c_try", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("cached_b2c_list_try", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                (
                    "last_snapshot",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="market.ratesnapshot",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pricing_recipes",
                        to="catalog.productmodel",
                    ),
                ),
            ],
            options={
                "db_table": "pricing_recipe",
                "ordering": ["-version"],
            },
        ),
        migrations.CreateModel(
            name="CostLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "line_type",
                    models.CharField(
                        choices=[
                            ("MADEN", "Maden Maliyeti"),
                            ("ISCILIK", "Toplam İşçilik Maliyeti"),
                            ("TAS", "Taş Maliyeti"),
                            ("MONTUR", "Montür Maliyeti"),
                            ("DIGER", "Diğer Maliyetler"),
                            ("TEDARIKCI", "Tedarikçi Hazır Fiyatı"),
                        ],
                        max_length=16,
                    ),
                ),
                ("fc_currency", models.CharField(default="USD", max_length=8)),
                ("fc_price", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("fc_price_manual", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("rate_override", models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True)),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cost_lines",
                        to="pricing.pricingrecipe",
                    ),
                ),
            ],
            options={
                "db_table": "pricing_cost_line",
            },
        ),
        migrations.CreateModel(
            name="ChannelRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "channel",
                    models.CharField(
                        choices=[("B2B", "B2B Toptan"), ("B2C", "B2C Perakende"), ("BOTH", "Her İkisi")],
                        max_length=8,
                    ),
                ),
                ("profit_unit", models.CharField(default="%", max_length=8)),
                ("profit_value", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=14)),
                ("discount_unit", models.CharField(default="%", max_length=8)),
                ("discount_value", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=14)),
                ("servis_bedeli_unit", models.CharField(default="%", max_length=8)),
                (
                    "servis_bedeli_value",
                    models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=14),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="channel_rules",
                        to="pricing.pricingrecipe",
                    ),
                ),
            ],
            options={
                "db_table": "pricing_channel_rule",
            },
        ),
        migrations.CreateModel(
            name="PriceQuote",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("channel", models.CharField(choices=[("B2B", "B2B"), ("B2C", "B2C")], max_length=8)),
                ("lc_currency", models.CharField(default="TRY", max_length=8)),
                ("list_price_try", models.DecimalField(decimal_places=2, max_digits=14)),
                ("final_price_lc", models.DecimalField(decimal_places=2, max_digits=14)),
                ("final_price_try", models.DecimalField(decimal_places=2, max_digits=14)),
                (
                    "effective_discount_pct",
                    models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=6),
                ),
                ("internal_audit_json", models.JSONField(default=dict)),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="organizations.organization",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="quotes",
                        to="catalog.productmodel",
                    ),
                ),
                (
                    "rate_snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="quotes",
                        to="market.ratesnapshot",
                    ),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="quotes",
                        to="pricing.pricingrecipe",
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="catalog.productvariant",
                    ),
                ),
            ],
            options={
                "db_table": "pricing_quote",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PriceLock",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "rate_snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="market.ratesnapshot",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="price_locks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "pricing_lock",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="pricingrecipe",
            constraint=models.UniqueConstraint(fields=("product", "version"), name="uniq_pricing_recipe_version"),
        ),
        migrations.AddConstraint(
            model_name="costline",
            constraint=models.UniqueConstraint(fields=("recipe", "line_type"), name="uniq_cost_line_per_recipe"),
        ),
        migrations.AddConstraint(
            model_name="channelrule",
            constraint=models.UniqueConstraint(fields=("recipe", "channel"), name="uniq_channel_rule_per_recipe"),
        ),
    ]
