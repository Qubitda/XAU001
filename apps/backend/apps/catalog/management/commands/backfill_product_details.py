from django.core.management.base import BaseCommand

from apps.catalog.models import ProductModel
from apps.catalog.product_details import dual_write_product_details
from apps.catalog.product_kinds import normalize_product_kind


class Command(BaseCommand):
    help = "Backfill Finished/Mounting/LooseStone detail rows from legacy ProductModel columns."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report counts without writing.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        qs = ProductModel.objects.all().order_by("created_at")
        counts = {"FINISHED": 0, "MOUNTING": 0, "LOOSE_STONE": 0}
        for product in qs.iterator():
            kind = normalize_product_kind(product.product_kind or product.product_type)
            counts[kind] = counts.get(kind, 0) + 1
            if dry:
                continue
            product.product_kind = kind
            dual_write_product_details(product)
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Dry-run ' if dry else ''}backfill: "
                f"FINISHED={counts['FINISHED']} MOUNTING={counts['MOUNTING']} "
                f"LOOSE_STONE={counts['LOOSE_STONE']} total={sum(counts.values())}"
            )
        )
