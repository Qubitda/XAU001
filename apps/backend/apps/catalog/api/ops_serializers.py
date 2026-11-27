"""Typed DRF input serializers for OPS catalog product endpoints."""
from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import ProductModel, StoneLine


def _validate_https_url(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) > 500 or not cleaned.startswith("https://"):
        raise serializers.ValidationError("URL yalnızca geçerli bir https:// adresi olabilir (en fazla 500 karakter).")
    return cleaned


class StoneLineInputSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=StoneLine.Role.choices, default=StoneLine.Role.MERKEZ, required=False)
    stoneType = serializers.CharField(max_length=60, required=False, allow_blank=True)
    measureUnit = serializers.CharField(max_length=16, required=False, default="ct")
    count = serializers.IntegerField(min_value=1, default=1, required=False)
    carat = serializers.DecimalField(
        max_digits=8,
        decimal_places=3,
        min_value=Decimal("0"),
        default=Decimal("0"),
        required=False,
    )
    clarity = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    colorGrade = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    cutShape = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")


class MountSpecSerializer(serializers.Serializer):
    structure = serializers.ChoiceField(choices=ProductModel.MountStructure.choices, required=False)
    allowedCaratMin = serializers.DecimalField(
        max_digits=8, decimal_places=3, min_value=Decimal("0"), required=False, allow_null=True
    )
    allowedCaratMax = serializers.DecimalField(
        max_digits=8, decimal_places=3, min_value=Decimal("0"), required=False, allow_null=True
    )
    headCode = serializers.CharField(max_length=60, required=False, allow_blank=True)
    bandCode = serializers.CharField(max_length=60, required=False, allow_blank=True)
    headWeightGram = serializers.DecimalField(
        max_digits=8, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True
    )
    bandWeightGram = serializers.DecimalField(
        max_digits=8, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True
    )


