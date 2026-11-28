"""Notification task creation & recipient validation tests."""

import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, TransactionTestCase

from apps.notifications.models import Notification
from apps.notifications.tasks import send_order_notification

User = get_user_model()


class NotificationTaskTests(TransactionTestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="notif-u@tara.local", password="pw")

    def test_send_order_notification_creates_in_app_record(self) -> None:
        res = send_order_notification(
            recipient_id=str(self.user.id),
            title="Siparişiniz Alındı",
            body="TG-1001 numaralı siparişiniz oluşturuldu.",
        )
        notif = Notification.objects.get(recipient=self.user, title="Siparişiniz Alındı")
        self.assertEqual(res, str(notif.id))

    def test_send_order_notification_unknown_user_raises(self) -> None:
        with self.assertRaises(IntegrityError):
            send_order_notification(
                recipient_id=str(uuid.uuid4()),
                title="Test",
                body="Test",
            )
