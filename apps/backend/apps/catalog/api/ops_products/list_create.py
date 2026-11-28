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

from .permissions import FIELD_PERMISSIONS, _enforce_field_permissions

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
        if str(request.data.get("catalogStatus") or "").upper() == ProductModel.CatalogStatus.ACTIVE:
            raise DomainError(
                "Yeni ürün doğrudan ACTIVE olarak oluşturulamaz. Önce taslak oluşturup /api/v1/ops/products/<sku>/publish endpoint'ini kullanın.",
                code="USE_PUBLISH_ENDPOINT",
                status_code=400,
            )
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
                catalog_status=(
                    ProductModel.CatalogStatus.ARCHIVED
                    if str(d.get("catalogStatus") or "").upper() == ProductModel.CatalogStatus.ARCHIVED
                    else ProductModel.CatalogStatus.DRAFT
                ),
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
                lifetime_maintenance=d.get("lifetimeMaintenance") or "",
                insured_shipping_info=d.get("insuredShippingInfo") or "Tam sigortalı Brinks / Loomis özel kurye",
                return_policy_text=d.get("returnPolicyText") or "Standart stok ürünlerinde 14 gün içinde koşulsuz iade; kişiye özel ölçü ve lazer yazı ürünlerinde iade istisnası uygulanır.",
                description=d.get("description") or "",
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
                meta_description=d.get("metaDescription") or "",
                marketplace_category=d.get("marketplaceCategory") or "",
                size_guide_url=d.get("sizeGuideUrl") or "",
                og_image=d.get("ogImage") or "",
                canonical_url=d.get("canonicalUrl") or "",
                robots=d.get("robots") or "index,follow",
                keywords=d.get("keywords") or "",
                b2b_share_permission=d.get("b2bSharePermission") or "ALLOWED",
                dynamic_dealer_watermark=bool(d.get("dynamicDealerWatermark", True)),
                social_share_caption=d.get("socialShareCaption") or "",
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
            media_items=d.get("mediaItems"),
            reels_video_url=d.get("reelsVideoUrl"),
            spin_360_url=d.get("spin360Url"),
            catalog_clean_image_url=d.get("catalogCleanImageUrl"),
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


