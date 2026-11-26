from decimal import Decimal
from django.db import IntegrityError, transaction
from django.test import TestCase
from apps.catalog.models import ProductModel, ProductVariant
from apps.inventory.models import StockMovement, Warehouse, WarehouseStock


class WarehouseStockConstraintTests(TestCase):
    def setUp(self):
        self.product = ProductModel.objects.create(
            parent_sku="STK-001",
            title="Stock Test",
            category="Yüzük",
            collection="Test",
            purity_code="14K",
            metal_color="Beyaz",
            seo_slug="stk-001-test",
            available_colors=["Beyaz"],
            available_sizes=[14],
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="STK-001-14K-BYZ-14",
            purity_code="14K",
            metal_color="Beyaz",
            size=14,
            gross_weight_gram=Decimal("3.5000"),
            is_default=True,
        )
        self.warehouse = Warehouse.objects.create(code="WH-TEST", name="Test Depo")

    def test_reserved_cannot_exceed_quantity(self):
        ws = WarehouseStock.objects.create(
            variant=self.variant,
            warehouse=self.warehouse,
            quantity=5,
            reserved_qty=2,
        )
        ws.reserved_qty = 6
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ws.save()

    def test_stock_movement_reference_unique(self):
        StockMovement.objects.create(
            product=self.product,
            variant=self.variant,
            warehouse=self.warehouse,
            movement_type=StockMovement.MovementType.INBOUND,
            quantity_delta=3,
            reference_no="REF-1",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(
                    product=self.product,
                    variant=self.variant,
                    warehouse=self.warehouse,
                    movement_type=StockMovement.MovementType.INBOUND,
                    quantity_delta=1,
                    reference_no="REF-1",
                )
