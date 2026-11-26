"""One-shot: set kategori meta.showOnStorefront defaults on existing DB."""

from apps.definitions.models import DefinitionItem

CODES_ON = {"YUZUK", "KOLYE", "KUPE", "BILEKLIK"}

qs = DefinitionItem.objects.filter(table__code="kategori")
updated = 0
for item in qs:
    meta = dict(item.meta or {})
    meta["showOnStorefront"] = item.code in CODES_ON
    item.meta = meta
    item.save(update_fields=["meta", "updated_at"])
    updated += 1
    print(item.code, meta.get("showOnStorefront"))

print("updated", updated)
