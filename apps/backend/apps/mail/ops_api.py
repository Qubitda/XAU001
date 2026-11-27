"""OPS / platform management for SMTP settings and email templates."""

from __future__ import annotations

from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import envelope_response
from apps.organizations.selectors import resolve_tenant_context
from config.exceptions import DomainError

from .crypto import encrypt_secret
from .models import EmailTemplate, MailLog, SmtpSetting


class SmtpSettingSerializer(serializers.Serializer):
    organizationId = serializers.UUIDField(required=False, allow_null=True)
    host = serializers.CharField(max_length=255)
    port = serializers.IntegerField(min_value=1, max_value=65535, default=587)
    encryption = serializers.ChoiceField(choices=["TLS", "SSL", "NONE"], default="TLS")
    username = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    password = serializers.CharField(max_length=512, required=False, allow_blank=True, default="")
    fromName = serializers.CharField(max_length=160, required=False, allow_blank=True, default="Tara Gold")
    fromEmail = serializers.EmailField()
    isActive = serializers.BooleanField(default=True)


class EmailTemplateSerializer(serializers.Serializer):
    organizationId = serializers.UUIDField(required=False, allow_null=True)
    templateKey = serializers.CharField(max_length=64)
    subject = serializers.CharField(max_length=255)
    bodyHtml = serializers.CharField()
    primaryColor = serializers.CharField(max_length=16, required=False, allow_blank=True, default="#4A101C")
    logoUrl = serializers.URLField(required=False, allow_blank=True, default="")
    isActive = serializers.BooleanField(default=True)


def _ser_smtp(row: SmtpSetting) -> dict:
    return {
        "id": str(row.id),
        "organizationId": str(row.organization_id) if row.organization_id else None,
        "host": row.host,
        "port": row.port,
        "encryption": row.encryption,
        "username": row.username,
        "hasPassword": bool(row.password_ciphertext),
        "fromName": row.from_name,
        "fromEmail": row.from_email,
        "isActive": row.is_active,
        "updatedAt": row.updated_at.isoformat(),
    }


def _ser_tpl(row: EmailTemplate) -> dict:
    return {
        "id": str(row.id),
        "organizationId": str(row.organization_id) if row.organization_id else None,
        "templateKey": row.template_key,
        "subject": row.subject,
        "bodyHtml": row.body_html,
        "primaryColor": row.primary_color,
        "logoUrl": row.logo_url,
        "isActive": row.is_active,
        "updatedAt": row.updated_at.isoformat(),
    }


class OpsSmtpSettingsView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "mail:manage"

    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        qs = SmtpSetting.objects.select_related("organization").order_by("-is_active", "-updated_at")
        if not ctx.is_ops:
            if ctx.organization is None:
                raise DomainError("Organizasyon gerekli.", code="ORG_REQUIRED", status_code=403)
            qs = qs.filter(organization=ctx.organization)
        return envelope_response([_ser_smtp(r) for r in qs[:100]], request)

    def post(self, request: Request):
        ctx = resolve_tenant_context(request)
        ser = SmtpSettingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        org_id = d.get("organizationId")
        if not ctx.is_ops:
            if ctx.organization is None:
                raise DomainError("Organizasyon gerekli.", code="ORG_REQUIRED", status_code=403)
            org_id = ctx.organization.id
        elif "organizationId" not in request.data:
            org_id = None

        existing = (
            SmtpSetting.objects.filter(organization_id=org_id)
            .order_by("-is_active", "-updated_at")
            .first()
        )
        if d.get("isActive", True):
            SmtpSetting.objects.filter(organization_id=org_id, is_active=True).update(is_active=False)

        row = SmtpSetting(
            organization_id=org_id,
            host=d["host"],
            port=d["port"],
            encryption=d["encryption"],
            username=d.get("username") or "",
            from_name=d.get("fromName") or "Tara Gold",
            from_email=d["fromEmail"],
            is_active=d.get("isActive", True),
        )
        if d.get("password"):
            row.password_ciphertext = encrypt_secret(d["password"])
        elif existing and existing.password_ciphertext:
            row.password_ciphertext = existing.password_ciphertext
        row.save()
        return envelope_response(_ser_smtp(row), request, status=201)


