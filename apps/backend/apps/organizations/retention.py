"""
KVKK-oriented retention helpers for partner KYC documents.

Policy (code-enforced soft retention):
- Documents with valid_until in the past are marked inactive (not hard-deleted).
- Hard delete / anonymization remains an OPS legal workflow outside automated purge
  unless DOCUMENT_HARD_DELETE_DAYS is set (>0).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def deactivate_expired_documents() -> int:
    from .models import OrganizationDocument

    today = timezone.localdate()
    qs = OrganizationDocument.objects.filter(is_active=True, valid_until__isnull=False, valid_until__lt=today)
    count = qs.update(is_active=False, updated_at=timezone.now())
    if count:
        logger.info("KVKK retention: deactivated %s expired organization documents", count)
    return count


def hard_delete_inactive_documents_past_grace() -> int:
    days = int(getattr(settings, "DOCUMENT_HARD_DELETE_DAYS", 0) or 0)
    if days <= 0:
        return 0
    from .models import OrganizationDocument

    cutoff = timezone.now() - timedelta(days=days)
    qs = OrganizationDocument.objects.filter(is_active=False, updated_at__lte=cutoff)
    deleted = 0
    for doc in qs.iterator():
        if doc.file:
            try:
                doc.file.delete(save=False)
            except Exception:
                logger.exception("Failed deleting file for document %s", doc.id)
        doc.delete()
        deleted += 1
    if deleted:
        logger.info("KVKK retention: hard-deleted %s inactive documents older than %s days", deleted, days)
    return deleted
