"""Notification provider stubs with swappable integrations.

Replace the stub logic with real integrations (SendGrid, AWS SES, Twilio,
AfricasTalking, etc.) before production use. Provider selection is controlled by
environment variables.
"""
import logging
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)


def send_email(email_message):
    """Return a fake provider reference; real sending is done via Django's backend."""
    ref = str(uuid.uuid4())
    logger.info(f"[STUB] Email provider logged email {ref} to {email_message.recipient}")
    return {'status': 'sent', 'provider_ref': ref}


def send_sms(sms_message):
    """Dispatch SMS using the configured provider or a stub."""
    provider = getattr(settings, 'SMS_PROVIDER', 'stub').lower()
    ref = str(uuid.uuid4())

    if provider == 'stub':
        logger.info(f"[STUB] Sending SMS {ref} to {sms_message.recipient}")
        return {'status': 'sent', 'provider_ref': ref}

    if provider == 'africastalking':
        # Real integration would use the africastalking Python SDK.
        logger.warning(f"[AFRICAS TALKING] SMS to {sms_message.recipient} not sent — configure credentials")
        return {
            'status': 'failed',
            'error': 'AfricasTalking credentials not configured.',
            'provider_ref': ref,
        }

    if provider == 'twilio':
        logger.warning(f"[TWILIO] SMS to {sms_message.recipient} not sent — configure credentials")
        return {
            'status': 'failed',
            'error': 'Twilio credentials not configured.',
            'provider_ref': ref,
        }

    return {'status': 'failed', 'error': f'Unknown SMS provider: {provider}'}
