"""OPS product list/create/detail endpoints."""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils.text import slugify
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import apply_safe_ordering, envelope_response, paginated_envelope_response
from apps.inventory.services import get_or_create_default_warehouse, set_variant_warehouse_stock
from apps.market.services import get_current_rate_snapshot
from apps.organizations.selectors import resolve_active_organization, resolve_tenant_context
from apps.pricing.models import ChannelRule, CostLine, PricingRecipe
from apps.pricing.services import publish_recipe
from config.exceptions import DomainError
from apps.catalog.models import ProductModel, ProductVariant, StoneLine
from apps.catalog.product_details import dual_write_product_details
from apps.catalog.product_kinds import kind_to_product_type_label, normalize_product_kind
from apps.catalog.services import sync_default_variant_center_carat, validate_publishable
from .common import (
    _apply_kind_fields,
    _detail_overrides_from_payload,
    _normalize_sales_channels,
    _parse_decimal,
    _parse_int,
    _sync_product_media,
)
from .ops_serializers import OpsProductSerializer
from .recipe_sync import _sync_recipe_from_ledger
from .serializers import _apply_filters, _products_queryset, serialize_ops_product

FIELD_PERMISSIONS: dict[str, str] = {
    "ledger": "pricing:edit",
    "pricingMode": "pricing:edit",
    "fireRatePct": "pricing:edit",
    "stockQty": "inventory:manage",
    "ownerOrganizationId": "orgs:manage",
    "salesChannels": "catalog:publish",
    "catalogStatus": "catalog:publish",
}


def _enforce_field_permissions(ctx, data: dict) -> None:
    for field_name, perm in FIELD_PERMISSIONS.items():
        if field_name in data and perm not in ctx.permissions:
            raise DomainError(
                f"'{field_name}' alanını değiştirmek için '{perm}' yetkisi gereklidir.",
                code="FORBIDDEN_FIELD",
                status_code=403,
            )


class OpsProductListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "catalog:read",
        "POST": "catalog:write",
    }

    def get(self, request: Request):
        rates = get_current_rate_snapshot()
        qs = _apply_filters(_products_queryset(), request)
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"createdAt": "created_at", "title": "title", "parentSku": "parent_sku"},
            default="-created_at",
        )
        return paginated_envelope_response(
            qs,
            request,
            lambda p: serialize_ops_product(p, p.published_recipes[0] if p.published_recipes else None, rates),
            default_page_size=24,
            max_page_size=100,
        )

    @transaction.atomic
    def post(self, request: Request):
        serializer = OpsProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        ctx = resolve_tenant_context(request)
        _enforce_field_permissions(ctx, {k: v for k, v in request.data.items() if k in FIELD_PERMISSIONS})
        sku = d["parentSku"].strip().upper()
        if ProductModel.objects.filter(parent_sku=sku).exists():
            raise DomainError(f"{sku} model kodu zaten katalogda mevcut.", code="DUPLICATE_SKU", status_code=409)

        owner_org = None
        if d.get("ownerOrganizationId"):
            owner_org = resolve_active_organization(d["ownerOrganizationId"])

        mount_spec = d.get("mountSpec") or {}
        raw_slug = slugify((d.get("seoSlug") or "").strip()) or slugify(f"{sku}-{d['title']}") or f"{sku.lower()}-mucevher"
        if ProductModel.objects.filter(seo_slug=raw_slug).exists():
            raw_slug = f"{raw_slug}-{sku.lower()}"

        initial_kind = normalize_product_kind(d.get("productKind") or d.get("productType"))
        erp_code = (d.get("erpCode") or "").strip() or None
        try:
            product = ProductModel.objects.create(
                parent_sku=sku,
                erp_code=erp_code,
                owner_organization=owner_org,
                catalog_status=d.get("catalogStatus") or ProductModel.CatalogStatus.DRAFT,
                barcode=d.get("barcode", ""),
                visual_type=d.get("visualType", "solitaire_ring"),
                title=d["title"],
                product_kind=initial_kind,
                product_type=kind_to_product_type_label(initial_kind),
                category=d["category"],
                sub_category=d["subCategory"],
                collection=d["collection"],
                style_technique=d.get("styleTechnique", "Modern"),
                occasion=d.get("occasion", ""),
                age_group=d.get("ageGroup") or "Yetişkin",
                metal_name=d.get("metalName") or "Altın",
                purity_code=d["purityCode"],
                metal_color=d["metalColor"],
                available_colors=d.get("availableColors") or ["Beyaz", "Sarı", "Rose"],
                sales_channels=_normalize_sales_channels(d.get("salesChannels")),
                stone_type=d["stoneType"],
                stone_measure_unit=d["stoneMeasureUnit"],
                stone_clarity=d.get("stoneClarity", ""),
                stone_color_grade=d.get("stoneColorGrade", ""),
                stone_cut_grade=d.get("stoneCutGrade", ""),
                stone_cut_shape=d.get("stoneCutShape", ""),
                stone_origin=d.get("stoneOrigin", ""),
                setting_type=d.get("settingType", ""),
                certificate_agency=d.get("certificateAgency", ""),
                certificate_number=d.get("certificateNumber", ""),
                gross_weight_gram=d["grossWeightGram"],
                fire_rate_pct=d["fireRatePct"],
                stock_status=(
                    ProductModel.StockStatus.OUT_OF_STOCK
                    if int(d["stockQty"]) <= 0 and d["stockStatus"] != ProductModel.StockStatus.MADE_TO_ORDER
                    else d["stockStatus"]
                ),
                stock_qty=d["stockQty"],
                lead_time_days=d.get("leadTimeDays", 2),
                ownership_type=d["ownershipType"],
                supplier_name=d.get("supplierName", ""),
                warehouse_location=d.get("warehouseLocation", ""),
                variant_size=d.get("variantSize", 0),
                available_sizes=d.get("availableSizes") or [],
                width_mm=d.get("widthMm", Decimal("2.00")),
                thickness_mm=d.get("thicknessMm", Decimal("1.60")),
                height_mm=d.get("heightMm", Decimal("5.20")),
                chain_type=d.get("chainType") or "",
                clasp_type=d.get("claspType") or "",
                is_resizable=d.get("isResizable", True),
                warranty_months=d.get("warrantyMonths", 24),
                insured_shipping_info=d.get("insuredShippingInfo", "Tam sigortalı Brinks / Loomis özel kurye"),
                return_policy_text=d.get("returnPolicyText") or "Standart stok ürünlerinde 14 gün içinde koşulsuz iade; kişiye özel ölçü ve lazer yazı ürünlerinde iade istisnası uygulanır.",
                description=d["description"],
                mount_structure=mount_spec.get("structure", ProductModel.MountStructure.FULL),
                allowed_carat_min=_parse_decimal(
                    mount_spec.get("allowedCaratMin"),
                    field_name="mountSpec.allowedCaratMin",
                    default=Decimal("0.100"),
                    min_value=Decimal("0"),
                ),
                allowed_carat_max=_parse_decimal(
                    mount_spec.get("allowedCaratMax"),
                    field_name="mountSpec.allowedCaratMax",
                    default=Decimal("2.000"),
                    min_value=Decimal("0"),
                ),
                head_code=mount_spec.get("headCode", ""),
                band_code=mount_spec.get("bandCode", ""),
                head_weight_gram=(
                    _parse_decimal(mount_spec["headWeightGram"], field_name="mountSpec.headWeightGram", min_value=Decimal("0"))
                    if mount_spec.get("headWeightGram") not in (None, "")
                    else None
                ),
                band_weight_gram=(
                    _parse_decimal(mount_spec["bandWeightGram"], field_name="mountSpec.bandWeightGram", min_value=Decimal("0"))
                    if mount_spec.get("bandWeightGram") not in (None, "")
                    else None
                ),
                seo_slug=raw_slug,
                meta_title=d.get("metaTitle") or d["title"],
                created_by=request.user,
            )
        except IntegrityError:
            raise DomainError(
                f"{sku} model kodu veya SEO slug zaten katalogda mevcut.",
                code="DUPLICATE_SKU",
                status_code=409,
            )

        _sync_product_media(
            product,
            gallery_images=d.get("galleryImages"),
            reels_video_url=d.get("reelsVideoUrl"),
            spin_360_url=d.get("spin360Url"),
            certificate_file_url=d.get("certificateFileUrl"),
        )

        incoming_stones = d.get("stoneLines")
        computed_center_carat = d["centerStoneCarat"]
        if incoming_stones:
            computed_center_carat = Decimal("0")
            for st in incoming_stones:
                st_role = st.get("role", StoneLine.Role.MERKEZ)
                st_count = _parse_int(st.get("count", 1), field_name="stoneLines.count", default=1, min_value=1)
                st_carat = _parse_decimal(st.get("carat", 0), field_name="stoneLines.carat", default=Decimal("0"), min_value=Decimal("0"))
                StoneLine.objects.create(
                    product=product,
                    role=st_role,
                    stone_type=st.get("stoneType", d["stoneType"]),
                    measure_unit=st.get("measureUnit", d["stoneMeasureUnit"]),
                    count=st_count,
                    carat=st_carat,
                    clarity=st.get("clarity", ""),
                    color_grade=st.get("colorGrade", ""),
                    cut_shape=st.get("cutShape", ""),
                )
                if st_role == StoneLine.Role.MERKEZ:
                    computed_center_carat += st_carat * st_count
        else:
            if d["centerStoneCarat"] > 0:
                StoneLine.objects.create(
                    product=product, role=StoneLine.Role.MERKEZ, stone_type=d["stoneType"], count=1, carat=d["centerStoneCarat"]
                )
            if d["sideStoneCarat"] > 0:
                StoneLine.objects.create(
                    product=product, role=StoneLine.Role.YAN, stone_type=d["stoneType"], count=1, carat=d["sideStoneCarat"]
                )

        # Always create a concrete default ProductVariant + WarehouseStock for every new model
        color_code = {"Beyaz": "BYZ", "Sarı": "SRY", "Rose": "RSE"}.get(
            product.metal_color,
            (slugify(product.metal_color).replace("-", "").upper()[:3] or "STD"),
        )
        try:
            default_variant = ProductVariant.objects.create(
                product=product,
                sku=f"{product.parent_sku}-{product.purity_code}-{color_code}-{product.variant_size}",
                purity_code=product.purity_code,
                metal_color=product.metal_color,
                size=product.variant_size,
                center_stone_carat=computed_center_carat,
                gross_weight_gram=product.gross_weight_gram,
                stock_qty=d["stockQty"],
                is_default=True,
            )
        except IntegrityError:
            raise DomainError(
                "Varsayılan varyant SKU'su başka bir varyantla çakışıyor.",
                code="DUPLICATE_VARIANT_SKU",
                status_code=409,
            )
        set_variant_warehouse_stock(
            variant=default_variant,
            warehouse=get_or_create_default_warehouse(),
            quantity=d["stockQty"],
            reference_no=f"INIT-{default_variant.sku}",
            actor=request.user,
        )

        if d.get("ledger"):
            recipe = _sync_recipe_from_ledger(
                product=product,
                pricing_mode=d.get("pricingMode", "1"),
                ledger=d["ledger"],
                actor=request.user,
            )
        else:
            recipe = PricingRecipe.objects.create(
                product=product,
                version=1,
                status=PricingRecipe.Status.DRAFT,
                pricing_mode=d.get("pricingMode", "1"),
            )

        dual_write_product_details(product, _detail_overrides_from_payload(d))
        record_audit(action="PRODUCT_CREATED", entity_type="ProductModel", entity_id=sku, actor=request.user)
        rates = get_current_rate_snapshot()
        product = _products_queryset().get(id=product.id)
        return envelope_response(serialize_ops_product(product, recipe, rates), request, status=201)


class OpsProductDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "catalog:read",
        "PATCH": "catalog:write",
        "DELETE": "catalog:delete",
    }

    def get(self, request: Request, parent_sku: str):
        rates = get_current_rate_snapshot()
        product = _products_queryset().filter(parent_sku=parent_sku).first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        recipe = product.published_recipes[0] if product.published_recipes else None
        return envelope_response(serialize_ops_product(product, recipe, rates), request)

    @transaction.atomic
    def patch(self, request: Request, parent_sku: str):
        product = ProductModel.objects.filter(parent_sku=parent_sku).first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        ctx = resolve_tenant_context(request)
        if str(request.data.get("catalogStatus") or "").upper() == ProductModel.CatalogStatus.ACTIVE:
            raise DomainError(
                "Ürünü yayına almak için /api/v1/ops/products/<sku>/publish endpoint'ini kullanın.",
                code="USE_PUBLISH_ENDPOINT",
                status_code=400,
            )
        if "stockQty" in request.data:
            raise DomainError(
                "Stok miktarını güncellemek için /api/v1/ops/products/<sku>/variants/<id>/stock endpoint'ini kullanın.",
                code="USE_INVENTORY_API",
                status_code=400,
            )
        serializer = OpsProductSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        _enforce_field_permissions(ctx, d)
        changed_audit: dict[str, dict] = {}
        if "fireRatePct" in d and d["fireRatePct"] != product.fire_rate_pct:
            changed_audit["fireRatePct"] = {"from": str(product.fire_rate_pct), "to": str(d["fireRatePct"])}
        if "catalogStatus" in d and d["catalogStatus"] != product.catalog_status:
            changed_audit["catalogStatus"] = {"from": product.catalog_status, "to": d["catalogStatus"]}
        if "salesChannels" in d:
            changed_audit["salesChannels"] = {"from": product.sales_channels or [], "to": _normalize_sales_channels(d["salesChannels"])}
        if "ledger" in d:
            changed_audit["ledger"] = {"from": "published_or_prev", "to": sorted(d["ledger"].keys())}

        if "ownerOrganizationId" in d:
            if d["ownerOrganizationId"] is None:
                product.owner_organization = None
            else:
                product.owner_organization = resolve_active_organization(d["ownerOrganizationId"])
        if "catalogStatus" in d:
            product.catalog_status = d["catalogStatus"]

        editable_map = {
            "title": "title",
            "barcode": "barcode",
            "visualType": "visual_type",
            "productType": "product_type",
            "category": "category",
            "subCategory": "sub_category",
            "collection": "collection",
            "styleTechnique": "style_technique",
            "occasion": "occasion",
            "ageGroup": "age_group",
            "metalName": "metal_name",
            "purityCode": "purity_code",
            "metalColor": "metal_color",
            "availableColors": "available_colors",
            "salesChannels": "sales_channels",
            "stoneType": "stone_type",
            "stoneMeasureUnit": "stone_measure_unit",
            "stoneClarity": "stone_clarity",
            "stoneColorGrade": "stone_color_grade",
            "stoneCutGrade": "stone_cut_grade",
            "stoneCutShape": "stone_cut_shape",
            "stoneOrigin": "stone_origin",
            "settingType": "setting_type",
            "certificateAgency": "certificate_agency",
            "certificateNumber": "certificate_number",
            "grossWeightGram": "gross_weight_gram",
            "fireRatePct": "fire_rate_pct",
            "stockStatus": "stock_status",
            "stockQty": "stock_qty",
            "leadTimeDays": "lead_time_days",
            "ownershipType": "ownership_type",
            "supplierName": "supplier_name",
            "warehouseLocation": "warehouse_location",
            "variantSize": "variant_size",
            "availableSizes": "available_sizes",
            "widthMm": "width_mm",
            "thicknessMm": "thickness_mm",
            "heightMm": "height_mm",
            "chainType": "chain_type",
            "claspType": "clasp_type",
            "isResizable": "is_resizable",
            "warrantyMonths": "warranty_months",
            "insuredShippingInfo": "insured_shipping_info",
            "returnPolicyText": "return_policy_text",
            "metaTitle": "meta_title",
            "description": "description",
        }
        for api_key, model_field in editable_map.items():
            if api_key in d:
                value = d[api_key]
                if api_key == "salesChannels":
                    value = _normalize_sales_channels(value)
                setattr(product, model_field, value)

        _apply_kind_fields(product, d)

        if product.stock_qty <= 0 and product.stock_status != ProductModel.StockStatus.MADE_TO_ORDER:
            product.stock_status = ProductModel.StockStatus.OUT_OF_STOCK

        if "seoSlug" in d and d["seoSlug"].strip():
            cleaned_slug = slugify(d["seoSlug"].strip())
            if cleaned_slug:
                if ProductModel.objects.filter(seo_slug=cleaned_slug).exclude(id=product.id).exists():
                    raise DomainError(f"SEO slug başka bir üründe kullanılıyor: {cleaned_slug}", code="DUPLICATE_SLUG", status_code=409)
                product.seo_slug = cleaned_slug

        if "mountSpec" in d and isinstance(d["mountSpec"], dict):
            ms = d["mountSpec"]
            if "structure" in ms:
                product.mount_structure = ms["structure"]
            if "allowedCaratMin" in ms:
                product.allowed_carat_min = _parse_decimal(
                    ms["allowedCaratMin"], field_name="mountSpec.allowedCaratMin", min_value=Decimal("0")
                )
            if "allowedCaratMax" in ms:
                product.allowed_carat_max = _parse_decimal(
                    ms["allowedCaratMax"], field_name="mountSpec.allowedCaratMax", min_value=Decimal("0")
                )
            if "headCode" in ms:
                product.head_code = str(ms["headCode"])
            if "bandCode" in ms:
                product.band_code = str(ms["bandCode"])
            if "headWeightGram" in ms:
                product.head_weight_gram = (
                    _parse_decimal(ms["headWeightGram"], field_name="mountSpec.headWeightGram", min_value=Decimal("0"))
                    if ms["headWeightGram"] not in (None, "")
                    else None
                )
            if "bandWeightGram" in ms:
                product.band_weight_gram = (
                    _parse_decimal(ms["bandWeightGram"], field_name="mountSpec.bandWeightGram", min_value=Decimal("0"))
                    if ms["bandWeightGram"] not in (None, "")
                    else None
                )
        product.save()

        _sync_product_media(
            product,
            gallery_images=d.get("galleryImages") if "galleryImages" in d else None,
            reels_video_url=d.get("reelsVideoUrl") if "reelsVideoUrl" in d else None,
            spin_360_url=d.get("spin360Url") if "spin360Url" in d else None,
            certificate_file_url=d.get("certificateFileUrl") if "certificateFileUrl" in d else None,
        )

        updated_center_carat: Decimal | None = None
        if "stoneLines" in d and isinstance(d["stoneLines"], list):
            product.stone_lines.all().delete()
            updated_center_carat = Decimal("0")
            for st in d["stoneLines"]:
                st_role = st.get("role", StoneLine.Role.MERKEZ)
                st_count = _parse_int(st.get("count", 1), field_name="stoneLines.count", default=1, min_value=1)
                st_carat = _parse_decimal(st.get("carat", 0), field_name="stoneLines.carat", default=Decimal("0"), min_value=Decimal("0"))
                StoneLine.objects.create(
                    product=product,
                    role=st_role,
                    stone_type=st.get("stoneType", product.stone_type),
                    measure_unit=st.get("measureUnit", product.stone_measure_unit),
                    count=st_count,
                    carat=st_carat,
                    clarity=st.get("clarity", ""),
                    color_grade=st.get("colorGrade", ""),
                    cut_shape=st.get("cutShape", ""),
                )
                if st_role == StoneLine.Role.MERKEZ:
                    updated_center_carat += st_carat * st_count
        elif "centerStoneCarat" in d or "sideStoneCarat" in d:
            if "centerStoneCarat" in d:
                updated_center_carat = d["centerStoneCarat"]
                center_line = product.stone_lines.filter(role=StoneLine.Role.MERKEZ).first()
                if center_line:
                    center_line.carat = d["centerStoneCarat"]
                    center_line.save(update_fields=["carat", "updated_at"])
                elif d["centerStoneCarat"] > 0:
                    StoneLine.objects.create(
                        product=product, role=StoneLine.Role.MERKEZ, stone_type=product.stone_type, count=1, carat=d["centerStoneCarat"]
                    )
            if "sideStoneCarat" in d:
                side_line = product.stone_lines.exclude(role=StoneLine.Role.MERKEZ).first()
                if side_line:
                    side_line.carat = d["sideStoneCarat"]
                    side_line.save(update_fields=["carat", "updated_at"])
                elif d["sideStoneCarat"] > 0:
                    StoneLine.objects.create(
                        product=product, role=StoneLine.Role.YAN, stone_type=product.stone_type, count=1, carat=d["sideStoneCarat"]
                    )

        # Sync default variant physical specs if edited at model level
        default_variant = product.variants.filter(is_default=True).first()
        if default_variant is not None:
            v_update_fields: list[str] = []
            if "grossWeightGram" in d:
                default_variant.gross_weight_gram = d["grossWeightGram"]
                v_update_fields.append("gross_weight_gram")
            if "purityCode" in d:
                default_variant.purity_code = d["purityCode"]
                v_update_fields.append("purity_code")
            if "metalColor" in d:
                default_variant.metal_color = d["metalColor"]
                v_update_fields.append("metal_color")
            if v_update_fields:
                v_update_fields.append("updated_at")
                default_variant.save(update_fields=v_update_fields)
        if updated_center_carat is not None:
            sync_default_variant_center_carat(product)

        if "ledger" in d or "pricingMode" in d:
            recipe = _sync_recipe_from_ledger(
                product=product,
                pricing_mode=d.get("pricingMode"),
                ledger=d.get("ledger"),
                actor=request.user,
            )
        else:
            recipe = product.pricing_recipes.filter(status=PricingRecipe.Status.PUBLISHED).first()

        dual_write_product_details(product, _detail_overrides_from_payload(d))
        record_audit(
            action="PRODUCT_UPDATED",
            entity_type="ProductModel",
            entity_id=parent_sku,
            actor=request.user,
            metadata={"changed": changed_audit} if changed_audit else {},
        )
        rates = get_current_rate_snapshot()
        product = _products_queryset().get(id=product.id)
        return envelope_response(serialize_ops_product(product, recipe, rates), request)

    @transaction.atomic
    def delete(self, request: Request, parent_sku: str):
        product = ProductModel.objects.filter(parent_sku=parent_sku).first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        from apps.commerce.models import B2bDraftLine, B2bOrderLine, B2cCartItem, B2cOrderItem

        has_refs = (
            B2cOrderItem.objects.filter(parent_sku=parent_sku).exists()
            or B2bOrderLine.objects.filter(parent_sku=parent_sku).exists()
            or B2cCartItem.objects.filter(parent_sku=parent_sku).exists()
            or B2bDraftLine.objects.filter(parent_sku=parent_sku).exists()
        )
        if product.catalog_status == ProductModel.CatalogStatus.DRAFT and not has_refs:
            product.delete()
            record_audit(action="PRODUCT_DELETED", entity_type="ProductModel", entity_id=parent_sku, actor=request.user)
            return envelope_response({"parentSku": parent_sku, "deleted": True, "archived": False}, request)

        prev_status = product.catalog_status
        product.catalog_status = ProductModel.CatalogStatus.ARCHIVED
        product.save(update_fields=["catalog_status", "updated_at"])
        record_audit(
            action="PRODUCT_ARCHIVED",
            entity_type="ProductModel",
            entity_id=parent_sku,
            actor=request.user,
            metadata={"changed": {"catalogStatus": {"from": prev_status, "to": "ARCHIVED"}}},
        )
        return envelope_response({"parentSku": parent_sku, "deleted": False, "archived": True}, request)


