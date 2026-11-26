"""OPS B2C cart tracking APIs."""

from __future__ import annotations

from django.db.models import Q
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import envelope_response, paginated_envelope_response
from config.exceptions import DomainError

from .cart_sync import serialize_b2c_cart
from .models import B2cCart


class OpsB2cCartListView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {"GET": "carts:view"}

    @extend_schema(tags=["OPS - Carts"], summary="B2C sepet listesi")
    def get(self, request: Request):
        qs = B2cCart.objects.select_related("user", "customer", "converted_order").all()
        status = (request.query_params.get("status") or "").strip().upper()
        if status:
            qs = qs.filter(status=status)
        checkout = (request.query_params.get("checkoutState") or "").strip().upper()
        if checkout:
            qs = qs.filter(checkout_state=checkout)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(external_id__icontains=q)
                | Q(guest_email__icontains=q)
                | Q(user__email__icontains=q)
                | Q(customer__full_name__icontains=q)
            )
        date_from = parse_datetime((request.query_params.get("from") or "").strip() or "")
        date_to = parse_datetime((request.query_params.get("to") or "").strip() or "")
        if date_from:
            qs = qs.filter(last_activity_at__gte=date_from)
        if date_to:
            qs = qs.filter(last_activity_at__lte=date_to)
        qs = qs.order_by("-last_activity_at")
        return paginated_envelope_response(qs, request, serialize_b2c_cart)


class OpsB2cCartDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "carts:view"

    @extend_schema(tags=["OPS - Carts"], summary="B2C sepet detay + events")
    def get(self, request: Request, cart_id: str):
        cart = (
            B2cCart.objects.select_related("user", "customer", "converted_order")
            .prefetch_related("items", "events")
            .filter(id=cart_id)
            .first()
        )
        if cart is None:
            raise DomainError("Sepet bulunamadı.", code="CART_NOT_FOUND", status_code=404)
        return envelope_response(serialize_b2c_cart(cart, detail=True), request)


class OpsCustomerCartsView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {"GET": "carts:view"}

    @extend_schema(tags=["OPS - Carts"], summary="Müşteri sepetleri")
    def get(self, request: Request, customer_id: str):
        qs = (
            B2cCart.objects.select_related("user", "converted_order")
            .filter(customer_id=customer_id)
            .order_by("-last_activity_at")
        )
        return envelope_response([serialize_b2c_cart(c) for c in qs[:100]], request)
