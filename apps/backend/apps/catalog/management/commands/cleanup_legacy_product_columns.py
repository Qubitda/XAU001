"""
Phase-5 cleanup tooling (run only after dual-write + PRICING_READ_FROM_DETAILS
have been stable in production).

Does NOT drop columns by default. With --apply-drop and
CATALOG_ALLOW_LEGACY_DROP=1 it removes obsolete ProductModel metal/stone fields
from the database after verifying every product has a matching detail row.

Until then: keep CATALOG_DUAL_WRITE_DETAILS=1 and switch reads with
PRICING_READ_FROM_DETAILS=1.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.catalog.models import FinishedDetail, LooseStoneDetail, MountingDetail, ProductModel
from apps.catalog.product_kinds import FINISHED, LOOSE_STONE, MOUNTING, normalize_product_kind
from apps.common.security import assert_safe_sql_identifier

LEGACY_COLUMNS = [
    "metal_name",
    "purity_code",
    "metal_color",
    "gross_weight_gram",
    "fire_rate_pct",
    "mount_structure",
    "allowed_carat_min",
    "allowed_carat_max",
    "head_code",
    "band_code",
    "head_weight_gram",
    "band_weight_gram",
    "stone_type",
    "stone_measure_unit",
    "stone_clarity",
    "stone_color_grade",
    "stone_cut_grade",
    "stone_cut_shape",
    "stone_origin",
    "setting_type",
    "certificate_agency",
    "certificate_number",
]


class Command(BaseCommand):
    help = "Validate detail coverage and optionally DROP legacy ProductModel columns."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply-drop",
            action="store_true",
            help="Drop legacy columns (requires CATALOG_ALLOW_LEGACY_DROP=1).",
        )

    def handle(self, *args, **options):
        missing = []
        for product in ProductModel.objects.all().iterator():
            kind = normalize_product_kind(product.product_kind or product.product_type)
            ok = False
            if kind == FINISHED:
                ok = FinishedDetail.objects.filter(product_id=product.id).exists()
            elif kind == MOUNTING:
                ok = MountingDetail.objects.filter(product_id=product.id).exists()
            elif kind == LOOSE_STONE:
                ok = LooseStoneDetail.objects.filter(product_id=product.id).exists()
            if not ok:
                missing.append(f"{product.parent_sku}:{kind}")

        dual = getattr(settings, "CATALOG_DUAL_WRITE_DETAILS", True)
        read_details = getattr(settings, "PRICING_READ_FROM_DETAILS", False)
        self.stdout.write(
            f"Coverage: missing={len(missing)} dual_write={dual} pricing_read_from_details={read_details}"
        )
        if missing:
            preview = ", ".join(missing[:20])
            raise CommandError(
                f"{len(missing)} ürün detay satırı eksik. Önce backfill_product_details çalıştırın. Örnek: {preview}"
            )

        self.stdout.write(self.style.SUCCESS("Tüm ürünlerde tip detayı mevcut."))
        self.stdout.write(
            "Stabilize sonrası: PRICING_READ_FROM_DETAILS=1 → CATALOG_DUAL_WRITE_DETAILS=0 → "
            "CATALOG_ALLOW_LEGACY_DROP=1 + --apply-drop"
        )

        if not options["apply_drop"]:
            return

        if not getattr(settings, "CATALOG_ALLOW_LEGACY_DROP", False) and not (
            __import__("os").environ.get("CATALOG_ALLOW_LEGACY_DROP") == "1"
        ):
            raise CommandError("CATALOG_ALLOW_LEGACY_DROP=1 olmadan kolon düşürülemez.")
        if dual:
            raise CommandError("Önce CATALOG_DUAL_WRITE_DETAILS=0 yapın.")
        if not read_details:
            raise CommandError("Önce PRICING_READ_FROM_DETAILS=1 ile okumayı detaya alın.")

        table = assert_safe_sql_identifier(ProductModel._meta.db_table)
        qn = connection.ops.quote_name
        with connection.cursor() as cursor:
            for col in LEGACY_COLUMNS:
                safe_col = assert_safe_sql_identifier(col)
                # Identifiers only — never interpolate user input into DDL.
                cursor.execute(
                    f"ALTER TABLE {qn(table)} DROP COLUMN IF EXISTS {qn(safe_col)}"
                )
                self.stdout.write(f"Dropped column {col}")
        self.stdout.write(
            self.style.WARNING(
                "Kolonlar düşürüldü. Model alanlarını da koddan kaldırıp makemigrations state "
                "migration'ı ekleyin."
            )
        )
