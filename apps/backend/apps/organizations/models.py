from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.common.models import TimestampedModel


class Organization(TimestampedModel):
    class OrgType(models.TextChoices):
        PLATFORM_OWNER = "PLATFORM_OWNER", "Platform Sahibi (Merkez)"
        DEALER = "DEALER", "B2B Bayi Firma"
        SUPPLIER = "SUPPLIER", "Tedarikçi Firma"

    class ApprovalStatus(models.TextChoices):
        DRAFT = "DRAFT", "Taslak"
        PENDING = "PENDING", "Onay bekliyor"
        APPROVED = "APPROVED", "Onaylandı"
        REJECTED = "REJECTED", "Reddedildi"
        SUSPENDED = "SUSPENDED", "Askıya alındı"
        INACTIVE = "INACTIVE", "Pasif"

    class RiskLevel(models.TextChoices):
        LOW = "LOW", "Düşük"
        MEDIUM = "MEDIUM", "Orta"
        HIGH = "HIGH", "Yüksek"
        BLOCKED = "BLOCKED", "Blokeli"

    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=240, blank=True, default="")
    org_type = models.CharField(max_length=24, choices=OrgType.choices, default=OrgType.DEALER)
    # Commercial roles: BUYER / SUPPLIER / PLATFORM — multi-select via JSON list.
    partner_roles = models.JSONField(default=list, blank=True)
    approval_status = models.CharField(
        max_length=16,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.APPROVED,
        db_index=True,
    )
    tax_office_and_no = models.CharField(max_length=120, blank=True, default="")
    tax_office = models.CharField(max_length=120, blank=True, default="")
    tax_number = models.CharField(max_length=32, blank=True, default="")
    mersis_no = models.CharField(max_length=32, blank=True, default="")
    trade_registry_no = models.CharField(max_length=64, blank=True, default="")
    company_type = models.CharField(max_length=64, blank=True, default="")
    founded_on = models.DateField(null=True, blank=True)
    contact_name = models.CharField(max_length=120, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    fax = models.CharField(max_length=32, blank=True, default="")
    website = models.URLField(blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    logo = models.ImageField(upload_to="org_logos/", blank=True, null=True)
    default_consignment_days = models.PositiveSmallIntegerField(default=45)
    payment_term_days = models.PositiveSmallIntegerField(default=30)
    risk_level = models.CharField(
        max_length=16,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
        db_index=True,
    )
    risk_note = models.TextField(blank=True, default="")
    credit_review_note = models.TextField(blank=True, default="")
    credit_reviewed_at = models.DateTimeField(null=True, blank=True)
    credit_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    commercial_notes = models.TextField(blank=True, default="")
    supplier_code = models.CharField(max_length=64, blank=True, default="")
    supplier_lead_time_days = models.PositiveSmallIntegerField(null=True, blank=True)
    supplier_notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    # Financial limit snapshot (SSOT updates via finance.services + select_for_update)
    credit_limit_usd = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    used_credit_usd = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    has_limit_gram = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0.0000"))
    used_has_gram = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0.0000"))

    class Meta:
        db_table = "organizations_organization"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"

    def save(self, *args, **kwargs):
        roles = self.partner_roles if isinstance(self.partner_roles, list) else []
        normalized = []
        for role in roles:
            code = str(role).strip().upper()
            if code in ("BUYER", "SUPPLIER", "PLATFORM") and code not in normalized:
                normalized.append(code)
        if not normalized:
            if self.org_type == self.OrgType.PLATFORM_OWNER:
                normalized = ["PLATFORM", "BUYER"]
            elif self.org_type == self.OrgType.SUPPLIER:
                normalized = ["SUPPLIER"]
            else:
                normalized = ["BUYER"]
        self.partner_roles = normalized
        super().save(*args, **kwargs)

    @property
    def remaining_credit_usd(self) -> Decimal:
        return max(Decimal("0.00"), self.credit_limit_usd - self.used_credit_usd)

    @property
    def remaining_has_gram(self) -> Decimal:
        return max(Decimal("0.0000"), self.has_limit_gram - self.used_has_gram)

    @property
    def is_buyer(self) -> bool:
        return "BUYER" in (self.partner_roles or [])

    @property
    def is_supplier(self) -> bool:
        return "SUPPLIER" in (self.partner_roles or [])


class Branch(TimestampedModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="branches",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    city = models.CharField(max_length=100)
    address = models.TextField(blank=True, default="")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "organizations_branch"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="uniq_branch_code_per_organization",
            )
        ]
        ordering = ["-is_default", "name"]

    def __str__(self) -> str:
        return f"{self.organization.code}/{self.code} · {self.name}"


class OrganizationMembership(TimestampedModel):
    class RoleKey(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Süper Admin"
        ORG_ADMIN = "ORG_ADMIN", "Firma Yöneticisi"
        OPS = "OPS", "Operasyon / Fiyatlama"
        B2B_BUYER = "B2B_BUYER", "B2B Satın Alma Yetkilisi"
        B2C_CUSTOMER = "B2C_CUSTOMER", "Perakende Müşteri"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
        null=True,
        blank=True,
    )
    role_key = models.CharField(max_length=24, choices=RoleKey.choices)
    job_title = models.CharField(max_length=120, blank=True, default="")
    branches = models.ManyToManyField(Branch, blank=True, related_name="memberships")
    default_branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    custom_permissions = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "organizations_membership"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization", "role_key"],
                name="uniq_user_org_role_membership",
            )
        ]

    def __str__(self) -> str:
        org_label = self.organization.code if self.organization_id else "B2C"
        return f"{self.user.email} · {org_label} ({self.role_key})"

    @property
    def audience(self) -> str:
        if self.role_key in (self.RoleKey.SUPER_ADMIN, self.RoleKey.OPS):
            return "erp"
        if self.role_key in (self.RoleKey.ORG_ADMIN, self.RoleKey.B2B_BUYER):
            return "b2b"
        return "b2c"


