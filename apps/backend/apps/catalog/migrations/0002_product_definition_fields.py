from django.db import migrations, models


def seed_default_sales_channels(apps, schema_editor):
    ProductModel = apps.get_model("catalog", "ProductModel")
    for product in ProductModel.objects.all().iterator():
        if not product.sales_channels:
            product.sales_channels = ["B2B", "B2B_API", "B2C_API"]
            product.save(update_fields=["sales_channels"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="productmodel",
            name="product_type",
            field=models.CharField(blank=True, default="Kuyum (Bitmiş Ürün)", max_length=80),
        ),
        migrations.AddField(
            model_name="productmodel",
            name="age_group",
            field=models.CharField(blank=True, default="Yetişkin", max_length=48),
        ),
        migrations.AddField(
            model_name="productmodel",
            name="sales_channels",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="productmodel",
            name="chain_type",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="productmodel",
            name="clasp_type",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="productmodel",
            name="purity_code",
            field=models.CharField(default="14K", max_length=16),
        ),
        migrations.AlterField(
            model_name="productmodel",
            name="metal_color",
            field=models.CharField(default="Beyaz", max_length=64),
        ),
        migrations.AlterField(
            model_name="productvariant",
            name="purity_code",
            field=models.CharField(max_length=16),
        ),
        migrations.AlterField(
            model_name="productvariant",
            name="metal_color",
            field=models.CharField(max_length=64),
        ),
        migrations.RunPython(seed_default_sales_channels, migrations.RunPython.noop),
    ]
