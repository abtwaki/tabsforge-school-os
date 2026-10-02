"""Core shared models and mixins."""
from django.db import models


class TimestampModel(models.Model):
    """Abstract base adding created/updated timestamps and soft-delete."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Soft-delete: archived records keep their relationships intact so linked
    # records still work and the record can be restored later.
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class TenantModel(TimestampModel):
    """Abstract base for every model scoped to a school."""
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='%(class)ss',
        help_text='School tenant this record belongs to.',
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['school', 'created_at']),
        ]


class AuditLog(models.Model):
    """Append-only record of sensitive actions (who did what, when, where).

    ``school`` is nullable because platform-level actions (suspend a school,
    create a school admin) may not belong to a single tenant.
    """
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        null=True, blank=True, related_name='audit_logs',
    )
    actor = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_events',
    )
    # Snapshots keep the log meaningful after the actor/object is gone.
    actor_email = models.CharField(max_length=200, blank=True)
    actor_role = models.CharField(max_length=30, blank=True)
    action = models.CharField(max_length=60, db_index=True)
    object_type = models.CharField(max_length=80, blank=True, db_index=True)
    object_id = models.CharField(max_length=40, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'created_at']),
            models.Index(fields=['object_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.actor_email or '?'} {self.action} {self.object_type}#{self.object_id}"
