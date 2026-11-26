from django.db import transaction
from apps.catalog.models import ProductModel, ProductVariant
from config.exceptions import DomainError
from .models import StockMovement, Warehouse, WarehouseStock


def get_or_create_default_warehouse() -> Warehouse:
    wh = Warehouse.objects.filter(is_active=True).order_by("created_at").first()
    if wh is not None:
        return wh
    wh, _ = Warehouse.objects.get_or_create(
        code="WH-MERKEZ",
        defaults={"name": "Kuyumcukent Merkez Kasa", "is_active": True},
    )
    return wh


@transaction.atomic
def sync_variant_and_product_stock(variant: ProductVariant) -> tuple[ProductVariant, ProductModel]:
    """
    Recomputes ProductVariant.stock_qty from active WarehouseStock rows,
    then synchronizes ProductModel.stock_qty and stock_status atomically.
    """
    locked_variant = ProductVariant.objects.select_for_update().select_related("product").get(id=variant.id)
    locked_product = ProductModel.objects.select_for_update().get(id=locked_variant.product_id)

    ws_rows = list(
        WarehouseStock.objects.filter(variant=locked_variant, warehouse__is_active=True)
    )
    variant_available = sum(max(0, ws.quantity - ws.reserved_qty) for ws in ws_rows)
    locked_variant.stock_qty = variant_available
    locked_variant.save(update_fields=["stock_qty", "updated_at"])

    total_product_available = sum(
        ProductVariant.objects.filter(product=locked_product, is_active=True).values_list("stock_qty", flat=True)
    )
    locked_product.stock_qty = total_product_available
    if total_product_available > 0:
        locked_product.stock_status = ProductModel.StockStatus.IN_STOCK
    elif locked_product.stock_status != ProductModel.StockStatus.MADE_TO_ORDER:
        locked_product.stock_status = ProductModel.StockStatus.OUT_OF_STOCK
    locked_product.save(update_fields=["stock_qty", "stock_status", "updated_at"])
    return locked_variant, locked_product


@transaction.atomic
def set_variant_warehouse_stock(
    *,
    variant: ProductVariant,
    warehouse: Warehouse | None,
    quantity: int,
    reference_no: str,
    actor=None,
) -> WarehouseStock:
    wh = warehouse or get_or_create_default_warehouse()
    ws, created = WarehouseStock.objects.select_for_update().get_or_create(
        variant=variant,
        warehouse=wh,
        defaults={"quantity": max(0, quantity), "reserved_qty": 0},
    )
    prev_qty = 0 if created else ws.quantity
    delta = max(0, quantity) - prev_qty
    ws.quantity = max(0, quantity)
    ws.save(update_fields=["quantity", "updated_at"])

    if delta != 0:
        StockMovement.objects.create(
            product=variant.product,
            variant=variant,
            warehouse=wh,
            movement_type=StockMovement.MovementType.INBOUND if delta > 0 else StockMovement.MovementType.SHIP,
            quantity_delta=delta,
            reference_no=reference_no,
            actor=actor,
        )
    sync_variant_and_product_stock(variant)
    return ws


@transaction.atomic
def reserve_variant_stock(
    *,
    variant: ProductVariant,
    qty: int,
    reference_no: str,
    warehouse: Warehouse | None = None,
    actor=None,
) -> StockMovement | None:
    """
    Concurrency-safe variant + warehouse stock reservation.
    - Uses row-level locking on WarehouseStock.
    - Idempotent per (variant, reference_no, RESERVE).
    - Synchronizes ProductVariant.stock_qty and ProductModel.stock_qty/stock_status.
    """
    if qty <= 0:
        return None

    product = ProductModel.objects.select_for_update().get(id=variant.product_id)
    if product.stock_status == ProductModel.StockStatus.MADE_TO_ORDER:
        return None

    existing = StockMovement.objects.filter(
        variant=variant,
        reference_no=reference_no,
        movement_type=StockMovement.MovementType.RESERVE,
    ).first()
    if existing is not None:
        return existing

    ws_qs = WarehouseStock.objects.select_for_update().select_related("warehouse").filter(
        variant=variant,
        warehouse__is_active=True,
    )
    if warehouse is not None:
        ws_qs = ws_qs.filter(warehouse=warehouse)

    candidates = list(ws_qs)
    chosen = next(
        (ws for ws in sorted(candidates, key=lambda r: r.available_qty, reverse=True) if ws.available_qty >= qty),
        None,
    )
    if chosen is None:
        total_avail = sum(ws.available_qty for ws in candidates)
        raise DomainError(
            f"{variant.sku} varyantı için yeterli depo stoğu bulunmuyor (Mevcut: {total_avail}, Talep: {qty}).",
            code="INSUFFICIENT_STOCK",
            status_code=409,
        )

    chosen.reserved_qty += qty
    chosen.save(update_fields=["reserved_qty", "updated_at"])

    movement = StockMovement.objects.create(
        product=product,
        variant=variant,
        warehouse=chosen.warehouse,
        movement_type=StockMovement.MovementType.RESERVE,
        quantity_delta=-qty,
        reference_no=reference_no,
        actor=actor,
    )
    sync_variant_and_product_stock(variant)
    return movement


