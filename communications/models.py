"""Communications models."""
from django.db import models

from accounts.models import User
from core.models import TenantModel


class Announcement(TenantModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='announcements',
        help_text='Optional school tenant; null for platform-wide announcements.',
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcements')
    target_roles = models.JSONField(default=list, blank=True, help_text='Roles this announcement targets.')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    publish_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Notice(TenantModel):
    class Priorities(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

    title = models.CharField(max_length=255)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notices')
    priority = models.CharField(max_length=10, choices=Priorities.choices, default=Priorities.MEDIUM)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
