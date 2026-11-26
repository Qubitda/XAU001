"""Storefront address book + profile for authenticated B2C users."""

from __future__ import annotations

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.api_keys.permissions import StorefrontScopedPermissionsMixin
from apps.common.responses import envelope_response
from config.exceptions import DomainError

from .api import (
    CustomerAddressPatchSerializer,
    CustomerAddressWriteSerializer,
    serialize_customer_address,
)
from .models import Customer, CustomerAddress
from .services import get_or_update_customer_for_user


def _customer_for_user(user) -> Customer:
    return get_or_update_customer_for_user(
        user=user,
        full_name=getattr(user, "full_name", "") or "",
        phone=getattr(user, "phone", "") or "",
        email=getattr(user, "email", "") or "",
        segment=Customer.Segment.B2C,
    )


def serialize_storefront_profile(customer: Customer, user) -> dict:
    return {
        "customerId": str(customer.id),
        "fullName": customer.full_name,
        "email": customer.email or user.email,
        "phone": customer.phone or getattr(user, "phone", "") or "",
        "emailVerified": bool(
            customer.email_verified or getattr(user, "email_verified_at", None)
        ),
        "segment": customer.segment,
        "city": customer.city,
        "address": customer.address,
        "identityOrTaxNo": customer.identity_or_tax_no,
    }


class StorefrontProfilePatchSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=160, required=False)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    identityOrTaxNo = serializers.CharField(max_length=32, required=False, allow_blank=True)


class StorefrontProfileView(StorefrontScopedPermissionsMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Storefront - Account"], summary="B2C profil getir")
    def get(self, request: Request):
        customer = _customer_for_user(request.user)
        return envelope_response(serialize_storefront_profile(customer, request.user), request)

    @extend_schema(tags=["Storefront - Account"], summary="B2C profil güncelle")
    @transaction.atomic
    def patch(self, request: Request):
        ser = StorefrontProfilePatchSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        customer = _customer_for_user(request.user)
        for api_key, field in {
            "fullName": "full_name",
            "phone": "phone",
            "city": "city",
            "address": "address",
            "identityOrTaxNo": "identity_or_tax_no",
        }.items():
            if api_key in d:
                setattr(customer, field, d[api_key].strip() if isinstance(d[api_key], str) else d[api_key])
        customer.save()
        if "fullName" in d and hasattr(request.user, "full_name"):
            request.user.full_name = d["fullName"].strip()
            request.user.save(update_fields=["full_name", "updated_at"])
        if "phone" in d and hasattr(request.user, "phone"):
            request.user.phone = d["phone"].strip()
            request.user.save(update_fields=["phone", "updated_at"])
        return envelope_response(serialize_storefront_profile(customer, request.user), request)


class StorefrontAddressListCreateView(StorefrontScopedPermissionsMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Storefront - Account"], summary="Adres defteri listele")
    def get(self, request: Request):
        customer = _customer_for_user(request.user)
        items = [
            serialize_customer_address(a)
            for a in customer.addresses.filter(is_active=True).order_by("-is_default", "title")
        ]
        return envelope_response(items, request)

    @extend_schema(tags=["Storefront - Account"], summary="Adres ekle", request=CustomerAddressWriteSerializer)
    @transaction.atomic
    def post(self, request: Request):
        customer = _customer_for_user(request.user)
        ser = CustomerAddressWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if d.get("isDefault"):
            CustomerAddress.objects.filter(customer=customer, is_default=True).update(is_default=False)
        addr = CustomerAddress.objects.create(
            customer=customer,
            address_type=d.get("addressType", CustomerAddress.AddressType.SHIPPING),
            title=d["title"].strip(),
            city=d.get("city", "").strip(),
            district=d.get("district", "").strip(),
            postal_code=d.get("postalCode", "").strip(),
            line=d["line"].strip(),
            contact_name=d.get("contactName", "").strip() or customer.full_name,
            phone=d.get("phone", "").strip() or customer.phone,
            is_default=d.get("isDefault", False),
            is_active=d.get("isActive", True),
        )
        return envelope_response(serialize_customer_address(addr), request, status=201)


class StorefrontAddressDetailView(StorefrontScopedPermissionsMixin, APIView):
    permission_classes = [IsAuthenticated]

    def _get_addr(self, user, address_id: str) -> CustomerAddress:
        customer = _customer_for_user(user)
        addr = CustomerAddress.objects.filter(id=address_id, customer=customer).first()
        if addr is None:
            raise DomainError("Adres bulunamadı.", code="ADDRESS_NOT_FOUND", status_code=404)
        return addr

    @extend_schema(tags=["Storefront - Account"], summary="Adres güncelle")
    @transaction.atomic
    def patch(self, request: Request, address_id: str):
        addr = CustomerAddress.objects.select_for_update().filter(
            id=address_id, customer=_customer_for_user(request.user)
        ).first()
        if addr is None:
            raise DomainError("Adres bulunamadı.", code="ADDRESS_NOT_FOUND", status_code=404)
        ser = CustomerAddressPatchSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        field_map = {
            "addressType": "address_type",
            "title": "title",
            "city": "city",
            "district": "district",
            "postalCode": "postal_code",
            "line": "line",
            "contactName": "contact_name",
            "phone": "phone",
            "isDefault": "is_default",
            "isActive": "is_active",
        }
        for api_key, model_field in field_map.items():
            if api_key in d:
                val = d[api_key].strip() if isinstance(d[api_key], str) else d[api_key]
                setattr(addr, model_field, val)
        if d.get("isDefault"):
            CustomerAddress.objects.filter(customer=addr.customer, is_default=True).exclude(
                id=addr.id
            ).update(is_default=False)
        addr.save()
        return envelope_response(serialize_customer_address(addr), request)

    @extend_schema(tags=["Storefront - Account"], summary="Adres sil (pasifleştir)")
    @transaction.atomic
    def delete(self, request: Request, address_id: str):
        addr = self._get_addr(request.user, address_id)
        addr.is_active = False
        addr.is_default = False
        addr.save(update_fields=["is_active", "is_default", "updated_at"])
        return envelope_response(serialize_customer_address(addr), request)
