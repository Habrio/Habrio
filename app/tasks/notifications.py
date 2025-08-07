import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_whatsapp_message_task(self, to: str, body: str) -> None:
    """Log message instead of sending via Twilio."""
    logger.info("[WhatsApp disabled] message to %s: %s", to, body)
