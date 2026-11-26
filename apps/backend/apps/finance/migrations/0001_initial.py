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
            name="DealerLedgerEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "entry_type",
                    models.CharField(
                        choices=[
                            ("ORDER_DEBIT", "Sipariş Borçlandırma"),
                            ("ORDER_REVERSAL", "Sipariş İptal Ters Kayıt"),
                            ("REFUND_CREDIT", "İade Alacak Kaydı"),
                            ("PAYMENT_CREDIT", "Tahsilat / Alacak"),
                            ("HAS_DELIVERY", "Has Altın Teslimi"),
                        ],
                        max_length=24,
                    ),
                ),
                ("reference_no", models.CharField(db_index=True, max_length=64)),
                ("amount_usd", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("has_gold_gram", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=12)),
                ("note", models.CharField(blank=True, default="", max_length=240)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ledger_entries",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "db_table": "finance_dealer_ledger_entry",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="dealerledgerentry",
            constraint=models.UniqueConstraint(
                fields=("organization", "reference_no", "entry_type"),
                name="uniq_dealer_ledger_idempotency",
            ),
        ),
    ]
