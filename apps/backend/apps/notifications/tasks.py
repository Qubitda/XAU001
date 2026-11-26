from celery import shared_task
from .models import Notification


@shared_task
def send_order_notification(recipient_id: str, title: str, body: str) -> str:
    notif = Notification.objects.create(
        recipient_id=recipient_id,
        channel=Notification.Channel.IN_APP,
        title=title,
        body=body,
    )
    return str(notif.id)
