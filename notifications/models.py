"""Notification/message log models with stub providers."""
from django.db import models

from accounts.models import User
from core.models import TenantModel, TimestampModel
from schools.models import School


class EmailMessage(TenantModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider_ref = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Email to {self.recipient}: {self.subject}"


class SMSMessage(TenantModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    recipient = models.CharField(max_length=30)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider_ref = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"SMS to {self.recipient}"


class InAppNotification(TimestampModel):
    """An in-app notification sent to a specific user."""

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='inapp_notifications',
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_notifications',
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='inapp_notifications',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'In-app Notification'
        verbose_name_plural = 'In-app Notifications'

    def __str__(self):
        return f"Notification for {self.recipient}: {self.title}"
