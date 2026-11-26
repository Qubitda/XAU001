import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DefinitionTable",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True, default="")),
                ("sort_order", models.PositiveSmallIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("is_system", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "definition_table",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="DefinitionItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(db_index=True, max_length=120)),
                ("label", models.CharField(max_length=240)),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("is_system", models.BooleanField(default=False)),
                (
                    "table",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="definitions.definitiontable",
                    ),
                ),
            ],
            options={
                "db_table": "definition_item",
                "ordering": ["sort_order", "label"],
            },
        ),
        migrations.AddIndex(
            model_name="definitionitem",
            index=models.Index(fields=["table", "is_active", "sort_order"], name="definition__table_i_7f0a1c_idx"),
        ),
        migrations.AddConstraint(
            model_name="definitionitem",
            constraint=models.UniqueConstraint(fields=("table", "code"), name="uniq_definition_item_code"),
        ),
    ]