class OpsProductSerializer(serializers.Serializer):
    """Unified OPS product serializer for create (full) and update (partial=True)."""

    parentSku = serializers.CharField(max_length=64)
    erpCode = serializers.CharField(max_length=64, required=False, allow_blank=True, allow_null=True)
    ownerOrganizationId = serializers.UUIDField(required=False, allow_null=True)
    catalogStatus = serializers.ChoiceField(
        choices=ProductModel.CatalogStatus.choices,
        default=ProductModel.CatalogStatus.DRAFT,
        required=False,
    )
    barcode = serializers.CharField(max_length=64, required=False, allow_blank=True)
    visualType = serializers.CharField(max_length=64, required=False, default="solitaire_ring")
    productKind = serializers.ChoiceField(choices=ProductModel.ProductKind.choices, required=False)
    productType = serializers.CharField(max_length=80, required=False, allow_blank=True)
    title = serializers.CharField(max_length=255)
    category = serializers.CharField(max_length=80)
    subCategory = serializers.CharField(max_length=80, required=False, default="", allow_blank=True)
    collection = serializers.CharField(max_length=80, required=False, default="", allow_blank=True)
    styleTechnique = serializers.CharField(max_length=80, required=False, default="Modern")
    occasion = serializers.CharField(max_length=80, required=False, allow_blank=True)
    ageGroup = serializers.CharField(max_length=60, required=False, allow_blank=True)
    metalName = serializers.CharField(max_length=40, required=False, allow_blank=True)
    purityCode = serializers.CharField(max_length=16)
    metalColor = serializers.CharField(max_length=40)
    availableColors = serializers.ListField(child=serializers.CharField(max_length=40), required=False)
    salesChannels = serializers.ListField(
        child=serializers.ChoiceField(choices=["B2B", "B2B_API", "B2C_API"]),
        required=False,
    )
    stoneType = serializers.CharField(max_length=60, required=False, default="Pırlanta", allow_blank=True)
    stoneMeasureUnit = serializers.CharField(max_length=16, required=False, default="ct")
    stoneClarity = serializers.CharField(max_length=40, required=False, allow_blank=True)
    stoneColorGrade = serializers.CharField(max_length=40, required=False, allow_blank=True)
    stoneCutGrade = serializers.CharField(max_length=40, required=False, allow_blank=True)
    stoneCutShape = serializers.CharField(max_length=60, required=False, allow_blank=True)
    stoneOrigin = serializers.CharField(max_length=80, required=False, allow_blank=True)
    settingType = serializers.CharField(max_length=80, required=False, allow_blank=True)
    certificateAgency = serializers.CharField(max_length=40, required=False, allow_blank=True)
    certificateNumber = serializers.CharField(max_length=80, required=False, allow_blank=True)
    grossWeightGram = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0.01"))
    fireRatePct = serializers.DecimalField(
        max_digits=6, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100"), required=False, default=Decimal("0")
    )
    stockStatus = serializers.ChoiceField(
        choices=ProductModel.StockStatus.choices, required=False, default=ProductModel.StockStatus.IN_STOCK
    )
    stockQty = serializers.IntegerField(min_value=0, default=0, required=False)
    leadTimeDays = serializers.IntegerField(min_value=0, max_value=365, required=False, default=2)
    ownershipType = serializers.ChoiceField(
        choices=ProductModel.OwnershipType.choices, required=False, default=ProductModel.OwnershipType.OWNED
    )
    supplierName = serializers.CharField(max_length=120, required=False, allow_blank=True)
    warehouseLocation = serializers.CharField(max_length=120, required=False, allow_blank=True)
    variantSize = serializers.IntegerField(min_value=0, max_value=60, required=False, default=0)
    availableSizes = serializers.ListField(child=serializers.IntegerField(min_value=0, max_value=60), required=False)
    widthMm = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"), required=False)
    thicknessMm = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"), required=False)
    heightMm = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"), required=False)
    chainType = serializers.CharField(max_length=60, required=False, allow_blank=True)
    claspType = serializers.CharField(max_length=60, required=False, allow_blank=True)
    isResizable = serializers.BooleanField(required=False, default=True)
    warrantyMonths = serializers.IntegerField(min_value=0, max_value=120, required=False, default=24)
    insuredShippingInfo = serializers.CharField(max_length=200, required=False, allow_blank=True)
    returnPolicyText = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, default="", allow_blank=True)
    seoSlug = serializers.CharField(max_length=255, required=False, allow_blank=True)
    metaTitle = serializers.CharField(max_length=255, required=False, allow_blank=True)
    centerStoneCarat = serializers.DecimalField(
        max_digits=8, decimal_places=3, min_value=Decimal("0"), required=False, default=Decimal("0")
    )
    sideStoneCarat = serializers.DecimalField(
        max_digits=8, decimal_places=3, min_value=Decimal("0"), required=False, default=Decimal("0")
    )
    pricingMode = serializers.CharField(max_length=16, required=False, default="1")
    mountSpec = MountSpecSerializer(required=False)
    stoneLines = StoneLineInputSerializer(many=True, required=False)
    galleryImages = serializers.ListField(
        child=serializers.URLField(max_length=500),
        max_length=20,
        required=False,
    )
    reelsVideoUrl = serializers.URLField(max_length=500, required=False, allow_blank=True)
    spin360Url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    certificateFileUrl = serializers.URLField(max_length=500, required=False, allow_blank=True)
    ledger = serializers.DictField(required=False)
    finishedDetail = serializers.DictField(required=False)
    mountingDetail = serializers.DictField(required=False)
    looseStoneDetail = serializers.DictField(required=False)

    def validate_reelsVideoUrl(self, value: str) -> str:
        return _validate_https_url(value)

    def validate_spin360Url(self, value: str) -> str:
        return _validate_https_url(value)

    def validate_certificateFileUrl(self, value: str) -> str:
        return _validate_https_url(value)

    def validate_galleryImages(self, value: list[str]) -> list[str]:
        return [_validate_https_url(item) for item in value if (item or "").strip()]
