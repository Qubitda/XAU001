"""Customer identity helpers — get-or-update, no orphan proliferation."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q

from .models import Customer


@transaction.atomic
def get_or_update_customer_for_user(
    *,
    user,
    full_name: str = "",
    phone: str = "",
    email: str = "",
    identity_or_tax_no: str = "",
    city: str = "",
    address: str = "",
    segment: str | None = None,
    external_id: str | None = None,
) -> Customer:
    """
    Resolve a single active Customer for the given user (or email).
    Prefer user-linked active profile; otherwise email match; otherwise create.
    """
    name = (full_name or getattr(user, "full_name", "") or "").strip()
    phone_v = (phone or getattr(user, "phone", "") or "").strip()
    email_v = (email or getattr(user, "email", "") or "").strip().lower()
    identity = (identity_or_tax_no or "").strip()
    city_v = (city or "").strip()
    address_v = (address or "").strip()
    seg = segment or Customer.Segment.B2C

    customer = (
        Customer.objects.select_for_update()
        .filter(user=user, is_active=True)
        .order_by("-updated_at")
        .first()
    )
    if customer is None and email_v:
        customer = (
            Customer.objects.select_for_update()
            .filter(Q(email__iexact=email_v), is_active=True)
            .order_by("-updated_at")
            .first()
        )
        if customer is not None and customer.user_id is None:
            customer.user = user

    if customer is None:
        return Customer.objects.create(
            customer_type=Customer.CustomerType.INDIVIDUAL,
            user=user,
            full_name=name or email_v or "Müşteri",
            phone=phone_v,
            email=email_v,
            identity_or_tax_no=identity,
            city=city_v,
            address=address_v,
            segment=seg,
            external_id=(external_id or "").strip() or None,
        )

    changed = False
    if name and customer.full_name != name:
        customer.full_name = name
        changed = True
    if phone_v and customer.phone != phone_v:
        customer.phone = phone_v
        changed = True
    if email_v and customer.email.lower() != email_v:
        customer.email = email_v
        changed = True
    if identity and customer.identity_or_tax_no != identity:
        customer.identity_or_tax_no = identity
        changed = True
    if city_v and customer.city != city_v:
        customer.city = city_v
        changed = True
    if address_v and customer.address != address_v:
        customer.address = address_v
        changed = True
    if customer.user_id != user.id:
        customer.user = user
        changed = True
    if segment and customer.segment != seg:
        customer.segment = seg
        changed = True
    if external_id and not customer.external_id:
        customer.external_id = external_id.strip()
        changed = True
    if changed:
        customer.save()
    return customer


@transaction.atomic
def upsert_customer_from_external(
    *,
    external_id: str,
    full_name: str,
    email: str = "",
    phone: str = "",
    segment: str = Customer.Segment.B2C,
    email_verified: bool | None = None,
    identity_or_tax_no: str = "",
    city: str = "",
    address: str = "",
    user=None,
) -> tuple[Customer, bool]:
    """Upsert by external_id (then email). Returns (customer, created)."""
    ext = (external_id or "").strip()
    email_v = (email or "").strip().lower()
    customer = None
    if ext:
        customer = Customer.objects.select_for_update().filter(external_id=ext).first()
    if customer is None and email_v:
        customer = (
            Customer.objects.select_for_update()
            .filter(email__iexact=email_v, is_active=True)
            .order_by("-updated_at")
            .first()
        )

    if customer is None:
        customer = Customer.objects.create(
            customer_type=Customer.CustomerType.INDIVIDUAL,
            user=user,
            external_id=ext or None,
            segment=segment,
            full_name=(full_name or "").strip() or email_v or "Müşteri",
            email=email_v,
            phone=(phone or "").strip(),
            identity_or_tax_no=(identity_or_tax_no or "").strip(),
            city=(city or "").strip(),
            address=(address or "").strip(),
            email_verified=bool(email_verified) if email_verified is not None else False,
        )
        return customer, True

    customer.full_name = (full_name or customer.full_name).strip()
    if email_v:
        customer.email = email_v
    if phone:
        customer.phone = phone.strip()
    if identity_or_tax_no:
        customer.identity_or_tax_no = identity_or_tax_no.strip()
    if city:
        customer.city = city.strip()
    if address:
        customer.address = address.strip()
    if ext and not customer.external_id:
        customer.external_id = ext
    customer.segment = segment or customer.segment
    if email_verified is not None:
        customer.email_verified = bool(email_verified)
    if user is not None and customer.user_id is None:
        customer.user = user
    customer.save()
    return customer, False
