import os
import logging
from celery import Celery
from celery.signals import task_failure, task_retry

broker_url = os.environ.get("CELERY_BROKER_URL", "memory://")
backend_url = os.environ.get("CELERY_RESULT_BACKEND", "cache+memory://")

celery_app = Celery("habrio", broker=broker_url, backend=backend_url)
celery_app.conf.task_always_eager = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "0") == "1"
celery_app.conf.task_eager_propagates = True
celery_app.conf.task_store_eager_result = False

logger = logging.getLogger(__name__)

@task_failure.connect
def _log_failure(sender=None, task_id=None, exception=None, **kwargs):
    logger.error("Task %s failed: %s", getattr(sender, 'name', task_id), exception)

@task_retry.connect
def _log_retry(sender=None, request=None, reason=None, **kwargs):
    logger.warning("Task %s retry due to: %s", getattr(sender, 'name', ''), reason)
