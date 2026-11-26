from django.conf import settings
from django.db import models
from apps.common.models import TimestampedModel


class Notification(TimestampedModel):
    class Channel(models.TextChoices):
        IN_APP = "IN_APP", "Uygulama İçi"
        EMAIL = "EMAIL", "E-posta"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.IN_APP)
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "notifications_notification"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.channel}] {self.recipient.email} · {self.title}"
