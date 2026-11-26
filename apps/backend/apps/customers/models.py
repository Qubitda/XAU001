from django.conf import settings
from django.db import models

from apps.common.models import TimestampedModel
from apps.organizations.models import Organization


class Customer(TimestampedModel):
    """
    Individual or corporate customer record — independent of accounts.User.
    A customer does NOT need a portal login account to place walk-in/guest or phone orders.
    Kept separate from Organization (B2B business partner).
    """

    class CustomerType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Bireysel Müşteri"
        CORPORATE = "CORPORATE", "Kurumsal Müşteri"

    class Segment(models.TextChoices):
        B2C = "B2C", "B2C"
        B2B = "B2B", "B2B"
        GUEST = "GUEST", "Misafir"

    customer_type = models.CharField(
        max_length=16, choices=CustomerType.choices, default=CustomerType.INDIVIDUAL
    )
    segment = models.CharField(
        max_length=8, choices=Segment.choices, default=Segment.B2C, db_index=True
    )
    external_id = models.CharField(
        max_length=64, unique=True, null=True, blank=True, db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_profiles",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
    )
    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    email_verified = models.BooleanField(default=False)
    identity_or_tax_no = models.CharField(max_length=32, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    address = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "customers_customer"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "-created_at"], name="cust_email_created_idx"),
            models.Index(fields=["user", "is_active"], name="cust_user_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.get_customer_type_display()})"


class CustomerAddress(TimestampedModel):
    class AddressType(models.TextChoices):
        SHIPPING = "SHIPPING", "Teslimat"
        BILLING = "BILLING", "Fatura"
        OTHER = "OTHER", "Diğer"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
    address_type = models.CharField(
        max_length=16, choices=AddressType.choices, default=AddressType.SHIPPING
    )
    title = models.CharField(max_length=120)
    city = models.CharField(max_length=100, blank=True, default="")
    district = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=16, blank=True, default="")
    line = models.TextField()
    contact_name = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "customers_address"
        ordering = ["-is_default", "address_type", "title"]

    def __str__(self) -> str:
        return f"{self.customer.full_name} · {self.title}"
