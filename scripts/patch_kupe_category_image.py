from apps.definitions.models import DefinitionItem

item = DefinitionItem.objects.filter(table__code="kategori", code="KUPE").first()
if item is None:
    raise SystemExit("KUPE missing")

meta = dict(item.meta or {})
meta["showOnStorefront"] = True
meta["storefrontImageUrl"] = "/media/definitions/category-earrings.jpg"
meta["storefrontImageAlt"] = "TARA DIAMOND sarı altın küpe kategorisi"
item.meta = meta
item.save(update_fields=["meta", "updated_at"])
print("KUPE", item.meta)
