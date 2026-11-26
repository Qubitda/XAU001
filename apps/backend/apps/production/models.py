from django.db import models
from apps.common.models import TimestampedModel
from apps.organizations.models import Organization


class WorkOrder(TimestampedModel):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planlandı"
        CASTING = "CASTING", "Döküm / Montür"
        SETTING = "SETTING", "Mıhlama"
        QUALITY_CHECK = "QUALITY_CHECK", "Kalite Kontrol & Tartım"
        COMPLETED = "COMPLETED", "Tamamlandı"

    work_order_no = models.CharField(max_length=40, unique=True, db_index=True)
    source_order_no = models.CharField(max_length=40, db_index=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True)
    sku = models.CharField(max_length=64)
    size = models.PositiveSmallIntegerField(default=14)
    quantity = models.PositiveIntegerField(default=1)
    engraving_or_stamp_note = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)

    class Meta:
        db_table = "production_work_order"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.work_order_no} ({self.sku} · {self.status})"
