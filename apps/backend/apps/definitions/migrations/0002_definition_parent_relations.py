import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("definitions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="definitiontable",
            name="parent_table",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="child_tables",
                to="definitions.definitiontable",
            ),
        ),
        migrations.AddField(
            model_name="definitionitem",
            name="parents",
            field=models.ManyToManyField(
                blank=True,
                related_name="children",
                to="definitions.definitionitem",
            ),
        ),
    ]
