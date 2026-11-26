from celery import shared_task

from .services import deliver_webhook


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
)
def deliver_webhook_task(self, endpoint_id: str, event: str, data: dict) -> str:
    deliver_webhook(endpoint_id, event, data)
    return endpoint_id