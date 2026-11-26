from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.accounts.models import User
from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import (
    MONEY_Q,
    apply_safe_ordering,
    dec_str,
    envelope_response,
    paginated_envelope_response,
    parse_bool_param,
)
from apps.organizations.models import Organization
from config.exceptions import DomainError
from .models import Customer, CustomerAddress


def serialize_customer_address(a: CustomerAddress) -> dict:
    return {
        "id": str(a.id),
        "customerId": str(a.customer_id),
        "addressType": a.address_type,
        "title": a.title,
        "city": a.city,
        "district": a.district,
        "postalCode": a.postal_code,
        "line": a.line,
        "contactName": a.contact_name,
        "phone": a.phone,
        "isDefault": a.is_default,
        "isActive": a.is_active,
        "createdAt": a.created_at.isoformat(),
        "updatedAt": a.updated_at.isoformat(),
    }


def serialize_ops_customer(c: Customer, *, detail: bool = False) -> dict:
    payload = {
        "id": str(c.id),
        "customerType": c.customer_type,
        "userId": str(c.user_id) if c.user_id else None,
        "userEmail": c.user.email if c.user else None,
        "organizationId": str(c.organization_id) if c.organization_id else None,
        "organizationCode": c.organization.code if c.organization else None,
        "organizationName": c.organization.name if c.organization else None,
        "fullName": c.full_name,
        "phone": c.phone,
        "email": c.email,
        "emailVerified": c.email_verified,
        "segment": c.segment,
        "externalId": c.external_id,
        "identityOrTaxNo": c.identity_or_tax_no,
        "city": c.city,
        "address": c.address,
        "isActive": c.is_active,
        "notes": c.notes,
        "createdAt": c.created_at.isoformat(),
        "updatedAt": c.updated_at.isoformat(),
    }
    if detail:
        addresses = list(c.addresses.order_by("-is_default", "address_type", "title"))
        orders = list(c.b2c_orders.order_by("-created_at")[:40])
        payload["addresses"] = [serialize_customer_address(a) for a in addresses]
        payload["orders"] = [
            {
                "orderNo": o.order_no,
                "status": o.status,
                "grandTotalTry": dec_str(o.grand_total_try, MONEY_Q),
                "paymentMethod": o.payment_method,
                "shippingFullName": o.shipping_full_name or c.full_name,
                "shippingCity": o.shipping_city or c.city,
                "billingFullName": o.billing_full_name or o.shipping_full_name or c.full_name,
                "createdAt": o.created_at.isoformat(),
            }
            for o in orders
        ]
        payload["orderCount"] = c.b2c_orders.count()
    return payload


class OpsCustomerCreateSerializer(serializers.Serializer):
    customerType = serializers.ChoiceField(
        choices=Customer.CustomerType.values, default=Customer.CustomerType.INDIVIDUAL
    )
    userId = serializers.UUIDField(required=False, allow_null=True)
    organizationId = serializers.UUIDField(required=False, allow_null=True)
    fullName = serializers.CharField(max_length=160)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    identityOrTaxNo = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    address = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    isActive = serializers.BooleanField(required=False, default=True)


