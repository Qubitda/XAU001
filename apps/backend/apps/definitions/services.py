"""
Definition domain services: seed, lookups, and item write rules.

API views stay thin; catalog/pricing import lookup helpers from here.
Model names (DefinitionTable / DefinitionItem) are the persistence schema — do not rename.
"""

from __future__ import annotations

from typing import Any, Iterable
from uuid import UUID

from django.db import transaction

from apps.definitions.models import DefinitionItem, DefinitionTable
from apps.definitions.seed_data import DEFINITION_ITEMS, DEFINITION_TABLES
from apps.definitions.serialize import serialize_item, serialize_table
from config.exceptions import DomainError

# Re-export wire serializers for existing importers (seed commands, older call sites).
__all__ = [
    "PROTECTED_META_KEYS",
    "children_for_parent",
    "create_definition_item",
    "deactivate_definition_item",
    "delete_definition_item",
    "find_item_by_label_or_code",
    "get_active_items_by_table_code",
    "get_definition_item",
    "get_definition_table",
    "list_definition_tables",
    "list_table_items",
    "merge_item_meta",
    "normalize_item_code",
    "purity_fineness_map",
    "resolve_parent_items",
    "seed_definition_tables",
    "serialize_item",
    "serialize_table",
    "update_definition_item",
]

PROTECTED_META_KEYS: frozenset[str] = frozenset({"fineness"})


def normalize_item_code(raw: str) -> str:
    return (raw or "").strip().upper().replace(" ", "_")


def merge_item_meta(
    existing: dict | None,
    incoming: dict | None,
    *,
    is_system: bool,
) -> dict:
    """
    Merge meta payloads while preserving calculation-critical keys (e.g. fineness).
    System items never lose protected keys even if the client overwrites them.
    """
    base = dict(existing or {})
    next_meta = dict(incoming or {})
    for key in PROTECTED_META_KEYS:
        if key not in base:
            continue
        if key not in next_meta or is_system:
            next_meta[key] = base[key]
    return next_meta


def get_definition_table(table_code: str, *, with_items: bool = False) -> DefinitionTable:
    qs = DefinitionTable.objects.select_related("parent_table")
    if with_items:
        qs = qs.prefetch_related("items__parents")
    table = qs.filter(code=table_code).first()
    if table is None:
        raise DomainError(
            "Tanım tablosu bulunamadı.",
            code="DEFINITION_TABLE_NOT_FOUND",
            status_code=404,
        )
    return table


def get_definition_item(item_id) -> DefinitionItem:
    item = (
        DefinitionItem.objects.select_related("table", "table__parent_table")
        .prefetch_related("parents")
        .filter(id=item_id)
        .first()
    )
    if item is None:
        raise DomainError(
            "Tanım kalemi bulunamadı.",
            code="DEFINITION_ITEM_NOT_FOUND",
            status_code=404,
        )
    return item


def list_definition_tables(*, include_items: bool = True):
    qs = (
        DefinitionTable.objects.select_related("parent_table")
        .prefetch_related("child_tables")
        .order_by("sort_order", "name")
    )
    if include_items:
        qs = qs.prefetch_related("items__parents")
    return qs


def list_table_items(
    table: DefinitionTable,
    *,
    is_active: bool | None = None,
    parent_id: str = "",
    parent_code: str = "",
    parent_label: str = "",
):
    items = table.items.prefetch_related("parents").all()
    if is_active is not None:
        items = items.filter(is_active=is_active)
    if parent_id:
        items = items.filter(parents__id=parent_id)
    elif parent_code and table.parent_table_id:
        items = items.filter(parents__code=parent_code, parents__table_id=table.parent_table_id)
    elif parent_label and table.parent_table_id:
        items = items.filter(parents__label=parent_label, parents__table_id=table.parent_table_id)
    return items.distinct()


def resolve_parent_items(
    table: DefinitionTable,
    parent_ids: Iterable[UUID | str] | None,
) -> list[DefinitionItem]:
    """Validate and load parent options for a child definition group."""
    ids = list(parent_ids or [])
    if not table.parent_table_id:
        if ids:
            raise DomainError(
                "Bu tanım grubu üst tanıma bağlanmaz.",
                code="DEFINITION_NO_PARENT_TABLE",
                status_code=400,
            )
        return []
    if not ids:
        raise DomainError(
            f"Bu grup için üst tanım zorunlu ({table.parent_table.code}).",
            code="DEFINITION_PARENT_REQUIRED",
            status_code=400,
        )
    parents = list(
        DefinitionItem.objects.filter(
            id__in=ids,
            table_id=table.parent_table_id,
            is_active=True,
        )
    )
    if len(parents) != len({str(x) for x in ids}):
        raise DomainError(
            "Geçersiz veya pasif üst tanım seçildi.",
            code="DEFINITION_PARENT_INVALID",
            status_code=400,
        )
    return parents


@transaction.atomic
def create_definition_item(
    table: DefinitionTable,
    *,
    code: str,
    label: str,
    meta: dict | None = None,
    sort_order: int = 100,
    is_active: bool = True,
    parent_ids: list | None = None,
) -> DefinitionItem:
    normalized = normalize_item_code(code)
    if not normalized:
        raise DomainError("Teknik kod zorunludur.", code="DEFINITION_CODE_REQUIRED", status_code=400)
    if DefinitionItem.objects.filter(table=table, code=normalized).exists():
        raise DomainError("Bu kod zaten tanımlı.", code="DEFINITION_ITEM_EXISTS", status_code=400)
    parents = resolve_parent_items(table, parent_ids)
    item = DefinitionItem.objects.create(
        table=table,
        code=normalized,
        label=(label or "").strip(),
        meta=dict(meta or {}),
        sort_order=sort_order,
        is_active=is_active,
        is_system=False,
    )
    if parents:
        item.parents.set(parents)
    return item


