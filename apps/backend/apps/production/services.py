import uuid
from django.db import transaction
from django.utils import timezone
from apps.audit.services import record_audit
from apps.organizations.models import Organization
from config.exceptions import DomainError
from .models import WorkOrder


WORK_ORDER_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    WorkOrder.Status.PLANNED: {WorkOrder.Status.CASTING, WorkOrder.Status.COMPLETED},
    WorkOrder.Status.CASTING: {WorkOrder.Status.SETTING, WorkOrder.Status.QUALITY_CHECK},
    WorkOrder.Status.SETTING: {WorkOrder.Status.QUALITY_CHECK, WorkOrder.Status.COMPLETED},
    WorkOrder.Status.QUALITY_CHECK: {WorkOrder.Status.SETTING, WorkOrder.Status.COMPLETED},
    WorkOrder.Status.COMPLETED: set(),
}


@transaction.atomic
def create_work_order(
    *,
    source_order_no: str,
    sku: str,
    size: int = 14,
    quantity: int = 1,
    organization: Organization | None = None,
    engraving_or_stamp_note: str = "",
    work_order_no: str | None = None,
    actor=None,
) -> WorkOrder:
    wo_no = (work_order_no or "").strip().upper() or f"WO-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}"
    if WorkOrder.objects.filter(work_order_no=wo_no).exists():
        raise DomainError(f"İş emri numarası zaten mevcut: {wo_no}", code="DUPLICATE_WORK_ORDER", status_code=409)

    wo = WorkOrder.objects.create(
        work_order_no=wo_no,
        source_order_no=source_order_no.strip(),
        organization=organization,
        sku=sku.strip().upper(),
        size=size,
        quantity=quantity,
        engraving_or_stamp_note=engraving_or_stamp_note.strip()[:120],
        status=WorkOrder.Status.PLANNED,
    )
    record_audit(
        action="WORK_ORDER_CREATED",
        entity_type="WorkOrder",
        entity_id=wo.work_order_no,
        actor=actor,
        organization=organization,
        metadata={"source_order_no": wo.source_order_no, "sku": wo.sku, "quantity": wo.quantity},
    )
    return wo


@transaction.atomic
def transition_work_order_status(*, work_order_id_or_no: str, next_status: str, actor=None) -> WorkOrder:
    if next_status not in WorkOrder.Status.values:
        raise DomainError("Geçersiz iş emri durumu.", code="INVALID_STATUS", status_code=400)

    qs = WorkOrder.objects.select_for_update().select_related("organization")
    wo = qs.filter(work_order_no=work_order_id_or_no).first()
    if wo is None:
        try:
            uuid.UUID(str(work_order_id_or_no))
            wo = qs.filter(id=work_order_id_or_no).first()
        except ValueError:
            wo = None
    if wo is None:
        raise DomainError("İş emri bulunamadı.", code="WORK_ORDER_NOT_FOUND", status_code=404)

    if wo.status == next_status:
        return wo

    allowed = WORK_ORDER_ALLOWED_TRANSITIONS.get(wo.status, set())
    if next_status not in allowed:
        raise DomainError(
            f"İş emri '{wo.status}' durumundan '{next_status}' durumuna geçirilemez.",
            code="INVALID_STATUS_TRANSITION",
            status_code=409,
        )

    prev = wo.status
    wo.status = next_status
    wo.save(update_fields=["status", "updated_at"])
    record_audit(
        action="WORK_ORDER_STATUS_UPDATED",
        entity_type="WorkOrder",
        entity_id=wo.work_order_no,
        actor=actor,
        organization=wo.organization,
        metadata={"from": prev, "to": next_status},
    )
    return wo
