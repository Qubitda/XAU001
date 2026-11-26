from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.catalog.models import ProductModel, ProductVariant
from apps.common.models import TimestampedModel
from apps.customers.models import Customer
from apps.market.models import RateSnapshot
from apps.organizations.models import Branch, Organization
from apps.pricing.models import PriceLock, PriceQuote


class CustomBundle(TimestampedModel):
    """DYO mounting + loose stone package header (cart/order lines reference this)."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        IN_CART = "IN_CART", "Sepette"
        CHECKED_OUT = "CHECKED_OUT", "Siparişe döndü"
        EXPIRED = "EXPIRED", "Süresi doldu"
        CANCELLED = "CANCELLED", "İptal"

    class Audience(models.TextChoices):
        B2C = "B2C", "B2C"
        B2B = "B2B", "B2B"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dyo_bundles"
    )
    audience = models.CharField(max_length=8, choices=Audience.choices, default=Audience.B2C)
    mounting_product = models.ForeignKey(
        ProductModel, on_delete=models.PROTECT, related_name="dyo_as_mounting"
    )
    stone_product = models.ForeignKey(
        ProductModel, on_delete=models.PROTECT, related_name="dyo_as_stone"
    )
    mounting_variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    stone_variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    setting_labor_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    price_quote = models.ForeignKey(
        PriceQuote, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "commerce_custom_bundle"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Bundle {self.id} · {self.mounting_product.parent_sku}+{self.stone_product.parent_sku}"


class StoneSoftLock(TimestampedModel):
    """Timed exclusive soft-lock on a unique loose stone (before hard warehouse reserve)."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Aktif"
        RELEASED = "RELEASED", "Bırakıldı"
        CONSUMED = "CONSUMED", "Siparişte kullanıldı"

    stone_product = models.ForeignKey(
        ProductModel, on_delete=models.CASCADE, related_name="soft_locks"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stone_soft_locks"
    )
    bundle = models.ForeignKey(
        CustomBundle, on_delete=models.CASCADE, related_name="stone_locks", null=True, blank=True
    )
    expires_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "commerce_stone_soft_lock"
        indexes = [
            models.Index(fields=["status", "expires_at"], name="idx_stone_lock_active_exp"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["stone_product"],
                condition=models.Q(status="ACTIVE"),
                name="uniq_active_stone_soft_lock",
            ),
        ]

    def __str__(self) -> str:
        return f"Lock {self.stone_product.parent_sku} · {self.status}"


class BundleRole(models.TextChoices):
    MOUNTING = "MOUNTING", "Montür"
    STONE = "STONE", "Serbest Taş"


