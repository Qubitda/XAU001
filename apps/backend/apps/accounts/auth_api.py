"""Account lifecycle: B2C register, password change/reset, email verification."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.mail import send_email_verification, send_password_reset_email
from apps.accounts.models import User
from apps.accounts.throttling import LoginRateThrottle
from apps.accounts.tokens import email_verify_token, password_reset_token
from apps.audit.services import record_audit
from apps.common.responses import envelope_response
from apps.customers.models import Customer
from apps.organizations.models import OrganizationMembership
from config.exceptions import DomainError

from .api import _serialize_session


def _b2c_self_register_enabled() -> bool:
    return getattr(settings, "ENABLE_B2C_SELF_REGISTER", True)


def _resolve_user_uid(uidb64: str) -> User | None:
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.filter(pk=uid).first()
    except (TypeError, ValueError, OverflowError):
        return None


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    fullName = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    acceptedKvkk = serializers.BooleanField(required=False, default=False)
    acceptedMarketingEmail = serializers.BooleanField(required=False, default=False)
    consents = serializers.ListField(
        child=serializers.DictField(), required=False, allow_empty=True
    )

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class PasswordChangeSerializer(serializers.Serializer):
    currentPassword = serializers.CharField(write_only=True)
    newPassword = serializers.CharField(write_only=True, min_length=8)

    def validate_newPassword(self, value: str) -> str:
        validate_password(value)
        return value


class PasswordForgotSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    newPassword = serializers.CharField(write_only=True, min_length=8)

    def validate_newPassword(self, value: str) -> str:
        validate_password(value)
        return value


class EmailVerifySerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()


class B2cRegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    @extend_schema(tags=["Auth"], summary="B2C perakende üyelik kaydı", request=RegisterSerializer)
    def post(self, request: Request):
        if not _b2c_self_register_enabled():
            raise DomainError(
                "B2C self-registration bu kurulumda kapalı.",
                code="B2C_REGISTER_DISABLED",
                status_code=403,
            )
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=d["email"],
                    password=d["password"],
                    full_name=d["fullName"].strip(),
                    phone=(d.get("phone") or "").strip(),
                )
                OrganizationMembership.objects.create(
                    user=user,
                    organization=None,
                    role_key=OrganizationMembership.RoleKey.B2C_CUSTOMER,
                    is_active=True,
                )
                from apps.consent.models import (
                    ConsentChannel,
                    ConsentPurpose,
                    ConsentSource,
                    ConsentStatus,
                )
                from apps.consent.services import append_consent
                from apps.customers.services import get_or_update_customer_for_user

                customer = get_or_update_customer_for_user(
                    user=user,
                    full_name=user.full_name,
                    email=user.email,
                    phone=user.phone,
                    segment=Customer.Segment.B2C,
                )
                raw_consents = d.get("consents")
                if isinstance(raw_consents, list) and raw_consents:
                    for raw in raw_consents:
                        if not isinstance(raw, dict):
                            continue
                        purpose = str(raw.get("purpose") or "").upper()
                        if not purpose:
                            continue
                        append_consent(
                            customer=customer,
                            purpose=purpose,
                            channel=str(raw.get("channel") or ConsentChannel.WEB).upper(),
                            status=str(raw.get("status") or ConsentStatus.GRANTED).upper(),
                            source=ConsentSource.REGISTER,
                            document_version=str(raw.get("documentVersion") or ""),
                            document_hash=str(raw.get("documentHash") or ""),
                            actor=user,
                        )
                else:
                    if d.get("acceptedKvkk"):
                        append_consent(
                            customer=customer,
                            purpose=ConsentPurpose.KVKK_NOTICE,
                            channel=ConsentChannel.WEB,
                            status=ConsentStatus.GRANTED,
                            source=ConsentSource.REGISTER,
                            actor=user,
                        )
                    if d.get("acceptedMarketingEmail"):
                        append_consent(
                            customer=customer,
                            purpose=ConsentPurpose.COMMERCIAL_EMAIL,
                            channel=ConsentChannel.EMAIL,
                            status=ConsentStatus.GRANTED,
                            source=ConsentSource.REGISTER,
                            actor=user,
                        )
        except IntegrityError as exc:
            raise DomainError(
                "Bu e-posta ile kayıt tamamlanamadı.",
                code="REGISTER_FAILED",
                status_code=400,
            ) from exc
        send_email_verification(user=user, also_welcome=True)
        login(request, user)
        membership = (
            OrganizationMembership.objects.filter(
                user=user, role_key=OrganizationMembership.RoleKey.B2C_CUSTOMER, is_active=True
            )
            .order_by("created_at")
            .first()
        )
        if membership is not None:
            request.session["active_membership_id"] = str(membership.id)
            request.session.pop("active_branch_id", None)
        record_audit(action="B2C_REGISTER", entity_type="User", entity_id=str(user.id), actor=user)
        payload = _serialize_session(request)
        payload["emailVerificationSent"] = True
        return envelope_response(payload, request, status=status.HTTP_201_CREATED)


class PasswordChangeView(APIView):
    @extend_schema(tags=["Auth"], summary="Oturum açıkken parola değiştir", request=PasswordChangeSerializer)
    def post(self, request: Request):
        ser = PasswordChangeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(ser.validated_data["currentPassword"]):
            raise DomainError("Mevcut parola hatalı.", code="INVALID_PASSWORD", status_code=400)
        user.set_password(ser.validated_data["newPassword"])
        user.save(update_fields=["password", "updated_at"])
        # Keep session alive after password change.
        from django.contrib.auth import update_session_auth_hash

        update_session_auth_hash(request, user)
        record_audit(action="PASSWORD_CHANGED", entity_type="User", entity_id=str(user.id), actor=user)
        return envelope_response({"passwordChanged": True}, request)


class PasswordForgotView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    @extend_schema(tags=["Auth"], summary="Parola sıfırlama e-postası gönder", request=PasswordForgotSerializer)
    def post(self, request: Request):
        ser = PasswordForgotSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        # Always return success to avoid account enumeration.
        if user is not None and user.has_usable_password():
            send_password_reset_email(user=user)
            record_audit(action="PASSWORD_RESET_REQUESTED", entity_type="User", entity_id=str(user.id), actor=user)
        return envelope_response({"accepted": True}, request)


class PasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    @extend_schema(tags=["Auth"], summary="Token ile parola sıfırla", request=PasswordResetSerializer)
    def post(self, request: Request):
        ser = PasswordResetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = _resolve_user_uid(ser.validated_data["uid"])
        if user is None or not password_reset_token.check_token(user, ser.validated_data["token"]):
            raise DomainError(
                "Parola sıfırlama bağlantısı geçersiz veya süresi dolmuş.",
                code="RESET_TOKEN_INVALID",
                status_code=400,
            )
        user.set_password(ser.validated_data["newPassword"])
        user.save(update_fields=["password", "updated_at"])
        record_audit(action="PASSWORD_RESET_COMPLETED", entity_type="User", entity_id=str(user.id), actor=user)
        return envelope_response({"passwordReset": True}, request)


class EmailVerifyView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    @extend_schema(tags=["Auth"], summary="E-posta doğrulama token'ını onayla", request=EmailVerifySerializer)
    def post(self, request: Request):
        ser = EmailVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = _resolve_user_uid(ser.validated_data["uid"])
        if user is None or not email_verify_token.check_token(user, ser.validated_data["token"]):
            raise DomainError(
                "Doğrulama bağlantısı geçersiz veya süresi dolmuş.",
                code="VERIFY_TOKEN_INVALID",
                status_code=400,
            )
        if user.email_verified_at is None:
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at", "updated_at"])
            record_audit(action="EMAIL_VERIFIED", entity_type="User", entity_id=str(user.id), actor=user)
        return envelope_response(
            {"emailVerified": True, "emailVerifiedAt": user.email_verified_at.isoformat()},
            request,
        )


class EmailResendVerificationView(APIView):
    throttle_classes = [LoginRateThrottle]

    @extend_schema(tags=["Auth"], summary="E-posta doğrulama bağlantısını yeniden gönder")
    def post(self, request: Request):
        user = request.user
        if user.email_verified_at is not None:
            return envelope_response({"alreadyVerified": True}, request)
        sent = send_email_verification(user=user)
        return envelope_response({"emailVerificationSent": sent}, request)
