"""OPS product endpoints."""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils.text import slugify
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
from apps.catalog.models import ProductModel, ProductVariant, StoneLine
from apps.catalog.product_details import dual_write_product_details
from apps.catalog.product_kinds import kind_to_product_type_label, normalize_product_kind
from apps.catalog.services import sync_default_variant_center_carat, validate_publishable
from apps.common.responses import apply_safe_ordering, envelope_response, paginated_envelope_response
from apps.inventory.services import get_or_create_default_warehouse, set_variant_warehouse_stock
from apps.market.services import get_current_rate_snapshot
from apps.organizations.selectors import resolve_active_organization, resolve_tenant_context
from apps.pricing.models import PricingRecipe
from apps.pricing.services import publish_recipe
from config.exceptions import DomainError
from ..common import (
    _apply_kind_fields,
    _detail_overrides_from_payload,
    _normalize_sales_channels,
    _parse_decimal,
    _parse_int,
    _sync_product_media,
)
from ..ops_serializers import OpsProductSerializer
from ..recipe_sync import _sync_recipe_from_ledger
from ..serializers import _apply_filters, _products_queryset, serialize_ops_product

from .permissions import _enforce_field_permissions

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
        product = ProductModel.objects.select_for_update().filter(parent_sku=parent_sku).first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        ctx = resolve_tenant_context(request)
        if (
            str(request.data.get("catalogStatus") or "").upper() == ProductModel.CatalogStatus.ACTIVE
            and product.catalog_status != ProductModel.CatalogStatus.ACTIVE
        ):
            raise DomainError(
                "Ürün düzenleme kaydıyla doğrudan yayına alınamaz; lütfen Yayınla butonunu kullanın.",
                code="USE_PUBLISH_ENDPOINT",
                status_code=400,
            )
        if "stockQty" in request.data and request.data.get("stockQty") != product.stock_qty:
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
            "lifetimeMaintenance": "lifetime_maintenance",
            "insuredShippingInfo": "insured_shipping_info",
            "returnPolicyText": "return_policy_text",
            "metaTitle": "meta_title",
            "metaDescription": "meta_description",
            "marketplaceCategory": "marketplace_category",
            "sizeGuideUrl": "size_guide_url",
            "ogImage": "og_image",
            "canonicalUrl": "canonical_url",
            "robots": "robots",
            "keywords": "keywords",
            "description": "description",
            "b2bSharePermission": "b2b_share_permission",
            "dynamicDealerWatermark": "dynamic_dealer_watermark",
            "socialShareCaption": "social_share_caption",
        }
        nullable_text_keys = {
            "lifetimeMaintenance",
            "insuredShippingInfo",
            "returnPolicyText",
            "metaTitle",
            "metaDescription",
            "marketplaceCategory",
            "sizeGuideUrl",
            "ogImage",
            "canonicalUrl",
            "robots",
            "keywords",
            "description",
        }
        for api_key, model_field in editable_map.items():
            if api_key in d:
                value = d[api_key]
                if api_key == "salesChannels":
                    value = _normalize_sales_channels(value)
                elif api_key in nullable_text_keys and value is None:
                    value = ""
                setattr(product, model_field, value)

        _apply_kind_fields(product, d)

        if product.stock_qty <= 0 and product.stock_status != ProductModel.StockStatus.MADE_TO_ORDER:
            product.stock_status = ProductModel.StockStatus.OUT_OF_STOCK

        if "seoSlug" in d and (d["seoSlug"] or "").strip():
            cleaned_slug = slugify((d["seoSlug"] or "").strip())
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
            media_items=d.get("mediaItems") if "mediaItems" in d else None,
            reels_video_url=d.get("reelsVideoUrl") if "reelsVideoUrl" in d else None,
            spin_360_url=d.get("spin360Url") if "spin360Url" in d else None,
            catalog_clean_image_url=d.get("catalogCleanImageUrl") if "catalogCleanImageUrl" in d else None,
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


