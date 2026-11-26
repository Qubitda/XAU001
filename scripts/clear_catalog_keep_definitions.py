"""Delete catalog products/variants/media; keep definition tables/items intact."""

from apps.catalog.models import ProductMedia, ProductModel, ProductVariant

variant_n, _ = ProductVariant.objects.all().delete()
media_n, _ = ProductMedia.objects.all().delete()
product_n, _ = ProductModel.objects.all().delete()
print("deleted_variants", variant_n)
print("deleted_media", media_n)
print("deleted_products", product_n)
print("remaining_products", ProductModel.objects.count())
