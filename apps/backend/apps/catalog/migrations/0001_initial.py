from decimal import Decimal
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
            name="ProductModel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("parent_sku", models.CharField(db_index=True, max_length=32, unique=True)),
                (
                    "owner_organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="catalog_products",
                        to="organizations.organization",
                    ),
                ),
                ("barcode", models.CharField(blank=True, default="", max_length=48)),
                ("title", models.CharField(max_length=240)),
                ("description", models.TextField(blank=True, default="")),
                ("visual_type", models.CharField(default="solitaire_ring", max_length=48)),
                ("collection", models.CharField(db_index=True, max_length=120)),
                ("category", models.CharField(db_index=True, max_length=80)),
                ("sub_category", models.CharField(blank=True, default="", max_length=120)),
                ("style_technique", models.CharField(blank=True, default="Modern", max_length=80)),
                ("occasion", models.CharField(blank=True, default="", max_length=80)),
                ("supplier_name", models.CharField(blank=True, default="", max_length=160)),
                ("warehouse_location", models.CharField(blank=True, default="", max_length=80)),
                (
                    "ownership_type",
                    models.CharField(
                        choices=[("Öz Mal", "Öz Mal"), ("Konsinye (Emanet)", "Konsinye (Emanet)")],
                        default="Öz Mal",
                        max_length=32,
                    ),
                ),
                (
                    "stock_status",
                    models.CharField(
                        choices=[
                            ("Stokta", "Stokta"),
                            ("Siparişe Özel", "Siparişe Özel"),
                            ("Tükendi", "Tükendi"),
                        ],
                        default="Stokta",
                        max_length=24,
                    ),
                ),
                ("stock_qty", models.PositiveIntegerField(default=1)),
                ("lead_time_days", models.PositiveSmallIntegerField(default=2)),
                ("metal_name", models.CharField(default="Altın", max_length=40)),
                ("purity_code", models.CharField(default="14K", max_length=8)),
                ("metal_color", models.CharField(default="Beyaz", max_length=24)),
                ("available_colors", models.JSONField(default=list)),
                ("gross_weight_gram", models.DecimalField(decimal_places=4, default=Decimal("3.0000"), max_digits=10)),
                ("fire_rate_pct", models.DecimalField(decimal_places=2, default=Decimal("2.00"), max_digits=6)),
                (
                    "mount_structure",
                    models.CharField(
                        choices=[("FULL", "Tek Parça (Full Montür)"), ("HEAD_BAND", "İki Parça (Taç + Kol)")],
                        default="FULL",
                        max_length=16,
                    ),
                ),
                ("allowed_carat_min", models.DecimalField(decimal_places=3, default=Decimal("0.100"), max_digits=6)),
                ("allowed_carat_max", models.DecimalField(decimal_places=3, default=Decimal("2.000"), max_digits=6)),
                ("head_code", models.CharField(blank=True, default="", max_length=48)),
                ("band_code", models.CharField(blank=True, default="", max_length=48)),
                ("head_weight_gram", models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True)),
                ("band_weight_gram", models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True)),
                ("stone_type", models.CharField(default="Pırlanta", max_length=48)),
                ("stone_measure_unit", models.CharField(default="ct", max_length=8)),
                ("stone_clarity", models.CharField(blank=True, default="VS1", max_length=24)),
                ("stone_color_grade", models.CharField(blank=True, default="F", max_length=24)),
                ("stone_cut_grade", models.CharField(blank=True, default="Excellent", max_length=32)),
                ("stone_cut_shape", models.CharField(blank=True, default="Yuvarlak (Round)", max_length=64)),
                ("stone_origin", models.CharField(blank=True, default="Doğal", max_length=48)),
                ("setting_type", models.CharField(blank=True, default="6 Tırnak", max_length=64)),
                ("certificate_agency", models.CharField(blank=True, default="GIA", max_length=32)),
                ("certificate_number", models.CharField(blank=True, default="", max_length=64)),
                ("variant_size", models.PositiveSmallIntegerField(default=14)),
                ("available_sizes", models.JSONField(default=list)),
                ("width_mm", models.DecimalField(decimal_places=2, default=Decimal("2.00"), max_digits=6)),
                ("thickness_mm", models.DecimalField(decimal_places=2, default=Decimal("1.60"), max_digits=6)),
                ("height_mm", models.DecimalField(decimal_places=2, default=Decimal("5.20"), max_digits=6)),
                ("is_resizable", models.BooleanField(default=True)),
                ("warranty_months", models.PositiveSmallIntegerField(default=24)),
                (
                    "insured_shipping_info",
                    models.CharField(default="Tam sigortalı Brinks / Loomis özel kurye", max_length=200),
                ),
                (
                    "return_policy_text",
                    models.TextField(
                        default="Standart stok ürünlerinde 14 gün içinde koşulsuz iade; kişiye özel ölçü ve lazer yazı ürünlerinde iade istisnası uygulanır."
                    ),
                ),
                ("seo_slug", models.SlugField(max_length=240, unique=True)),
                ("meta_title", models.CharField(blank=True, default="", max_length=240)),
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
            ],
            options={
                "db_table": "catalog_product_model",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="StoneLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("MERKEZ", "Merkez Taş"),
                            ("YAN", "Yan Taş"),
                            ("PAVE", "Pavé"),
                            ("AKSAN", "Aksan"),
                        ],
                        default="MERKEZ",
                        max_length=16,
                    ),
                ),
                ("stone_type", models.CharField(default="Pırlanta", max_length=48)),
                ("measure_unit", models.CharField(default="ct", max_length=8)),
                ("count", models.PositiveSmallIntegerField(default=1)),
                ("carat", models.DecimalField(decimal_places=4, max_digits=8)),
                ("clarity", models.CharField(blank=True, default="", max_length=24)),
                ("color_grade", models.CharField(blank=True, default="", max_length=24)),
                ("cut_shape", models.CharField(blank=True, default="", max_length=64)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stone_lines",
                        to="catalog.productmodel",
                    ),
                ),
            ],
            options={
                "db_table": "catalog_stone_line",
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="ProductVariant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sku", models.CharField(db_index=True, max_length=64, unique=True)),
                ("purity_code", models.CharField(max_length=8)),
                ("metal_color", models.CharField(max_length=24)),
                ("size", models.PositiveSmallIntegerField(default=14)),
                ("center_stone_carat", models.DecimalField(decimal_places=3, default=Decimal("0.000"), max_digits=6)),
                ("gross_weight_gram", models.DecimalField(decimal_places=4, max_digits=10)),
                ("stock_qty", models.PositiveIntegerField(default=0)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="variants",
                        to="catalog.productmodel",
                    ),
                ),
            ],
            options={
                "db_table": "catalog_product_variant",
                "ordering": ["-is_default", "purity_code", "metal_color", "size"],
            },
        ),
        migrations.CreateModel(
            name="ProductMedia",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("metal_color", models.CharField(default="Beyaz", max_length=24)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("GALLERY_MAIN", "Ana Stüdyo"),
                            ("ON_HAND", "Elde / Model"),
                            ("MACRO", "Makro Detay"),
                            ("VIDEO_REELS", "Video / Reels"),
                            ("SPIN_360", "360 Derece"),
                            ("CERTIFICATE_PDF", "Sertifika"),
                        ],
                        default="GALLERY_MAIN",
                        max_length=24,
                    ),
                ),
                ("url", models.URLField(max_length=500)),
                ("sort_order", models.PositiveSmallIntegerField(default=1)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="media_items",
                        to="catalog.productmodel",
                    ),
                ),
            ],
            options={
                "db_table": "catalog_product_media",
                "ordering": ["metal_color", "sort_order"],
            },
        ),
        migrations.CreateModel(
            name="Favorite",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="favorited_by",
                        to="catalog.productmodel",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="favorites",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "catalog_favorite",
            },
        ),
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.UniqueConstraint(
                fields=("product", "purity_code", "metal_color", "size", "center_stone_carat"),
                name="uniq_variant_axes_per_product",
            ),
        ),
        migrations.AddConstraint(
            model_name="favorite",
            constraint=models.UniqueConstraint(fields=("user", "product"), name="uniq_favorite_user_product"),
        ),
    ]
