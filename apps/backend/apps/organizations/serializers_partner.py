from decimal import Decimal

from rest_framework import serializers

from .models import Organization, OrganizationAddress, OrganizationBankAccount, OrganizationDocument


PARTNER_ROLE_CHOICES = ("BUYER", "SUPPLIER", "PLATFORM")


class OpsOrganizationCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=200)
    legalName = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")
    orgType = serializers.ChoiceField(choices=Organization.OrgType.values, default=Organization.OrgType.DEALER)
    partnerRoles = serializers.ListField(
        child=serializers.ChoiceField(choices=PARTNER_ROLE_CHOICES),
        required=False,
        default=list,
    )
    approvalStatus = serializers.ChoiceField(
        choices=Organization.ApprovalStatus.values,
        required=False,
        default=Organization.ApprovalStatus.APPROVED,
    )
    taxOfficeAndNo = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    taxOffice = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    taxNumber = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    mersisNo = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    tradeRegistryNo = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    companyType = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    foundedOn = serializers.DateField(required=False, allow_null=True)
    contactName = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    fax = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    website = serializers.URLField(required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    defaultConsignmentDays = serializers.IntegerField(min_value=0, max_value=365, default=45)
    paymentTermDays = serializers.IntegerField(min_value=0, max_value=365, default=30)
    riskLevel = serializers.ChoiceField(
        choices=Organization.RiskLevel.values,
        required=False,
        default=Organization.RiskLevel.LOW,
    )
    riskNote = serializers.CharField(required=False, allow_blank=True, default="")
    commercialNotes = serializers.CharField(required=False, allow_blank=True, default="")
    supplierCode = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    supplierLeadTimeDays = serializers.IntegerField(min_value=0, max_value=365, required=False, allow_null=True)
    supplierNotes = serializers.CharField(required=False, allow_blank=True, default="")
    creditLimitUsd = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"), default=Decimal("0.00")
    )
    hasLimitGram = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=Decimal("0"), default=Decimal("0.0000")
    )
    isActive = serializers.BooleanField(default=True)


class OpsOrganizationUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    legalName = serializers.CharField(max_length=240, required=False, allow_blank=True)
    orgType = serializers.ChoiceField(choices=Organization.OrgType.values, required=False)
    partnerRoles = serializers.ListField(
        child=serializers.ChoiceField(choices=PARTNER_ROLE_CHOICES),
        required=False,
    )
    approvalStatus = serializers.ChoiceField(choices=Organization.ApprovalStatus.values, required=False)
    taxOfficeAndNo = serializers.CharField(max_length=120, required=False, allow_blank=True)
    taxOffice = serializers.CharField(max_length=120, required=False, allow_blank=True)
    taxNumber = serializers.CharField(max_length=32, required=False, allow_blank=True)
    mersisNo = serializers.CharField(max_length=32, required=False, allow_blank=True)
    tradeRegistryNo = serializers.CharField(max_length=64, required=False, allow_blank=True)
    companyType = serializers.CharField(max_length=64, required=False, allow_blank=True)
    foundedOn = serializers.DateField(required=False, allow_null=True)
    contactName = serializers.CharField(max_length=120, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    fax = serializers.CharField(max_length=32, required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    defaultConsignmentDays = serializers.IntegerField(min_value=0, max_value=365, required=False)
    paymentTermDays = serializers.IntegerField(min_value=0, max_value=365, required=False)
    riskLevel = serializers.ChoiceField(choices=Organization.RiskLevel.values, required=False)
    riskNote = serializers.CharField(required=False, allow_blank=True)
    creditReviewNote = serializers.CharField(required=False, allow_blank=True)
    commercialNotes = serializers.CharField(required=False, allow_blank=True)
    supplierCode = serializers.CharField(max_length=64, required=False, allow_blank=True)
    supplierLeadTimeDays = serializers.IntegerField(min_value=0, max_value=365, required=False, allow_null=True)
    supplierNotes = serializers.CharField(required=False, allow_blank=True)
    creditLimitUsd = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False
    )
    hasLimitGram = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=Decimal("0"), required=False
    )
    isActive = serializers.BooleanField(required=False)


class AddressWriteSerializer(serializers.Serializer):
    addressType = serializers.ChoiceField(
        choices=OrganizationAddress.AddressType.values, default=OrganizationAddress.AddressType.OTHER
    )
    title = serializers.CharField(max_length=120)
    country = serializers.CharField(max_length=64, required=False, allow_blank=True, default="Türkiye")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    district = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    neighborhood = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    postalCode = serializers.CharField(max_length=16, required=False, allow_blank=True, default="")
    line = serializers.CharField()
    contactName = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    isDefault = serializers.BooleanField(required=False, default=False)
    isActive = serializers.BooleanField(required=False, default=True)


class AddressPatchSerializer(AddressWriteSerializer):
    title = serializers.CharField(max_length=120, required=False)
    line = serializers.CharField(required=False)
    addressType = serializers.ChoiceField(choices=OrganizationAddress.AddressType.values, required=False)
    isDefault = serializers.BooleanField(required=False)
    isActive = serializers.BooleanField(required=False)


class BankAccountWriteSerializer(serializers.Serializer):
    bankName = serializers.CharField(max_length=120)
    iban = serializers.CharField(max_length=34)
    currency = serializers.CharField(max_length=8, required=False, default="TRY")
    accountHolder = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    isDefault = serializers.BooleanField(required=False, default=False)
    isActive = serializers.BooleanField(required=False, default=True)


class BankAccountPatchSerializer(BankAccountWriteSerializer):
    bankName = serializers.CharField(max_length=120, required=False)
    iban = serializers.CharField(max_length=34, required=False)


class DocumentWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    docType = serializers.ChoiceField(
        choices=OrganizationDocument.DocType.values, default=OrganizationDocument.DocType.OTHER
    )
    validUntil = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")
