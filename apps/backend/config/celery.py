import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("taragold")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.update(
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=60,
    task_time_limit=120,
    task_default_retry_delay=15,
)
app.autodiscover_tasks()