@transaction.atomic
def update_definition_item(item: DefinitionItem, data: dict[str, Any]) -> DefinitionItem:
    """
    Apply a validated patch dict (API field names: code, label, meta, sortOrder, isActive, parentIds).
    """
    if "code" in data:
        if item.is_system:
            raise DomainError(
                "Sistem tanımının teknik kodu değiştirilemez.",
                code="DEFINITION_SYSTEM_CODE_LOCKED",
                status_code=403,
            )
        new_code = normalize_item_code(data["code"])
        if (
            DefinitionItem.objects.filter(table=item.table, code=new_code)
            .exclude(id=item.id)
            .exists()
        ):
            raise DomainError("Bu kod zaten tanımlı.", code="DEFINITION_ITEM_EXISTS", status_code=400)
        item.code = new_code
    if "label" in data:
        item.label = (data["label"] or "").strip()
    if "meta" in data:
        item.meta = merge_item_meta(item.meta, data.get("meta"), is_system=item.is_system)
    if "sortOrder" in data:
        item.sort_order = data["sortOrder"]
    if "isActive" in data:
        item.is_active = bool(data["isActive"])
    item.save()
    if "parentIds" in data:
        parents = resolve_parent_items(item.table, data.get("parentIds") or [])
        item.parents.set(parents)
    return item


@transaction.atomic
def deactivate_definition_item(item: DefinitionItem) -> DefinitionItem:
    item.is_active = False
    item.save(update_fields=["is_active", "updated_at"])
    return item


@transaction.atomic
def delete_definition_item(item: DefinitionItem, *, hard: bool = True) -> DefinitionItem | None:
    """
    Remove a definition option.
    hard=True (default): permanent delete. System seeds can be restored via seed refresh.
    hard=False: soft-deactivate only.
    """
    if not hard:
        return deactivate_definition_item(item)
    item.delete()
    return None


def seed_definition_tables(*, reset_system_items: bool = False) -> dict[str, int]:
    """
    Upsert canonical Tanım_Tablosu seed with parent relations.
    Custom (non-system) items are preserved unless reset_system_items deletes system rows first.
    """
    tables_by_code: dict[str, DefinitionTable] = {}

    for code, name, description, sort_order, _parent_code in DEFINITION_TABLES:
        table, _ = DefinitionTable.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "sort_order": sort_order,
                "is_active": True,
                "is_system": True,
            },
        )
        tables_by_code[code] = table
        if reset_system_items:
            table.items.filter(is_system=True).delete()

    for code, _name, _desc, _sort, parent_code in DEFINITION_TABLES:
        table = tables_by_code[code]
        desired = tables_by_code.get(parent_code) if parent_code else None
        if table.parent_table_id != (desired.id if desired else None):
            table.parent_table = desired
            table.save(update_fields=["parent_table", "updated_at"])

    items_by_key: dict[tuple[str, str], DefinitionItem] = {}
    for table_code, item_code, label, meta, item_sort, _parents in DEFINITION_ITEMS:
        table = tables_by_code[table_code]
        item, _ = DefinitionItem.objects.update_or_create(
            table=table,
            code=item_code,
            defaults={
                "label": label,
                "meta": meta or {},
                "sort_order": item_sort,
                "is_active": True,
                "is_system": True,
            },
        )
        items_by_key[(table_code, item_code)] = item

    links = 0
    for table_code, item_code, _label, _meta, _sort, parent_codes in DEFINITION_ITEMS:
        item = items_by_key[(table_code, item_code)]
        child_table = tables_by_code[table_code]
        parent_table = child_table.parent_table
        if not parent_codes:
            item.parents.clear()
            continue
        if parent_table is None:
            continue
        parent_objs = []
        for pc in parent_codes:
            parent = items_by_key.get((parent_table.code, pc))
            if parent is not None:
                parent_objs.append(parent)
        item.parents.set(parent_objs)
        links += len(parent_objs)

    return {
        "tables": len(tables_by_code),
        "items": len(items_by_key),
        "links": links,
    }


def get_active_items_by_table_code(table_code: str) -> list[DefinitionItem]:
    return list(
        DefinitionItem.objects.filter(
            table__code=table_code,
            table__is_active=True,
            is_active=True,
        )
        .select_related("table")
        .prefetch_related("parents")
        .order_by("sort_order", "label")
    )


def find_item_by_label_or_code(table_code: str, value: str) -> DefinitionItem | None:
    value = (value or "").strip()
    if not value:
        return None
    qs = DefinitionItem.objects.filter(table__code=table_code, is_active=True)
    return qs.filter(code=value).first() or qs.filter(label=value).first()


def children_for_parent(
    child_table_code: str,
    *,
    parent_table_code: str,
    parent_value: str,
) -> list[DefinitionItem]:
    """Return active child items linked to a parent identified by code or label."""
    parent = find_item_by_label_or_code(parent_table_code, parent_value)
    if parent is None:
        return []
    return list(
        DefinitionItem.objects.filter(
            table__code=child_table_code,
            is_active=True,
            parents=parent,
        )
        .prefetch_related("parents")
        .order_by("sort_order", "label")
    )


def purity_fineness_map() -> dict[str, float]:
    """Map ayar_kodu code/label → meta.fineness for pricing calculations."""
    out: dict[str, float] = {}
    for item in get_active_items_by_table_code("ayar_kodu"):
        fineness = (item.meta or {}).get("fineness")
        if fineness is None:
            continue
        try:
            value = float(fineness)
        except (TypeError, ValueError):
            continue
        out[item.code] = value
        out[item.label] = value
    return out
