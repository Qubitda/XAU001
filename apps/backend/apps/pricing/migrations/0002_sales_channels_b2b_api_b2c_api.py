from django.db import migrations, models


def forwards_channels(apps, schema_editor):
    ChannelRule = apps.get_model("pricing", "ChannelRule")
    PriceQuote = apps.get_model("pricing", "PriceQuote")

    ChannelRule.objects.filter(channel="B2C").update(channel="B2C_API")
    PriceQuote.objects.filter(channel="B2C").update(channel="B2C_API")

    # Expand BOTH into B2B + B2C_API clones (skip if target already exists)
    for rule in ChannelRule.objects.filter(channel="BOTH"):
        exists_b2b = ChannelRule.objects.filter(recipe_id=rule.recipe_id, channel="B2B").exists()
        exists_b2c = ChannelRule.objects.filter(recipe_id=rule.recipe_id, channel="B2C_API").exists()
        if not exists_b2b:
            rule.channel = "B2B"
            rule.save(update_fields=["channel"])
            if not exists_b2c:
                ChannelRule.objects.create(
                    recipe_id=rule.recipe_id,
                    channel="B2C_API",
                    profit_unit=rule.profit_unit,
                    profit_value=rule.profit_value,
                    discount_unit=rule.discount_unit,
                    discount_value=rule.discount_value,
                    servis_bedeli_unit=rule.servis_bedeli_unit,
                    servis_bedeli_value=rule.servis_bedeli_value,
                )
        else:
            if not exists_b2c:
                rule.channel = "B2C_API"
                rule.save(update_fields=["channel"])
            else:
                rule.delete()


def backwards_channels(apps, schema_editor):
    ChannelRule = apps.get_model("pricing", "ChannelRule")
    PriceQuote = apps.get_model("pricing", "PriceQuote")
    ChannelRule.objects.filter(channel="B2C_API").update(channel="B2C")
    ChannelRule.objects.filter(channel="B2B_API").update(channel="B2B")
    PriceQuote.objects.filter(channel="B2C_API").update(channel="B2C")
    PriceQuote.objects.filter(channel="B2B_API").update(channel="B2B")


class Migration(migrations.Migration):
    dependencies = [
        ("pricing", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="channelrule",
            name="channel",
            field=models.CharField(
                choices=[
                    ("B2B", "B2B (Bayi Portalı)"),
                    ("B2B_API", "B2B API"),
                    ("B2C_API", "B2C API"),
                ],
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="pricequote",
            name="channel",
            field=models.CharField(
                choices=[
                    ("B2B", "B2B"),
                    ("B2B_API", "B2B API"),
                    ("B2C_API", "B2C API"),
                ],
                max_length=16,
            ),
        ),
        migrations.RunPython(forwards_channels, backwards_channels),
    ]
