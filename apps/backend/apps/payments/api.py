from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.api_keys.permissions import StorefrontScopedPermissionsMixin
from apps.common.responses import envelope_response
from apps.idempotency.mixins import IdempotentCreateMixin

from .services import handle_iyzico_callback, handle_iyzico_webhook, initiate_iyzico_checkout


class CheckoutFormInitializeSerializer(serializers.Serializer):
    customerName = serializers.CharField(max_length=160)
    customerPhone = serializers.CharField(max_length=32)
    customerEmail = serializers.EmailField()
    isTurkishCitizen = serializers.BooleanField(required=False, default=True)
    identityNumber = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    shippingCity = serializers.CharField(max_length=80)
    shippingAddress = serializers.CharField(max_length=500)
    billingName = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    billingCity = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    billingAddress = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    billingIdentityOrTaxNo = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    paymentMethod = serializers.ChoiceField(choices=["CREDIT_CARD", "INSTALLMENT"], default="CREDIT_CARD")
    acceptedCustomPolicy = serializers.BooleanField(default=True)

    def validate(self, attrs):
        is_tr = attrs.get("isTurkishCitizen", True)
        tckn = (attrs.get("identityNumber") or "").strip()
        if is_tr:
            if not tckn.isdigit() or len(tckn) != 11:
                raise serializers.ValidationError(
                    {"identityNumber": "Türk vatandaşları için 11 haneli TC Kimlik No zorunludur."}
                )
        elif tckn and (not tckn.isdigit() or len(tckn) != 11):
            raise serializers.ValidationError(
                {"identityNumber": "TC Kimlik No girildiyse 11 haneli rakam olmalıdır."}
            )
        attrs["identityNumber"] = tckn
        return attrs


class StorefrontCheckoutFormInitializeView(
    IdempotentCreateMixin, StorefrontScopedPermissionsMixin, APIView
):
    """POST /api/v1/storefront/payments/checkout-form/initialize"""

    def post(self, request: Request):
        serializer = CheckoutFormInitializeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = initiate_iyzico_checkout(
            user=request.user, payload=serializer.validated_data, request=request
        )
        return envelope_response(result, request, status=201)


@method_decorator(csrf_exempt, name="dispatch")
class IyzicoCallbackView(APIView):
    """
    POST /api/v1/payments/iyzico/callback
    iyzico browser redirect posts `token`. CSRF exempt; auth via stored token match + CF retrieve.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request):
        token = (
            request.data.get("token")
            or request.POST.get("token")
            or request.query_params.get("token")
            or ""
        )
        raw = {}
        try:
            if hasattr(request.data, "dict"):
                raw = dict(request.data.dict())
            elif isinstance(request.data, dict):
                raw = dict(request.data)
        except Exception:
            raw = {"token": token}
        return handle_iyzico_callback(token=str(token).strip(), raw_payload=raw)

    def get(self, request: Request):
        # Some tunnels/tools may bounce as GET; still accept token.
        token = request.query_params.get("token") or ""
        return handle_iyzico_callback(token=str(token).strip(), raw_payload={"token": token})


@method_decorator(csrf_exempt, name="dispatch")
class IyzicoWebhookView(APIView):
    """POST /api/v1/payments/iyzico/webhook — secondary CF notification."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request):
        payload = {}
        try:
            if hasattr(request.data, "dict"):
                payload = dict(request.data.dict())
            elif isinstance(request.data, dict):
                payload = dict(request.data)
        except Exception:
            payload = {}
        result = handle_iyzico_webhook(payload=payload)
        return envelope_response(result, request)