class B2cCart(TimestampedModel):
    """Cart header for B2C — lines live on B2cCartItem; events on CartEvent."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Aktif"
        ABANDONED = "ABANDONED", "Terk edilmiş"
        CONVERTED = "CONVERTED", "Siparişe dönüştü"
        EXPIRED = "EXPIRED", "Süresi doldu"

    class CheckoutState(models.TextChoices):
        NONE = "NONE", "Yok"
        STARTED = "STARTED", "Checkout başladı"
        COMPLETED = "COMPLETED", "Tamamlandı"

    external_id = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="b2c_carts",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="b2c_carts",
    )
    guest_email = models.EmailField(blank=True, default="", db_index=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    checkout_state = models.CharField(
        max_length=16, choices=CheckoutState.choices, default=CheckoutState.NONE
    )
    currency = models.CharField(max_length=8, default="TRY")
    subtotal_try = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    discount_try = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    tax_try = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_try = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    line_count = models.PositiveIntegerField(default=0)
    last_activity_at = models.DateTimeField(db_index=True)
    converted_order = models.ForeignKey(
        "commerce.B2cOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_carts",
    )
    recovery_session = models.ForeignKey(
        "commerce.CartRecoverySession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="b2c_carts",
    )

    class Meta:
        db_table = "commerce_b2c_cart"
        ordering = ["-last_activity_at"]
        indexes = [
            models.Index(fields=["status", "-last_activity_at"], name="b2c_cart_status_act_idx"),
            models.Index(fields=["user", "status"], name="b2c_cart_user_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="ACTIVE", user__isnull=False),
                name="uniq_active_b2c_cart_user",
            ),
        ]

    def __str__(self) -> str:
        who = self.user_id or self.guest_email or self.external_id or self.id
        return f"Cart {who} · {self.status}"


class CartEvent(TimestampedModel):
    class EventType(models.TextChoices):
        CART_CREATED = "cart.created", "Cart created"
        PRODUCT_ADDED = "product.added", "Product added"
        PRODUCT_REMOVED = "product.removed", "Product removed"
        CART_UPDATED = "cart.updated", "Cart updated"
        CHECKOUT_STARTED = "checkout.started", "Checkout started"
        CART_ABANDONED = "cart.abandoned", "Cart abandoned"
        CART_RECOVERED = "cart.recovered", "Cart recovered"
        ORDER_CREATED = "order.created", "Order created"

    cart = models.ForeignKey(B2cCart, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=32, default="STOREFRONT")
    idempotency_key = models.CharField(max_length=128, unique=True, null=True, blank=True)

    class Meta:
        db_table = "commerce_cart_event"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["cart", "-occurred_at"], name="cart_event_cart_occ_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.cart_id} · {self.event_type}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("CartEvent is append-only; updates are forbidden.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("CartEvent is append-only; deletes are forbidden.")


class B2cCartItem(TimestampedModel):
    cart = models.ForeignKey(
        B2cCart,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="items",
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="b2c_cart_items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    bundle = models.ForeignKey(
        CustomBundle, on_delete=models.CASCADE, null=True, blank=True, related_name="b2c_cart_items"
    )
    bundle_role = models.CharField(
        max_length=16, choices=BundleRole.choices, blank=True, default=""
    )
    sku = models.CharField(max_length=64)
    parent_sku = models.CharField(max_length=32)
    title = models.CharField(max_length=240)
    category = models.CharField(max_length=80)
    metal_color = models.CharField(max_length=24)
    purity_code = models.CharField(max_length=8)
    size = models.PositiveSmallIntegerField(default=14)
    size_unit_label = models.CharField(max_length=40, default="Yüzük Ölçüsü")
    qty = models.PositiveSmallIntegerField(default=1)
    engraving_text = models.CharField(max_length=40, blank=True, default="")
    gift_wrap = models.BooleanField(default=False)
    gift_note = models.CharField(max_length=200, blank=True, default="")
    certificate_label = models.CharField(max_length=120, blank=True, default="")
    stock_status = models.CharField(max_length=24, default="Stokta")
    lead_time_text = models.CharField(max_length=160, blank=True, default="")
    gross_weight_gram = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0"))
    unit_list_price_try = models.DecimalField(max_digits=14, decimal_places=2)
    unit_final_price_try = models.DecimalField(max_digits=14, decimal_places=2)
    rate_snapshot = models.ForeignKey(
        RateSnapshot, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    price_quote = models.ForeignKey(
        PriceQuote, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    snapshot_code = models.CharField(max_length=40)

    class Meta:
        db_table = "commerce_b2c_cart_item"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} · {self.sku} x{self.qty}"


class B2cOrder(TimestampedModel):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "ODEME_BEKLIYOR", "Ödeme Bekleniyor"
        CONFIRMED = "ONAYLANDI", "Sipariş Onaylandı"
        WORKSHOP = "ATOLYE_URETIMDE", "Atölye & Kalite Kontrol"
        SHIPPED = "SIGORTALI_KARGODA", "Sigortalı Kurye Yolda"
        CANCELLED = "IPTAL_EDILDI", "İptal Edildi"
        REFUNDED = "IADE_EDILDI", "İade Edildi"

    order_no = models.CharField(max_length=40, unique=True, db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="b2c_orders")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    rate_snapshot = models.ForeignKey(RateSnapshot, on_delete=models.PROTECT, related_name="b2c_orders")
    price_lock = models.ForeignKey(
        PriceLock, on_delete=models.PROTECT, null=True, blank=True, related_name="b2c_orders"
    )
    gold_rate_try_per_gram = models.DecimalField(max_digits=14, decimal_places=4)

    payment_method = models.CharField(max_length=24)
    accepted_custom_policy = models.BooleanField(default=True)
    # Immutable checkout address / party snapshot (must not follow live Customer edits).
    shipping_full_name = models.CharField(max_length=160, blank=True, default="")
    shipping_phone = models.CharField(max_length=32, blank=True, default="")
    shipping_email = models.EmailField(blank=True, default="")
    shipping_city = models.CharField(max_length=100, blank=True, default="")
    shipping_address = models.TextField(blank=True, default="")
    billing_full_name = models.CharField(max_length=160, blank=True, default="")
    billing_identity_or_tax_no = models.CharField(max_length=32, blank=True, default="")
    billing_city = models.CharField(max_length=100, blank=True, default="")
    billing_address = models.TextField(blank=True, default="")
    subtotal_list_try = models.DecimalField(max_digits=14, decimal_places=2)
    campaign_discount_try = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    transfer_discount_try = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    insured_shipping_try = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    vat_included_try = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    grand_total_try = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.CONFIRMED)

    class Meta:
        db_table = "commerce_b2c_order"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.order_no} ({self.status})"


class B2cOrderItem(TimestampedModel):
    order = models.ForeignKey(B2cOrder, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    bundle = models.ForeignKey(
        CustomBundle, on_delete=models.SET_NULL, null=True, blank=True, related_name="b2c_order_items"
    )
    bundle_role = models.CharField(
        max_length=16, choices=BundleRole.choices, blank=True, default=""
    )
    sku = models.CharField(max_length=64)
    parent_sku = models.CharField(max_length=32)
    title = models.CharField(max_length=240)
    category = models.CharField(max_length=80)
    metal_color = models.CharField(max_length=24)
    purity_code = models.CharField(max_length=8)
    size = models.PositiveSmallIntegerField(default=14)
    size_unit_label = models.CharField(max_length=40)
    qty = models.PositiveSmallIntegerField(default=1)
    engraving_text = models.CharField(max_length=40, blank=True, default="")
    gift_wrap = models.BooleanField(default=False)
    gift_note = models.CharField(max_length=200, blank=True, default="")
    certificate_label = models.CharField(max_length=120, blank=True, default="")
    stock_status = models.CharField(max_length=24)
    lead_time_text = models.CharField(max_length=160, blank=True, default="")
    gross_weight_gram = models.DecimalField(max_digits=10, decimal_places=4)
    unit_list_price_try = models.DecimalField(max_digits=14, decimal_places=2)
    unit_final_price_try = models.DecimalField(max_digits=14, decimal_places=2)
    rate_snapshot = models.ForeignKey(
        RateSnapshot, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    price_quote = models.ForeignKey(
        PriceQuote, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    snapshot_code = models.CharField(max_length=40)

    class Meta:
        db_table = "commerce_b2c_order_item"

    def __str__(self) -> str:
        return f"{self.order.order_no} · {self.sku} x{self.qty}"


class B2bDraftLine(TimestampedModel):
    """Organization-isolated B2B wholesale draft order sheet line."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="b2b_draft_lines"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    bundle = models.ForeignKey(
        CustomBundle, on_delete=models.CASCADE, null=True, blank=True, related_name="b2b_draft_lines"
    )
    bundle_role = models.CharField(
        max_length=16, choices=BundleRole.choices, blank=True, default=""
    )
    sku = models.CharField(max_length=64)
    parent_sku = models.CharField(max_length=32)
    title = models.CharField(max_length=240)
    category = models.CharField(max_length=80)
    metal_color = models.CharField(max_length=24)
    purity_code = models.CharField(max_length=8)
    size = models.PositiveSmallIntegerField(default=14)
    size_unit_label = models.CharField(max_length=40, default="Yüzük Ölçüsü")
    qty = models.PositiveIntegerField(default=1)
    supply_type = models.CharField(max_length=16, default="STOCK")
    dealer_stamp_note = models.CharField(max_length=80, blank=True, default="")
    unit_gross_gram = models.DecimalField(max_digits=10, decimal_places=4)
    unit_net_metal_gram = models.DecimalField(max_digits=10, decimal_places=4)
    unit_fire_included_fine_gram = models.DecimalField(max_digits=10, decimal_places=4)
    unit_labor_and_stone_usd = models.DecimalField(max_digits=14, decimal_places=2)
    unit_wholesale_usd = models.DecimalField(max_digits=14, decimal_places=2)
    unit_wholesale_try = models.DecimalField(max_digits=14, decimal_places=2)
    pricing_currency = models.CharField(max_length=16, default="USD")
    rate_snapshot = models.ForeignKey(
        RateSnapshot, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    price_quote = models.ForeignKey(
        PriceQuote, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    snapshot_code = models.CharField(max_length=40)

    class Meta:
        db_table = "commerce_b2b_draft_line"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.organization.code} · {self.sku} x{self.qty}"


class B2bOrder(TimestampedModel):
    """
    Immutable B2B wholesale order placed on behalf of an Organization & Branch,
    with the placing User stored separately.
    """

    class Status(models.TextChoices):
        PROFORMA_CONFIRMED = "PROFORMA_ONAYLANDI", "Proforma Onaylandı"
        WORKSHOP_PLANNED = "ATOLYE_PLANLANDI", "Atölye Üretim Planlandı"
        READY_FOR_DISPATCH = "SEVK_HAZIR", "Sevke Hazır"
        CANCELLED = "IPTAL_EDILDI", "İptal Edildi"
        REFUNDED = "IADE_EDILDI", "İade Edildi"

    order_no = models.CharField(max_length=40, unique=True, db_index=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="b2b_orders")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, null=True, blank=True, related_name="b2b_orders")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_b2b_orders"
    )
    rate_snapshot = models.ForeignKey(RateSnapshot, on_delete=models.PROTECT, related_name="b2b_orders")

    usd_try_rate = models.DecimalField(max_digits=14, decimal_places=4)
    gold_rate_try_per_gram = models.DecimalField(max_digits=14, decimal_places=4)
    contact_person = models.CharField(max_length=120)
    settlement_method = models.CharField(max_length=24)
    rate_lock_mode = models.CharField(max_length=24)
    consignment_days = models.PositiveSmallIntegerField(null=True, blank=True)
    delivery_method = models.CharField(max_length=32)
    order_note = models.TextField(blank=True, default="")
    accepted_weight_tolerance = models.BooleanField(default=True)
    # Immutable delivery / billing snapshots (org address book may change later).
    shipping_title = models.CharField(max_length=120, blank=True, default="")
    shipping_city = models.CharField(max_length=100, blank=True, default="")
    shipping_address = models.TextField(blank=True, default="")
    shipping_contact_name = models.CharField(max_length=120, blank=True, default="")
    shipping_phone = models.CharField(max_length=32, blank=True, default="")
    billing_title = models.CharField(max_length=120, blank=True, default="")
    billing_city = models.CharField(max_length=100, blank=True, default="")
    billing_address = models.TextField(blank=True, default="")
    billing_contact_name = models.CharField(max_length=120, blank=True, default="")
    billing_phone = models.CharField(max_length=32, blank=True, default="")
    billing_tax_office_and_no = models.CharField(max_length=120, blank=True, default="")

    total_pieces = models.PositiveIntegerField()
    total_gross_gram = models.DecimalField(max_digits=12, decimal_places=4)
    total_has_gold_gram = models.DecimalField(max_digits=12, decimal_places=4)
    total_labor_and_stone_usd = models.DecimalField(max_digits=14, decimal_places=2)
    total_wholesale_usd = models.DecimalField(max_digits=14, decimal_places=2)
    total_wholesale_try = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PROFORMA_CONFIRMED)

    class Meta:
        db_table = "commerce_b2b_order"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.order_no} · {self.organization.code} ({self.status})"


