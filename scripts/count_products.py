from apps.catalog.models import ProductModel

print("products", ProductModel.objects.count())
for sku, title in ProductModel.objects.values_list("parent_sku", "title")[:30]:
    print(sku, title)
