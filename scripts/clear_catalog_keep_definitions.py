"""Delete seeded catalog + stock rows; keep definition tables/items intact."""

from django.apps import apps

WarehouseStock = apps.get_model("inventory", "WarehouseStock")
StockMovement = apps.get_model("inventory", "StockMovement")
ProductMedia = apps.get_model("catalog", "ProductMedia")
ProductVariant = apps.get_model("catalog", "ProductVariant")
ProductModel = apps.get_model("catalog", "ProductModel")

n, _ = StockMovement.objects.all().delete()
print("deleted_stock_movements", n)
n, _ = WarehouseStock.objects.all().delete()
print("deleted_warehouse_stock", n)
n, _ = ProductMedia.objects.all().delete()
print("deleted_media", n)
n, _ = ProductVariant.objects.all().delete()
print("deleted_variants", n)
n, _ = ProductModel.objects.all().delete()
print("deleted_products", n)
print("remaining_products", ProductModel.objects.count())