class B2bOrderLine(TimestampedModel):
    order = models.ForeignKey(B2bOrder, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    bundle = models.ForeignKey(
        CustomBundle, on_delete=models.SET_NULL, null=True, blank=True, related_name="b2b_order_lines"
    )
    bundle_role = models.CharField(
        max_length=16, choices=BundleRole.choices, blank=True, default=""
    )
    sku = models.CharField(max_length=64)
    parent_sku = models.CharField(max_length=32)
    title = models.CharField(max_length=240)
    category = models.CharField(max_length=80)
    metal_color = models.CharField(max_length=24)
    purity_code = models.CharField(max_length=8)
    size = models.PositiveSmallIntegerField(default=14)
    size_unit_label = models.CharField(max_length=40)
    qty = models.PositiveIntegerField(default=1)
    supply_type = models.CharField(max_length=16)
    dealer_stamp_note = models.CharField(max_length=80, blank=True, default="")
    unit_gross_gram = models.DecimalField(max_digits=10, decimal_places=4)
    unit_net_metal_gram = models.DecimalField(max_digits=10, decimal_places=4)
    unit_fire_included_fine_gram = models.DecimalField(max_digits=10, decimal_places=4)
    unit_labor_and_stone_usd = models.DecimalField(max_digits=14, decimal_places=2)
    unit_wholesale_usd = models.DecimalField(max_digits=14, decimal_places=2)
    unit_wholesale_try = models.DecimalField(max_digits=14, decimal_places=2)
    pricing_currency = models.CharField(max_length=16)
    rate_snapshot = models.ForeignKey(
        RateSnapshot, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    price_quote = models.ForeignKey(
        PriceQuote, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    snapshot_code = models.CharField(max_length=40)

    class Meta:
        db_table = "commerce_b2b_order_line"

    def __str__(self) -> str:
        return f"{self.order.order_no} · {self.sku} x{self.qty}"


class CartRecoverySession(TimestampedModel):
    """Lifecycle for abandoned B2C cart / B2B draft recovery outreach."""

    class Segment(models.TextChoices):
        B2C = "B2C", "B2C"
        B2B = "B2B", "B2B"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Aktif"
        SUPPRESSED = "SUPPRESSED", "Bastırıldı"
        COMPLETED = "COMPLETED", "Tamamlandı"
        COOLDOWN = "COOLDOWN", "Bekleme"

    class Stage(models.TextChoices):
        NONE = "NONE", "Yok"
        T1 = "T1", "Aşama 1"
        T2 = "T2", "Aşama 2"
        T3 = "T3", "Aşama 3"

    class SuppressReason(models.TextChoices):
        CHECKOUT = "CHECKOUT", "Sipariş tamamlandı"
        EMPTIED = "EMPTIED", "Sepet/taslak boşaltıldı"
        OPT_OUT = "OPT_OUT", "Opt-out"
        MANUAL = "MANUAL", "Manuel"
        CONSENT_WITHDRAWN = "CONSENT_WITHDRAWN", "İzin geri çekildi"

    segment = models.CharField(max_length=8, choices=Segment.choices, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart_recovery_sessions",
    )
    guest_email = models.EmailField(blank=True, default="", db_index=True)
    guest_cart_snapshot = models.JSONField(default=dict, blank=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart_recovery_sessions",
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    stage = models.CharField(max_length=8, choices=Stage.choices, default=Stage.NONE)
    cart_fingerprint = models.CharField(max_length=64, blank=True, default="")
    cart_updated_at = models.DateTimeField(db_index=True)
    last_touch_at = models.DateTimeField(null=True, blank=True)
    cart_value_try = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    has_stock_lines = models.BooleanField(default=False)
    line_count = models.PositiveIntegerField(default=0)
    stock_line_count = models.PositiveIntegerField(default=0)
    production_line_count = models.PositiveIntegerField(default=0)
    first_item_title = models.CharField(max_length=240, blank=True, default="")
    suppress_reason = models.CharField(
        max_length=32, choices=SuppressReason.choices, blank=True, default=""
    )
    cooldown_until = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "commerce_cart_recovery_session"
        ordering = ["-cart_updated_at"]
        indexes = [
            models.Index(fields=["status", "stage", "cart_updated_at"], name="idx_recovery_scan"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "segment"],
                condition=models.Q(segment="B2C", status="ACTIVE", user__isnull=False),
                name="uniq_active_b2c_recovery_user",
            ),
            models.UniqueConstraint(
                fields=["guest_email", "segment"],
                condition=models.Q(segment="B2C", status="ACTIVE", user__isnull=True)
                & ~models.Q(guest_email=""),
                name="uniq_active_b2c_recovery_guest",
            ),
            models.UniqueConstraint(
                fields=["organization", "segment"],
                condition=models.Q(segment="B2B", status="ACTIVE"),
                name="uniq_active_b2b_recovery_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.segment} · {self.status} · {self.stage}"


class CartRecoveryAttempt(TimestampedModel):
    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "E-posta"
        IN_APP = "IN_APP", "Uygulama İçi"
        OPS_TASK = "OPS_TASK", "OPS Görevi"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        SMS = "SMS", "SMS"

    class Status(models.TextChoices):
        SENT = "SENT", "Gönderildi"
        FAILED = "FAILED", "Hata"
        SKIPPED = "SKIPPED", "Atlandı"

    session = models.ForeignKey(
        CartRecoverySession, on_delete=models.CASCADE, related_name="attempts"
    )
    stage = models.CharField(max_length=8, choices=CartRecoverySession.Stage.choices)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    template_key = models.CharField(max_length=80, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SENT)
    provider_ref = models.CharField(max_length=64, blank=True, default="")
    skip_reason = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        db_table = "commerce_cart_recovery_attempt"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "stage", "channel"],
                name="uniq_recovery_attempt_stage_channel",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.session_id} · {self.stage}/{self.channel}"


class OpsSalesTask(TimestampedModel):
    class Kind(models.TextChoices):
        ABANDONED_CART_CALL = "ABANDONED_CART_CALL", "B2C Sepet Ara"
        ABANDONED_DRAFT_CALL = "ABANDONED_DRAFT_CALL", "B2B Taslak Ara"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Açık"
        DONE = "DONE", "Tamamlandı"
        DISMISSED = "DISMISSED", "Kapatıldı"

    kind = models.CharField(max_length=32, choices=Kind.choices)
    segment = models.CharField(max_length=8, choices=CartRecoverySession.Segment.choices)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ops_sales_tasks_as_customer",
    )
    guest_email = models.EmailField(blank=True, default="")
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ops_sales_tasks",
    )
    recovery_session = models.ForeignKey(
        CartRecoverySession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ops_tasks",
    )
    cart_value_try = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    due_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)
    script_key = models.CharField(max_length=80, blank=True, default="")
    context_snapshot = models.JSONField(default=dict, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "commerce_ops_sales_task"
        ordering = ["-due_at"]

    def __str__(self) -> str:
        return f"{self.kind} · {self.status}"
