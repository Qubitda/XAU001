import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RateSnapshot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("snapshot_code", models.CharField(db_index=True, max_length=40, unique=True)),
                (
                    "source_mode",
                    models.CharField(
                        choices=[("auto", "Canlı Piyasa Akışı"), ("manual", "Manuel Operasyon Girişi")],
                        default="auto",
                        max_length=12,
                    ),
                ),
                ("live_usd_sell", models.DecimalField(decimal_places=4, max_digits=14)),
                ("live_eur_sell", models.DecimalField(decimal_places=4, max_digits=14)),
                ("live_has_gold_try_sell", models.DecimalField(decimal_places=4, max_digits=14)),
                ("fx_base_rates", models.JSONField(default=dict)),
                ("is_current", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "db_table": "market_rate_snapshot",
                "ordering": ["-created_at"],
            },
        ),
    ]
