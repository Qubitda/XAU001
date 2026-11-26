from django.db import migrations, models
import django.db.models.deletion


def strip_b2c_from_org_endpoints(apps, schema_editor):
    WebhookEndpoint = apps.get_model("webhooks", "WebhookEndpoint")
    for ep in WebhookEndpoint.objects.filter(is_platform=False).iterator():
        events = list(ep.events or [])
        cleaned = [e for e in events if e != "b2c.order.created"]
        if cleaned != events:
            ep.events = cleaned
            ep.save(update_fields=["events", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
        ("webhooks", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="webhookendpoint",
            name="is_platform",
            field=models.BooleanField(
                default=False,
                help_text="True → platform (B2C) events only; must not bind a dealer organization.",
            ),
        ),
        migrations.AlterField(
            model_name="webhookendpoint",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="webhook_endpoints",
                to="organizations.organization",
            ),
        ),
        migrations.AddIndex(
            model_name="webhookendpoint",
            index=models.Index(fields=["is_platform", "is_active"], name="webhook_end_is_plat_idx"),
        ),
        migrations.RunPython(strip_b2c_from_org_endpoints, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="webhookendpoint",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(is_platform=True, organization__isnull=True)
                    | models.Q(is_platform=False, organization__isnull=False)
                ),
                name="webhook_platform_xor_organization",
            ),
        ),
    ]
