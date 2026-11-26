"""Wire-format serializers for DefinitionTable / DefinitionItem (API responses)."""

from __future__ import annotations

from apps.definitions.models import DefinitionItem, DefinitionTable
from apps.definitions.usage_catalog import SYSTEM_FIXED_NOTES, enrich_table_payload


def serialize_item(item: DefinitionItem) -> dict:
    parents = list(item.parents.all())
    return {
        "id": str(item.id),
        "code": item.code,
        "label": item.label,
        "meta": item.meta or {},
        "sortOrder": item.sort_order,
        "isActive": item.is_active,
        "isSystem": item.is_system,
        "parentIds": [str(p.id) for p in parents],
        "parentCodes": [p.code for p in parents],
        "parentLabels": [p.label for p in parents],
        "createdAt": item.created_at.isoformat(),
        "updatedAt": item.updated_at.isoformat(),
    }


def serialize_table(table: DefinitionTable, *, include_items: bool = True) -> dict:
    payload = {
        "id": str(table.id),
        "code": table.code,
        "name": table.name,
        "description": table.description,
        "sortOrder": table.sort_order,
        "isActive": table.is_active,
        "isSystem": table.is_system,
        "parentTableCode": table.parent_table.code if table.parent_table_id else None,
        "parentTableName": table.parent_table.name if table.parent_table_id else None,
        "childTableCodes": [c.code for c in table.child_tables.all()],
    }
    if include_items:
        # Prefer prefetched cache when available; avoid a separate COUNT query.
        items = list(table.items.all())
        payload["itemCount"] = len(items)
        payload["activeItemCount"] = sum(1 for i in items if i.is_active)
        payload["items"] = [serialize_item(i) for i in items]
    else:
        payload["itemCount"] = table.items.count()
        payload["activeItemCount"] = table.items.filter(is_active=True).count()
    return enrich_table_payload(table.code, payload)


def serialize_definitions_bundle(tables: list[DefinitionTable], *, include_items: bool = True) -> dict:
    return {
        "tables": [serialize_table(t, include_items=include_items) for t in tables],
        "systemFixed": SYSTEM_FIXED_NOTES,
    }