class OpsCustomerUpdateSerializer(serializers.Serializer):
    customerType = serializers.ChoiceField(choices=Customer.CustomerType.values, required=False)
    userId = serializers.UUIDField(required=False, allow_null=True)
    organizationId = serializers.UUIDField(required=False, allow_null=True)
    fullName = serializers.CharField(max_length=160, required=False)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    identityOrTaxNo = serializers.CharField(max_length=32, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    isActive = serializers.BooleanField(required=False)


class CustomerAddressWriteSerializer(serializers.Serializer):
    addressType = serializers.ChoiceField(
        choices=CustomerAddress.AddressType.values, default=CustomerAddress.AddressType.SHIPPING
    )
    title = serializers.CharField(max_length=120)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    district = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    postalCode = serializers.CharField(max_length=16, required=False, allow_blank=True, default="")
    line = serializers.CharField()
    contactName = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    isDefault = serializers.BooleanField(required=False, default=False)
    isActive = serializers.BooleanField(required=False, default=True)


class CustomerAddressPatchSerializer(serializers.Serializer):
    addressType = serializers.ChoiceField(choices=CustomerAddress.AddressType.values, required=False)
    title = serializers.CharField(max_length=120, required=False)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    district = serializers.CharField(max_length=100, required=False, allow_blank=True)
    postalCode = serializers.CharField(max_length=16, required=False, allow_blank=True)
    line = serializers.CharField(required=False)
    contactName = serializers.CharField(max_length=120, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    isDefault = serializers.BooleanField(required=False)
    isActive = serializers.BooleanField(required=False)


def _get_customer(customer_id: str) -> Customer:
    customer = Customer.objects.select_related("user", "organization").filter(id=customer_id).first()
    if customer is None:
        raise DomainError("Müşteri bulunamadı.", code="CUSTOMER_NOT_FOUND", status_code=404)
    return customer


class OpsCustomerListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "customers:manage"

    @extend_schema(tags=["OPS - Customers"], summary="Müşterileri listele, ara ve filtrele")
    def get(self, request: Request):
        qs = Customer.objects.select_related("user", "organization")
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(full_name__icontains=q)
                | Q(phone__icontains=q)
                | Q(email__icontains=q)
                | Q(identity_or_tax_no__icontains=q)
                | Q(city__icontains=q)
            )
        ctype = (request.query_params.get("customerType") or request.query_params.get("customer_type") or "").strip()
        if ctype:
            qs = qs.filter(customer_type=ctype)
        org_id = (request.query_params.get("organizationId") or "").strip()
        if org_id:
            qs = qs.filter(organization_id=org_id)
        city = (request.query_params.get("city") or "").strip()
        if city:
            qs = qs.filter(city__icontains=city)
        is_active = parse_bool_param(request.query_params.get("isActive") or request.query_params.get("is_active"))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)

        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"fullName": "full_name", "city": "city", "createdAt": "created_at"},
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, serialize_ops_customer)

    @extend_schema(tags=["OPS - Customers"], summary="Yeni müşteri oluştur", request=OpsCustomerCreateSerializer)
    @transaction.atomic
    def post(self, request: Request):
        serializer = OpsCustomerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        user = None
        if d.get("userId"):
            user = User.objects.filter(id=d["userId"]).first()
            if user is None:
                raise DomainError("Bağlı kullanıcı bulunamadı.", code="USER_NOT_FOUND", status_code=404)

        org = None
        if d.get("organizationId"):
            org = Organization.objects.filter(id=d["organizationId"]).first()
            if org is None:
                raise DomainError("Bağlı organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)

        customer = Customer.objects.create(
            customer_type=d["customerType"],
            user=user,
            organization=org,
            full_name=d["fullName"].strip(),
            phone=d.get("phone", "").strip(),
            email=d.get("email", "").strip().lower(),
            identity_or_tax_no=d.get("identityOrTaxNo", "").strip(),
            city=d.get("city", "").strip(),
            address=d.get("address", "").strip(),
            notes=d.get("notes", "").strip(),
            is_active=d.get("isActive", True),
        )
        record_audit(
            action="OPS_CUSTOMER_CREATED",
            entity_type="Customer",
            entity_id=str(customer.id),
            actor=request.user,
            organization=org,
            metadata={"full_name": customer.full_name, "customer_type": customer.customer_type},
        )
        customer = Customer.objects.select_related("user", "organization").get(id=customer.id)
        return envelope_response(serialize_ops_customer(customer, detail=True), request, status=201)


class OpsCustomerDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "customers:manage"

    @extend_schema(tags=["OPS - Customers"], summary="Müşteri detayını getir")
    def get(self, request: Request, customer_id: str):
        customer = _get_customer(customer_id)
        return envelope_response(serialize_ops_customer(customer, detail=True), request)

    @extend_schema(tags=["OPS - Customers"], summary="Müşteri bilgilerini güncelle", request=OpsCustomerUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, customer_id: str):
        customer = Customer.objects.select_for_update().filter(id=customer_id).first()
        if customer is None:
            raise DomainError("Müşteri bulunamadı.", code="CUSTOMER_NOT_FOUND", status_code=404)

        serializer = OpsCustomerUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        if "userId" in d:
            if d["userId"] is None:
                customer.user = None
            else:
                user = User.objects.filter(id=d["userId"]).first()
                if user is None:
                    raise DomainError("Bağlı kullanıcı bulunamadı.", code="USER_NOT_FOUND", status_code=404)
                customer.user = user
        if "organizationId" in d:
            if d["organizationId"] is None:
                customer.organization = None
            else:
                org = Organization.objects.filter(id=d["organizationId"]).first()
                if org is None:
                    raise DomainError("Bağlı organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)
                customer.organization = org

        field_map = {
            "customerType": "customer_type",
            "fullName": "full_name",
            "phone": "phone",
            "email": "email",
            "identityOrTaxNo": "identity_or_tax_no",
            "city": "city",
            "address": "address",
            "notes": "notes",
            "isActive": "is_active",
        }
        for api_key, model_field in field_map.items():
            if api_key in d:
                val = d[api_key].strip() if isinstance(d[api_key], str) else d[api_key]
                setattr(customer, model_field, val.lower() if model_field == "email" else val)

        customer.save()
        record_audit(
            action="OPS_CUSTOMER_UPDATED",
            entity_type="Customer",
            entity_id=str(customer.id),
            actor=request.user,
            organization=customer.organization,
        )
        customer = Customer.objects.select_related("user", "organization").get(id=customer.id)
        return envelope_response(serialize_ops_customer(customer, detail=True), request)

    @extend_schema(tags=["OPS - Customers"], summary="Müşteriyi pasifleştir (sipariş varsa silinmez)")
    @transaction.atomic
    def delete(self, request: Request, customer_id: str):
        customer = Customer.objects.select_for_update().filter(id=customer_id).first()
        if customer is None:
            raise DomainError("Müşteri bulunamadı.", code="CUSTOMER_NOT_FOUND", status_code=404)
        if customer.b2c_orders.exists():
            customer.is_active = False
            customer.save(update_fields=["is_active", "updated_at"])
            record_audit(
                action="OPS_CUSTOMER_DEACTIVATED",
                entity_type="Customer",
                entity_id=str(customer.id),
                actor=request.user,
                organization=customer.organization,
            )
            return envelope_response(serialize_ops_customer(customer, detail=True), request)
        cid = str(customer.id)
        org = customer.organization
        customer.delete()
        record_audit(
            action="OPS_CUSTOMER_DELETED",
            entity_type="Customer",
            entity_id=cid,
            actor=request.user,
            organization=org,
        )
        return envelope_response({"id": cid, "deleted": True}, request)


class OpsCustomerAddressListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "customers:manage"

    @extend_schema(tags=["OPS - Customers"], summary="Müşteri adreslerini listele")
    def get(self, request: Request, customer_id: str):
        customer = _get_customer(customer_id)
        items = [serialize_customer_address(a) for a in customer.addresses.all()]
        return envelope_response(items, request)

    @extend_schema(tags=["OPS - Customers"], summary="Müşteri adresi ekle")
    @transaction.atomic
    def post(self, request: Request, customer_id: str):
        customer = _get_customer(customer_id)
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
            contact_name=d.get("contactName", "").strip(),
            phone=d.get("phone", "").strip(),
            is_default=d.get("isDefault", False),
            is_active=d.get("isActive", True),
        )
        record_audit(
            action="OPS_CUSTOMER_ADDRESS_CREATED",
            entity_type="CustomerAddress",
            entity_id=str(addr.id),
            actor=request.user,
            organization=customer.organization,
        )
        return envelope_response(serialize_customer_address(addr), request, status=201)


class OpsCustomerAddressDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "customers:manage"

    @extend_schema(tags=["OPS - Customers"], summary="Müşteri adresini güncelle")
    @transaction.atomic
    def patch(self, request: Request, customer_id: str, address_id: str):
        customer = _get_customer(customer_id)
        addr = CustomerAddress.objects.select_for_update().filter(id=address_id, customer=customer).first()
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
            CustomerAddress.objects.filter(customer=customer, is_default=True).exclude(id=addr.id).update(
                is_default=False
            )
        addr.save()
        return envelope_response(serialize_customer_address(addr), request)

    @extend_schema(tags=["OPS - Customers"], summary="Müşteri adresini pasifleştir")
    @transaction.atomic
    def delete(self, request: Request, customer_id: str, address_id: str):
        customer = _get_customer(customer_id)
        addr = CustomerAddress.objects.select_for_update().filter(id=address_id, customer=customer).first()
        if addr is None:
            raise DomainError("Adres bulunamadı.", code="ADDRESS_NOT_FOUND", status_code=404)
        addr.is_active = False
        addr.save(update_fields=["is_active", "updated_at"])
        return envelope_response(serialize_customer_address(addr), request)
