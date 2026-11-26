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
    apply_safe_ordering,
    envelope_response,
    paginated_envelope_response,
    parse_bool_param,
)
from config.exceptions import DomainError
from .models import Notification


def serialize_ops_notification(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "recipientId": str(n.recipient_id),
        "recipientEmail": n.recipient.email,
        "recipientName": n.recipient.full_name,
        "channel": n.channel,
        "title": n.title,
        "body": n.body,
        "isRead": n.is_read,
        "createdAt": n.created_at.isoformat(),
        "updatedAt": n.updated_at.isoformat(),
    }


class OpsNotificationCreateSerializer(serializers.Serializer):
    recipientId = serializers.UUIDField()
    channel = serializers.ChoiceField(choices=Notification.Channel.values, default=Notification.Channel.IN_APP)
    title = serializers.CharField(max_length=200)
    body = serializers.CharField(max_length=4000)


class OpsNotificationUpdateSerializer(serializers.Serializer):
    isRead = serializers.BooleanField()


class OpsNotificationListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "notifications:manage"

    @extend_schema(tags=["OPS - Notifications"], summary="Bildirimleri listele")
    def get(self, request: Request):
        qs = Notification.objects.select_related("recipient")
        recipient_id = (request.query_params.get("recipientId") or "").strip()
        if recipient_id:
            qs = qs.filter(recipient_id=recipient_id)
        channel = (request.query_params.get("channel") or "").strip().upper()
        if channel:
            qs = qs.filter(channel=channel)
        is_read = parse_bool_param(request.query_params.get("isRead") or request.query_params.get("is_read"))
        if is_read is not None:
            qs = qs.filter(is_read=is_read)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q) | Q(recipient__email__icontains=q))
        qs = apply_safe_ordering(qs, request, allowed_fields={"createdAt": "created_at", "isRead": "is_read"}, default="-created_at")
        return paginated_envelope_response(qs, request, serialize_ops_notification)

    @extend_schema(tags=["OPS - Notifications"], summary="Kullanıcıya yeni bildirim gönder", request=OpsNotificationCreateSerializer)
    @transaction.atomic
    def post(self, request: Request):
        serializer = OpsNotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        recipient = User.objects.filter(id=d["recipientId"]).first()
        if recipient is None:
            raise DomainError("Alıcı kullanıcı bulunamadı.", code="USER_NOT_FOUND", status_code=404)

        notif = Notification.objects.create(
            recipient=recipient,
            channel=d["channel"],
            title=d["title"].strip(),
            body=d["body"].strip(),
        )
        record_audit(
            action="OPS_NOTIFICATION_SENT",
            entity_type="Notification",
            entity_id=str(notif.id),
            actor=request.user,
            metadata={"recipient_email": recipient.email, "channel": notif.channel},
        )
        notif = Notification.objects.select_related("recipient").get(id=notif.id)
        return envelope_response(serialize_ops_notification(notif), request, status=201)


class OpsNotificationDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "notifications:manage"

    @extend_schema(tags=["OPS - Notifications"], summary="Bildirim detayını getir")
    def get(self, request: Request, notification_id: str):
        notif = Notification.objects.select_related("recipient").filter(id=notification_id).first()
        if notif is None:
            raise DomainError("Bildirim bulunamadı.", code="NOTIFICATION_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_notification(notif), request)

    @extend_schema(tags=["OPS - Notifications"], summary="Bildirim okundu bilgisini güncelle", request=OpsNotificationUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, notification_id: str):
        notif = Notification.objects.select_for_update().select_related("recipient").filter(id=notification_id).first()
        if notif is None:
            raise DomainError("Bildirim bulunamadı.", code="NOTIFICATION_NOT_FOUND", status_code=404)
        serializer = OpsNotificationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notif.is_read = serializer.validated_data["isRead"]
        notif.save(update_fields=["is_read", "updated_at"])
        return envelope_response(serialize_ops_notification(notif), request)

    @extend_schema(tags=["OPS - Notifications"], summary="Bildirimi sil")
    @transaction.atomic
    def delete(self, request: Request, notification_id: str):
        notif = Notification.objects.select_for_update().filter(id=notification_id).first()
        if notif is None:
            raise DomainError("Bildirim bulunamadı.", code="NOTIFICATION_NOT_FOUND", status_code=404)
        notif.delete()
        return envelope_response({"id": str(notification_id), "deleted": True}, request)
