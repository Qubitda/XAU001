import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="organizations.apply_document_retention")
def apply_document_retention_task() -> dict:
    from .retention import deactivate_expired_documents, hard_delete_inactive_documents_past_grace

    deactivated = deactivate_expired_documents()
    hard_deleted = hard_delete_inactive_documents_past_grace()
    return {"deactivated": deactivated, "hardDeleted": hard_deleted}