class OpsEmailTemplatesView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "mail:manage"

    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        qs = EmailTemplate.objects.select_related("organization").all()
        if not ctx.is_ops:
            if ctx.organization is None:
                raise DomainError("Organizasyon gerekli.", code="ORG_REQUIRED", status_code=403)
            qs = qs.filter(organization=ctx.organization)
        key = (request.query_params.get("templateKey") or "").strip()
        if key:
            qs = qs.filter(template_key=key)
        return envelope_response([_ser_tpl(r) for r in qs[:200]], request)

    def post(self, request: Request):
        ctx = resolve_tenant_context(request)
        ser = EmailTemplateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        org_id = d.get("organizationId")
        if not ctx.is_ops:
            if ctx.organization is None:
                raise DomainError("Organizasyon gerekli.", code="ORG_REQUIRED", status_code=403)
            org_id = ctx.organization.id
        row, _ = EmailTemplate.objects.update_or_create(
            organization_id=org_id,
            template_key=d["templateKey"],
            defaults={
                "subject": d["subject"],
                "body_html": d["bodyHtml"],
                "primary_color": d.get("primaryColor") or "#4A101C",
                "logo_url": d.get("logoUrl") or "",
                "is_active": d.get("isActive", True),
            },
        )
        return envelope_response(_ser_tpl(row), request, status=201)


class OpsMailLogsView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "mail:manage"

    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        qs = MailLog.objects.all()
        if not ctx.is_ops:
            if ctx.organization is None:
                raise DomainError("Organizasyon gerekli.", code="ORG_REQUIRED", status_code=403)
            qs = qs.filter(organization=ctx.organization)
        status_f = (request.query_params.get("status") or "").strip().upper()
        if status_f:
            qs = qs.filter(status=status_f)
        rows = [
            {
                "id": str(r.id),
                "organizationId": str(r.organization_id) if r.organization_id else None,
                "recipient": r.recipient,
                "templateKey": r.template_key,
                "subject": r.subject,
                "status": r.status,
                "errorMessage": r.error_message,
                "sentAt": r.sent_at.isoformat() if r.sent_at else None,
                "createdAt": r.created_at.isoformat(),
            }
            for r in qs[:100]
        ]
        return envelope_response(rows, request)


class OpsMailLogRetryView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "mail:manage"

    def post(self, request: Request, log_id):
        ctx = resolve_tenant_context(request)
        row = MailLog.objects.filter(id=log_id).first()
        if row is None:
            raise DomainError("Mail log bulunamadı.", code="NOT_FOUND", status_code=404)
        if not ctx.is_ops:
            if ctx.organization is None or row.organization_id != ctx.organization.id:
                raise DomainError("Yetkisiz.", code="FORBIDDEN", status_code=403)
        if row.status == MailLog.Status.SENT:
            raise DomainError("Zaten iletilmiş mail tekrar gönderilemez.", code="ALREADY_SENT", status_code=400)

        from .events import emit_mail_event

        new_id = emit_mail_event(
            template_key=row.template_key,
            recipient=row.recipient,
            context=row.context_snapshot or {},
            organization_id=str(row.organization_id) if row.organization_id else None,
        )
        return envelope_response({"retriedFrom": str(row.id), "newMailLogId": new_id}, request)


class OpsSmtpTestMailSerializer(serializers.Serializer):
    to = serializers.EmailField(required=False, allow_blank=True)
    organizationId = serializers.UUIDField(required=False, allow_null=True)


class OpsSmtpTestMailView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "mail:manage"

    def post(self, request: Request):
        ctx = resolve_tenant_context(request)
        ser = OpsSmtpTestMailSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        org_id = d.get("organizationId")
        if not ctx.is_ops:
            if ctx.organization is None:
                raise DomainError("Organizasyon gerekli.", code="ORG_REQUIRED", status_code=403)
            org_id = ctx.organization.id

        to = (d.get("to") or "").strip() or (request.user.email or "")
        if not to:
            raise DomainError("Test alıcısı gerekli.", code="RECIPIENT_REQUIRED", status_code=400)

        from .events import emit_mail_event
        from .constants import WELCOME

        log_id = emit_mail_event(
            template_key=WELCOME,
            recipient=to,
            organization_id=str(org_id) if org_id else None,
            context={
                "customer_name": getattr(request.user, "full_name", None)
                or getattr(request.user, "email", "Test"),
                "verify_url": "",
            },
        )
        return envelope_response({"mailLogId": log_id, "to": to}, request)


class OpsSmtpConnectionTestView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "mail:manage"

    def post(self, request: Request):
        ctx = resolve_tenant_context(request)
        org = None
        if not ctx.is_ops:
            if ctx.organization is None:
                raise DomainError("Organizasyon gerekli.", code="ORG_REQUIRED", status_code=403)
            org = ctx.organization
        result = MailService().test_smtp_connection(organization=org)
        return envelope_response(result, request)
