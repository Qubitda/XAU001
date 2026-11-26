from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="mail.send_transactional_email",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def send_transactional_email_task(
    self,
    *,
    template_key: str,
    recipient: str,
    context: dict[str, Any] | None = None,
    organization_id: str | None = None,
    mail_log_id: str | None = None,
) -> str:
    from .models import MailLog
    from .service import MailService

    log = MailService().send(
        template_key=template_key,
        recipient=recipient,
        context=context or {},
        organization_id=organization_id,
        mail_log_id=mail_log_id,
    )
    if log.status == MailLog.Status.FAILED:
        if self.request.retries < (self.max_retries or 0):
            raise self.retry(exc=Exception(log.error_message or "mail_failed"))
        logger.error(
            "Mail permanently failed key=%s to=%s log=%s",
            template_key,
            recipient,
            log.id,
        )
    return str(log.id)
