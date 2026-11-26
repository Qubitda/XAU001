import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkOrder",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("work_order_no", models.CharField(db_index=True, max_length=40, unique=True)),
                ("source_order_no", models.CharField(db_index=True, max_length=40)),
                ("sku", models.CharField(max_length=64)),
                ("size", models.PositiveSmallIntegerField(default=14)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("engraving_or_stamp_note", models.CharField(blank=True, default="", max_length=120)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PLANNED", "Planlandı"),
                            ("CASTING", "Döküm / Montür"),
                            ("SETTING", "Mıhlama"),
                            ("QUALITY_CHECK", "Kalite Kontrol & Tartım"),
                            ("COMPLETED", "Tamamlandı"),
                        ],
                        default="PLANNED",
                        max_length=20,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "db_table": "production_work_order",
                "ordering": ["-created_at"],
            },
        ),
    ]
