import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0002_exchange_metal_matrix"),
        ("pricing", "0002_sales_channels_b2b_api_b2c_api"),
    ]

    operations = [
        migrations.AddField(
            model_name="pricingrecipe",
            name="applied_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pricingrecipe",
            name="applied_rates_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="pricingrecipe",
            name="override_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="pricingrecipe",
            name="source_matrix",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pricing_recipes",
                to="market.exchangemetalmatrix",
            ),
        ),
        migrations.AddField(
            model_name="pricingrecipe",
            name="source_matrix_version",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
