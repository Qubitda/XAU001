"""Typed DRF serializers for Product pricing ledger and channel rules."""
from decimal import Decimal

from rest_framework import serializers

SUPPORTED_CURRENCIES = ("TRY", "USD", "EUR", "GBP", "XAU")
SUPPORTED_RULE_UNITS = ("%", "TRY", "USD", "EUR")


class _RuleComponentSerializer(serializers.Serializer):
    unit = serializers.ChoiceField(choices=SUPPORTED_RULE_UNITS, required=False, default="%")
    value = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=Decimal("0"), required=False, default=Decimal("0")
    )

    def validate(self, attrs):
        if attrs.get("unit", "%") == "%" and attrs.get("value", Decimal("0")) > Decimal("1000"):
            raise serializers.ValidationError("Yüzde değeri 1000'den büyük olamaz.")
        return attrs


class _DiscountComponentSerializer(serializers.Serializer):
    unit = serializers.ChoiceField(choices=SUPPORTED_RULE_UNITS, required=False, default="%")
    value = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=Decimal("0"), required=False, default=Decimal("0")
    )

    def validate(self, attrs):
        if attrs.get("unit", "%") == "%" and attrs.get("value", Decimal("0")) > Decimal("100"):
            raise serializers.ValidationError("İndirim yüzdesi 0 ile 100 arasında olmalıdır.")
        return attrs


class ChannelRuleInputSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=("B2B", "B2B_API", "B2C_API", "B2C"))
    profit = _RuleComponentSerializer(required=False)
    discount = _DiscountComponentSerializer(required=False)
    platformFee = _RuleComponentSerializer(required=False)
    servisBedeli = _RuleComponentSerializer(required=False)


class LedgerSerializer(serializers.Serializer):
    lcCurrency = serializers.ChoiceField(choices=SUPPORTED_CURRENCIES, required=False)

    metalCurrency = serializers.ChoiceField(choices=SUPPORTED_CURRENCIES, required=False)
    metalFcManual = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True
    )
    metalRateOverride = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True
    )

    laborCurrency = serializers.ChoiceField(choices=SUPPORTED_CURRENCIES, required=False)
    laborFcPrice = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True
    )
    laborRateOverride = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True
    )

    stoneCurrency = serializers.ChoiceField(choices=SUPPORTED_CURRENCIES, required=False)
    stoneFcPrice = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True
    )
    stoneRateOverride = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True
    )

    mountingCurrency = serializers.ChoiceField(choices=SUPPORTED_CURRENCIES, required=False)
    mountingFcPrice = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True
    )
    mountingRateOverride = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True
    )

    otherCostCurrency = serializers.ChoiceField(choices=SUPPORTED_CURRENCIES, required=False)
    otherCostFcPrice = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True
    )
    otherCostRateOverride = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True
    )

    supplierCurrency = serializers.ChoiceField(choices=SUPPORTED_CURRENCIES, required=False)
    supplierFcPrice = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True
    )
    supplierRateOverride = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True
    )

    channelRules = serializers.ListField(child=ChannelRuleInputSerializer(), required=False)