class OrganizationAddress(TimestampedModel):
    class AddressType(models.TextChoices):
        HQ = "HQ", "Merkez"
        BILLING = "BILLING", "Fatura"
        SHIPPING = "SHIPPING", "Teslimat"
        BRANCH = "BRANCH", "Şube"
        WAREHOUSE = "WAREHOUSE", "Depo"
        OTHER = "OTHER", "Diğer"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="addresses"
    )
    address_type = models.CharField(
        max_length=16, choices=AddressType.choices, default=AddressType.OTHER
    )
    title = models.CharField(max_length=120)
    country = models.CharField(max_length=64, blank=True, default="Türkiye")
    city = models.CharField(max_length=100, blank=True, default="")
    district = models.CharField(max_length=100, blank=True, default="")
    neighborhood = models.CharField(max_length=120, blank=True, default="")
    postal_code = models.CharField(max_length=16, blank=True, default="")
    line = models.TextField()
    contact_name = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "organizations_address"
        ordering = ["-is_default", "address_type", "title"]

    def __str__(self) -> str:
        return f"{self.organization.code} · {self.title}"


class OrganizationBankAccount(TimestampedModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="bank_accounts"
    )
    bank_name = models.CharField(max_length=120)
    iban = models.CharField(max_length=34)
    currency = models.CharField(max_length=8, default="TRY")
    account_holder = models.CharField(max_length=160, blank=True, default="")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "organizations_bank_account"
        ordering = ["-is_default", "bank_name"]

    def __str__(self) -> str:
        return f"{self.organization.code} · {self.bank_name}"


class OrganizationDocument(TimestampedModel):
    class DocType(models.TextChoices):
        TAX_PLATE = "TAX_PLATE", "Vergi levhası"
        TRADE_REGISTRY = "TRADE_REGISTRY", "Ticaret sicil"
        SIGNATURE_CIRCULAR = "SIGNATURE_CIRCULAR", "İmza sirküleri"
        ACTIVITY_CERT = "ACTIVITY_CERT", "Faaliyet belgesi"
        BANK = "BANK", "Banka belgesi"
        SUPPLIER_CERT = "SUPPLIER_CERT", "Tedarikçi sertifikası"
        CONTRACT = "CONTRACT", "Sözleşme"
        OTHER = "OTHER", "Diğer"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="documents"
    )
    name = models.CharField(max_length=200)
    doc_type = models.CharField(max_length=32, choices=DocType.choices, default=DocType.OTHER)
    file = models.FileField(upload_to="org_documents/")
    valid_until = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=240, blank=True, default="")

    class Meta:
        db_table = "organizations_document"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.organization.code} · {self.name}"


class SiteContactSettings(TimestampedModel):
    """Singleton public contact profile shown on storefront (footer / iletişim)."""

    singleton_key = models.CharField(max_length=32, unique=True, default="platform")
    company_name = models.CharField(max_length=200, blank=True, default="TARA DIAMOND")
    tagline = models.CharField(
        max_length=320,
        blank=True,
        default="Zamansız mücevher zarafetiyle, her anınızda yanınızdayız.",
    )
    address_line = models.CharField(
        max_length=320, blank=True, default="Nuruosmaniye Cad. No:54 Fatih / İstanbul"
    )
    phone = models.CharField(max_length=64, blank=True, default="+90 (212) 519 40 00")
    email = models.EmailField(blank=True, default="destek@taradiamond.com.tr")
    working_hours = models.CharField(max_length=120, blank=True, default="Pzt – Cmt · 09:30 – 19:00")
    whatsapp = models.CharField(max_length=64, blank=True, default="")
    instagram_url = models.URLField(blank=True, default="https://instagram.com")
    youtube_url = models.URLField(blank=True, default="https://youtube.com")
    tiktok_url = models.URLField(blank=True, default="")
    pinterest_url = models.URLField(blank=True, default="")
    map_url = models.URLField(blank=True, default="")

    class Meta:
        db_table = "organizations_site_contact_settings"
        verbose_name = "Site iletişim ayarı"
        verbose_name_plural = "Site iletişim ayarları"

    def __str__(self) -> str:
        return f"SiteContact · {self.company_name or self.singleton_key}"