@transaction.atomic
def release_variant_stock(
    *,
    variant: ProductVariant,
    qty: int,
    reference_no: str,
    warehouse: Warehouse | None = None,
    actor=None,
) -> StockMovement | None:
    """
    Idempotent variant + warehouse stock release for order cancellation or refund.
    """
    if qty <= 0:
        return None

    existing_release = StockMovement.objects.filter(
        variant=variant,
        reference_no=reference_no,
        movement_type=StockMovement.MovementType.RELEASE,
    ).first()
    if existing_release is not None:
        return existing_release

    reserve_mv = (
        StockMovement.objects.select_related("warehouse")
        .filter(
            variant=variant,
            reference_no=reference_no,
            movement_type=StockMovement.MovementType.RESERVE,
        )
        .first()
    )
    if reserve_mv is None:
        return None

    target_wh = warehouse or reserve_mv.warehouse or get_or_create_default_warehouse()
    ws, _ = WarehouseStock.objects.select_for_update().get_or_create(
        variant=variant,
        warehouse=target_wh,
        defaults={"quantity": 0, "reserved_qty": 0},
    )
    release_amount = min(qty, abs(reserve_mv.quantity_delta))
    ws.reserved_qty = max(0, ws.reserved_qty - release_amount)
    ws.save(update_fields=["reserved_qty", "updated_at"])

    movement = StockMovement.objects.create(
        product=variant.product,
        variant=variant,
        warehouse=target_wh,
        movement_type=StockMovement.MovementType.RELEASE,
        quantity_delta=release_amount,
        reference_no=reference_no,
        actor=actor,
    )
    sync_variant_and_product_stock(variant)
    return movement


@transaction.atomic
def reserve_product_stock(
    *,
    parent_sku: str,
    qty: int,
    reference_no: str,
    variant: ProductVariant | None = None,
    actor=None,
) -> StockMovement | None:
    """
    Backward-compatible entry point that resolves the concrete ProductVariant
    and reserves stock against WarehouseStock.
    """
    if variant is not None:
        return reserve_variant_stock(variant=variant, qty=qty, reference_no=reference_no, actor=actor)

    product = ProductModel.objects.filter(parent_sku=parent_sku).first()
    if product is None:
        raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
    if product.stock_status == ProductModel.StockStatus.MADE_TO_ORDER:
        return None

    resolved_variant = (
        ProductVariant.objects.filter(product=product, is_active=True)
        .order_by("-is_default", "-stock_qty")
        .first()
    )
    if resolved_variant is None:
        raise DomainError(
            f"{parent_sku} ürünü için satılabilir varyant stok kaydı bulunamadı.",
            code="VARIANT_NOT_FOUND",
            status_code=409,
        )
    return reserve_variant_stock(variant=resolved_variant, qty=qty, reference_no=reference_no, actor=actor)


@transaction.atomic
def record_manual_stock_movement(
    *,
    variant: ProductVariant,
    warehouse: Warehouse,
    movement_type: str,
    quantity: int,
    reference_no: str,
    actor=None,
) -> StockMovement:
    """
    OPS ledger-driven stock movement service.
    Guarantees WarehouseStock, ProductVariant.stock_qty, and ProductModel.stock_qty stay in sync.
    """
    from apps.audit.services import record_audit

    if quantity <= 0:
        raise DomainError("Hareket adedi pozitif bir tam sayı olmalıdır.", code="INVALID_QTY", status_code=400)
    if not warehouse.is_active:
        raise DomainError("Pasif depoda stok hareketi yapılamaz.", code="WAREHOUSE_INACTIVE", status_code=400)

    ref = reference_no.strip()
    if not ref:
        raise DomainError("Referans numarası (referenceNo) zorunludur.", code="REFERENCE_REQUIRED", status_code=400)

    if movement_type == StockMovement.MovementType.RESERVE:
        mv = reserve_variant_stock(
            variant=variant, qty=quantity, reference_no=ref, warehouse=warehouse, actor=actor
        )
        if mv is None:
            raise DomainError("Siparişe özel ürünlerde rezervasyon hareketi oluşturulamaz.", code="MADE_TO_ORDER", status_code=400)
        return mv

    if movement_type == StockMovement.MovementType.RELEASE:
        mv = release_variant_stock(
            variant=variant, qty=quantity, reference_no=ref, warehouse=warehouse, actor=actor
        )
        if mv is None:
            raise DomainError("Bu referans için çözülecek aktif rezervasyon bulunamadı.", code="RESERVATION_NOT_FOUND", status_code=404)
        return mv

    existing = StockMovement.objects.filter(
        variant=variant,
        warehouse=warehouse,
        reference_no=ref,
        movement_type=movement_type,
    ).first()
    if existing is not None:
        return existing

    ws, _ = WarehouseStock.objects.select_for_update().get_or_create(
        variant=variant,
        warehouse=warehouse,
        defaults={"quantity": 0, "reserved_qty": 0},
    )

    if movement_type == StockMovement.MovementType.INBOUND:
        ws.quantity += quantity
        delta = quantity
    elif movement_type == StockMovement.MovementType.SHIP:
        if ws.available_qty < quantity:
            raise DomainError(
                f"Depoda yeterli satılabilir stok yok (Mevcut: {ws.available_qty}, Çıkış: {quantity}).",
                code="INSUFFICIENT_STOCK",
                status_code=409,
            )
        ws.quantity -= quantity
        delta = -quantity
    else:
        raise DomainError("Geçersiz stok hareket türü.", code="INVALID_MOVEMENT_TYPE", status_code=400)

    ws.save(update_fields=["quantity", "updated_at"])
    movement = StockMovement.objects.create(
        product=variant.product,
        variant=variant,
        warehouse=warehouse,
        movement_type=movement_type,
        quantity_delta=delta,
        reference_no=ref,
        actor=actor,
    )
    sync_variant_and_product_stock(variant)
    record_audit(
        action="STOCK_MOVEMENT_RECORDED",
        entity_type="StockMovement",
        entity_id=str(movement.id),
        actor=actor,
        metadata={
            "variant_sku": variant.sku,
            "warehouse_code": warehouse.code,
            "movement_type": movement_type,
            "quantity_delta": delta,
            "reference_no": ref,
        },
    )
    return movement


