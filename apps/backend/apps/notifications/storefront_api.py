"""Authenticated storefront in-app notifications (own inbox)."""

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.api_keys.permissions import StorefrontScopedPermissionsMixin
from apps.common.responses import envelope_response
from config.exceptions import DomainError

from .models import Notification


def serialize_my_notification(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "channel": n.channel,
        "title": n.title,
        "body": n.body,
        "isRead": n.is_read,
        "createdAt": n.created_at.isoformat(),
    }


class NotificationReadSerializer(serializers.Serializer):
    isRead = serializers.BooleanField(required=False, default=True)


class StorefrontNotificationListView(StorefrontScopedPermissionsMixin, APIView):
    @extend_schema(tags=["Storefront - Notifications"], summary="Bildirimlerim")
    def get(self, request: Request):
        qs = Notification.objects.filter(
            recipient=request.user, channel=Notification.Channel.IN_APP
        ).order_by("-created_at")[:40]
        unread = Notification.objects.filter(
            recipient=request.user, channel=Notification.Channel.IN_APP, is_read=False
        ).count()
        return envelope_response(
            {
                "unreadCount": unread,
                "items": [serialize_my_notification(n) for n in qs],
            },
            request,
        )


class StorefrontNotificationDetailView(StorefrontScopedPermissionsMixin, APIView):
    @extend_schema(
        tags=["Storefront - Notifications"],
        summary="Bildirimi okundu işaretle",
        request=NotificationReadSerializer,
    )
    @transaction.atomic
    def patch(self, request: Request, notification_id: str):
        notif = (
            Notification.objects.select_for_update()
            .filter(id=notification_id, recipient=request.user)
            .first()
        )
        if notif is None:
            raise DomainError("Bildirim bulunamadı.", code="NOT_FOUND", status_code=404)
        serializer = NotificationReadSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        notif.is_read = bool(serializer.validated_data.get("isRead", True))
        notif.save(update_fields=["is_read", "updated_at"])
        return envelope_response(serialize_my_notification(notif), request)


class StorefrontNotificationReadAllView(StorefrontScopedPermissionsMixin, APIView):
    @extend_schema(tags=["Storefront - Notifications"], summary="Tümünü okundu işaretle")
    def post(self, request: Request):
        updated = Notification.objects.filter(
            recipient=request.user, channel=Notification.Channel.IN_APP, is_read=False
        ).update(is_read=True, updated_at=timezone.now())
        return envelope_response({"updated": updated}, request)