class OpsProductPublishView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:publish"

    @transaction.atomic
    def post(self, request: Request, parent_sku: str):
        product = ProductModel.objects.filter(parent_sku=parent_sku).first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        missing = validate_publishable(product)
        if missing:
            return envelope_response(
                {"code": "NOT_PUBLISHABLE", "message": "Ürün yayın koşulları sağlanmadı.", "missing": missing},
                request,
                status=422,
            )
        prev = product.catalog_status
        product.catalog_status = ProductModel.CatalogStatus.ACTIVE
        product.save(update_fields=["catalog_status", "updated_at"])
        record_audit(
            action="PRODUCT_PUBLISHED",
            entity_type="ProductModel",
            entity_id=parent_sku,
            actor=request.user,
            metadata={"changed": {"catalogStatus": {"from": prev, "to": "ACTIVE"}}},
        )
        return envelope_response({"parentSku": parent_sku, "catalogStatus": product.catalog_status}, request)


class OpsProductRecipePublishView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "pricing:edit"

    @transaction.atomic
    def post(self, request: Request, parent_sku: str):
        product = ProductModel.objects.filter(parent_sku=parent_sku).first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        draft = (
            PricingRecipe.objects.filter(product=product, status=PricingRecipe.Status.DRAFT)
            .order_by("-version")
            .first()
        )
        if draft is None:
            raise DomainError("Yayınlanacak DRAFT fiyat reçetesi bulunamadı.", code="DRAFT_RECIPE_NOT_FOUND", status_code=404)
        published, _ = publish_recipe(draft, actor=request.user)
        record_audit(
            action="PRODUCT_RECIPE_PUBLISHED",
            entity_type="PricingRecipe",
            entity_id=str(published.id),
            actor=request.user,
            metadata={"parentSku": parent_sku, "version": published.version},
        )
        return envelope_response(
            {"parentSku": parent_sku, "recipeId": str(published.id), "version": published.version, "status": published.status},
            request,
        )
