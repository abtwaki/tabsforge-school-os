"""Signals for communications."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User
from notifications.utils import queue_email

from .models import Announcement


@receiver(post_save, sender=Announcement)
def broadcast_announcement(sender, instance, created, **kwargs):
    """Email the announcement to users in the target roles when published."""
    if not created or instance.status != Announcement.Status.PUBLISHED:
        return
    if instance.school is None:
        # Platform-wide announcements are handled through in-app notifications only.
        return

    target_roles = instance.target_roles or []
    if not target_roles:
        target_roles = [User.Roles.STAFF, User.Roles.PARENT, User.Roles.STUDENT]

    recipients = User.objects.filter(
        school=instance.school,
        role__in=target_roles,
        is_active=True,
    ).exclude(email='').values_list('email', flat=True)

    for email in recipients:
        queue_email(
            school=instance.school,
            recipient=email,
            subject=f'Announcement: {instance.title}',
            body=instance.content,
        )
