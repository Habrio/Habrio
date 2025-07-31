import os
import logging
from celery import shared_task
from twilio.rest import Client

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_whatsapp_message_task(self, to: str, body: str) -> None:
    """Send WhatsApp message asynchronously via Twilio."""
    # Skip sending when running tests or missing credentials
    if os.environ.get("APP_ENV") == "testing":
        logger.info("[WhatsApp] testing mode - message to %s: %s", to, body)
        return
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    whatsapp_from = os.environ.get("TWILIO_WHATSAPP_FROM")
    try:
        client = Client(sid, token)
        client.messages.create(from_=whatsapp_from, to=f"whatsapp:{to}", body=body)
        logger.info("[WhatsApp] message sent to %s", to)
    except Exception as exc:
        logger.error("WhatsApp send failed: %s", exc)
        raise self.retry(exc=exc)
