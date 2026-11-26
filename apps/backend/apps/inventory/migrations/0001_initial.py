import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0001_initial"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Warehouse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "branch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="organizations.branch",
                    ),
                ),
            ],
            options={
                "db_table": "inventory_warehouse",
            },
        ),
        migrations.CreateModel(
            name="WarehouseStock",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("quantity", models.PositiveIntegerField(default=0)),
                ("reserved_qty", models.PositiveIntegerField(default=0)),
                (
                    "variant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="warehouse_stocks",
                        to="catalog.productvariant",
                    ),
                ),
                (
                    "warehouse",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="variant_stocks",
                        to="inventory.warehouse",
                    ),
                ),
            ],
            options={
                "db_table": "inventory_warehouse_stock",
            },
        ),
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "movement_type",
                    models.CharField(
                        choices=[
                            ("INBOUND", "Stok Girişi"),
                            ("RESERVE", "Sipariş Rezervasyonu"),
                            ("RELEASE", "Rezervasyon İptali"),
                            ("SHIP", "Sevkiyat Çıkışı"),
                        ],
                        max_length=16,
                    ),
                ),
                ("quantity_delta", models.IntegerField()),
                ("reference_no", models.CharField(db_index=True, max_length=64)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stock_movements",
                        to="catalog.productmodel",
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stock_movements",
                        to="catalog.productvariant",
                    ),
                ),
                (
                    "warehouse",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stock_movements",
                        to="inventory.warehouse",
                    ),
                ),
            ],
            options={
                "db_table": "inventory_stock_movement",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="warehousestock",
            constraint=models.UniqueConstraint(
                fields=("variant", "warehouse"),
                name="uniq_warehouse_stock_variant_warehouse",
            ),
        ),
    ]