@transaction.atomic
def transfer_warehouse_stock(
    *,
    variant: ProductVariant,
    source_warehouse: Warehouse,
    target_warehouse: Warehouse,
    quantity: int,
    reference_no: str,
    actor=None,
) -> tuple[StockMovement, StockMovement]:
    """
    Atomic warehouse-to-warehouse transfer with deterministic lock ordering to prevent deadlocks.
    """
    from apps.audit.services import record_audit

    if source_warehouse.id == target_warehouse.id:
        raise DomainError("Kaynak ve hedef depo aynı olamaz.", code="SAME_WAREHOUSE", status_code=400)
    if not source_warehouse.is_active or not target_warehouse.is_active:
        raise DomainError("Transfer için kaynak ve hedef depolar aktif olmalıdır.", code="WAREHOUSE_INACTIVE", status_code=400)
    if quantity <= 0:
        raise DomainError("Transfer adedi pozitif olmalıdır.", code="INVALID_QTY", status_code=400)

    ref = reference_no.strip()
    existing_out = StockMovement.objects.filter(
        variant=variant,
        warehouse=source_warehouse,
        reference_no=ref,
        movement_type=StockMovement.MovementType.SHIP,
    ).first()
    existing_in = StockMovement.objects.filter(
        variant=variant,
        warehouse=target_warehouse,
        reference_no=ref,
        movement_type=StockMovement.MovementType.INBOUND,
    ).first()
    if existing_out is not None and existing_in is not None:
        return existing_out, existing_in

    # Lock in deterministic UUID order to prevent deadlocks under concurrent transfers
    ordered_whs = sorted([source_warehouse, target_warehouse], key=lambda w: str(w.id))
    locked: dict[str, WarehouseStock] = {}
    for wh in ordered_whs:
        ws, _ = WarehouseStock.objects.select_for_update().get_or_create(
            variant=variant,
            warehouse=wh,
            defaults={"quantity": 0, "reserved_qty": 0},
        )
        locked[str(wh.id)] = ws

    src_ws = locked[str(source_warehouse.id)]
    dst_ws = locked[str(target_warehouse.id)]

    if src_ws.available_qty < quantity:
        raise DomainError(
            f"Kaynak depoda yeterli stok yok (Mevcut: {src_ws.available_qty}, Talep: {quantity}).",
            code="INSUFFICIENT_STOCK",
            status_code=409,
        )

    src_ws.quantity -= quantity
    dst_ws.quantity += quantity
    src_ws.save(update_fields=["quantity", "updated_at"])
    dst_ws.save(update_fields=["quantity", "updated_at"])

    out_mv = StockMovement.objects.create(
        product=variant.product,
        variant=variant,
        warehouse=source_warehouse,
        movement_type=StockMovement.MovementType.SHIP,
        quantity_delta=-quantity,
        reference_no=ref,
        actor=actor,
    )
    in_mv = StockMovement.objects.create(
        product=variant.product,
        variant=variant,
        warehouse=target_warehouse,
        movement_type=StockMovement.MovementType.INBOUND,
        quantity_delta=quantity,
        reference_no=ref,
        actor=actor,
    )
    sync_variant_and_product_stock(variant)
    record_audit(
        action="STOCK_TRANSFERRED",
        entity_type="ProductVariant",
        entity_id=variant.sku,
        actor=actor,
        metadata={
            "from_warehouse": source_warehouse.code,
            "to_warehouse": target_warehouse.code,
            "quantity": quantity,
            "reference_no": ref,
        },
    )
    return out_mv, in_mv
