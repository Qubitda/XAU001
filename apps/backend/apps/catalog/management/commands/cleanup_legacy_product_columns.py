"""Verify that ProductModel rows have synchronized normalized detail tables."""
import os

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import ProductModel
from apps.catalog.product_kinds import normalize_product_kind


class Command(BaseCommand):
    help = "Verify legacy ProductModel columns match normalized Finished/Mounting/LooseStone detail tables."

    def handle(self, *args, **options):
        strict = os.environ.get("CATALOG_VERIFY_LEGACY_COLUMNS", "").lower() in ("1", "true", "yes")
        missing: list[str] = []
        for product in ProductModel.objects.select_related(
            "finished_detail", "mounting_detail", "loose_stone_detail"
        ).iterator():
            kind = normalize_product_kind(product.product_kind)
            if kind == ProductModel.ProductKind.FINISHED and not hasattr(product, "finished_detail"):
                missing.append(f"{product.parent_sku}:finished_detail")
            elif kind == ProductModel.ProductKind.MOUNTING and not hasattr(product, "mounting_detail"):
                missing.append(f"{product.parent_sku}:mounting_detail")
            elif kind == ProductModel.ProductKind.LOOSE_STONE and not hasattr(product, "loose_stone_detail"):
                missing.append(f"{product.parent_sku}:loose_stone_detail")

        if missing:
            msg = f"Missing normalized detail rows ({len(missing)}): {', '.join(missing[:20])}"
            if strict:
                raise CommandError(msg)
            self.stdout.write(self.style.WARNING(msg))
            return

        self.stdout.write(self.style.SUCCESS("All ProductModel rows have matching normalized detail tables."))
