"""Notification delivery helpers.

Email is sent through Django's configured email backend.
SMS is dispatched through a configurable stub/provider interface.
"""
from django.conf import settings
from django.core.mail import send_mail

from .models import EmailMessage, SMSMessage
from .providers import send_sms as sms_provider_send


def send_email_message(email_message: EmailMessage):
    """Send an EmailMessage using Django's email backend."""
    if not settings.EMAIL_HOST and settings.EMAIL_BACKEND != 'django.core.mail.backends.console.EmailBackend':
        email_message.status = EmailMessage.Status.FAILED
        email_message.error_message = 'Email backend not configured.'
        email_message.save(update_fields=['status', 'error_message'])
        return

    try:
        send_mail(
            subject=email_message.subject,
            message=email_message.body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_message.recipient],
            fail_silently=False,
        )
        email_message.status = EmailMessage.Status.SENT
        email_message.save(update_fields=['status'])
    except Exception as exc:
        email_message.status = EmailMessage.Status.FAILED
        email_message.error_message = str(exc)
        email_message.save(update_fields=['status', 'error_message'])


def queue_email(school, recipient, subject, body):
    """Create an EmailMessage record and attempt to send it."""
    email = EmailMessage.objects.create(
        school=school,
        recipient=recipient,
        subject=subject,
        body=body,
        status=EmailMessage.Status.PENDING,
    )
    send_email_message(email)
    return email


def queue_sms(school, recipient, message):
    """Create an SMSMessage record and attempt to send it."""
    sms = SMSMessage.objects.create(
        school=school,
        recipient=recipient,
        message=message,
        status=SMSMessage.Status.PENDING,
    )
    result = sms_provider_send(sms)
    if result.get('status') == 'sent':
        sms.status = SMSMessage.Status.SENT
        sms.provider_ref = result.get('provider_ref', '')
        sms.save(update_fields=['status', 'provider_ref'])
    else:
        sms.status = SMSMessage.Status.FAILED
        sms.error_message = result.get('error', 'Provider failed')
        sms.save(update_fields=['status', 'error_message'])
    return sms
