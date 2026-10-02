"""Notification providers with swappable integrations.

Provider selection is controlled by environment variables:

    SMS_PROVIDER=termii|africastalking|twilio|stub

Termii (the Nigerian-standard SMS gateway) needs:
    TERMII_API_KEY      — from app.termii.com → API settings
    TERMII_SENDER_ID    — approved alphanumeric sender ID (e.g. school name)
    TERMII_BASE_URL     — default https://v3.api.termii.com
"""
import json
import logging
import urllib.error
import urllib.request
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 20


def _post_json(url, payload, headers=None):
    """Minimal JSON POST — keeps the provider dependency-free."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', **(headers or {})},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return resp.status, json.loads(resp.read() or '{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or '{}')
        except Exception:
            return e.code, {}
    except urllib.error.URLError as e:
        return 0, {'error': str(e)}


def _normalize_ng_phone(phone):
    """Termii wants MSISDN without '+' — normalise common Nigerian formats."""
    digits = ''.join(c for c in (phone or '') if c.isdigit())
    if digits.startswith('234'):
        return digits
    if digits.startswith('0') and len(digits) == 11:
        return '234' + digits[1:]
    return digits


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

    if provider == 'termii':
        api_key = getattr(settings, 'TERMII_API_KEY', '')
        if not api_key:
            logger.warning('[TERMII] TERMII_API_KEY not set — SMS skipped')
            return {'status': 'failed', 'error': 'TERMII_API_KEY not configured.', 'provider_ref': ref}
        base = getattr(settings, 'TERMII_BASE_URL', 'https://v3.api.termii.com').rstrip('/')
        status_code, body = _post_json(f'{base}/api/sms/send', {
            'api_key': api_key,
            'to': _normalize_ng_phone(sms_message.recipient),
            'from': getattr(settings, 'TERMII_SENDER_ID', 'TabsForge'),
            'sms': sms_message.message,
            'type': 'plain',
            'channel': getattr(settings, 'TERMII_CHANNEL', 'generic'),
        })
        message_id = body.get('message_id') or body.get('messageId')
        if status_code == 200 and message_id:
            return {'status': 'sent', 'provider_ref': str(message_id)}
        error = body.get('message') or body.get('error') or f'HTTP {status_code}'
        logger.warning(f"[TERMII] SMS failed ({status_code}): {error}")
        return {'status': 'failed', 'error': str(error), 'provider_ref': ref}

    if provider == 'africastalking':
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
