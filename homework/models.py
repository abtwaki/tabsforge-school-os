"""Homework assignments, submissions, and live lesson scheduling."""
from django.db import models

from core.models import TenantModel


class Assignment(TenantModel):
    """A homework or classwork assignment set by a teacher."""

    class Types(models.TextChoices):
        HOMEWORK = 'homework', 'Homework'
        CLASSWORK = 'classwork', 'Classwork'
        PROJECT = 'project', 'Project'
        ESSAY = 'essay', 'Essay'
        TEST = 'test', 'Test'

    school_class = models.ForeignKey(
        'academics.Class', on_delete=models.CASCADE, related_name='assignments',
    )
    subject = models.ForeignKey(
        'academics.Subject', on_delete=models.CASCADE, related_name='assignments',
    )
    teacher = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, related_name='set_assignments',
    )
    term = models.ForeignKey(
        'schools.Term', on_delete=models.CASCADE, related_name='assignments',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=Types.choices, default=Types.HOMEWORK)
    due_date = models.DateField()
    max_points = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    attachment = models.FileField(
        upload_to='homework/assignments/', blank=True, null=True,
    )
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['due_date', 'title']
        verbose_name = 'Assignment'

    def __str__(self):
        return f"{self.title} – {self.school_class} ({self.subject})"


class Submission(TenantModel):
    """A student's response to an assignment."""

    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        LATE = 'late', 'Late'
        GRADED = 'graded', 'Graded'
        RETURNED = 'returned', 'Returned'

    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name='submissions',
    )
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='submissions',
    )
    content = models.TextField(blank=True)
    file = models.FileField(
        upload_to='homework/submissions/', blank=True, null=True,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SUBMITTED,
    )
    score = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
    )
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='graded_submissions',
    )

    class Meta:
        unique_together = [['school', 'assignment', 'student']]
        ordering = ['-submitted_at']
        verbose_name = 'Submission'

    def __str__(self):
        return f"{self.student} → {self.assignment} ({self.status})"


class LiveLesson(TenantModel):
    """A scheduled live/video lesson linked to a Jitsi Meet room."""

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        LIVE = 'live', 'Live Now'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    school_class = models.ForeignKey(
        'academics.Class', on_delete=models.CASCADE, related_name='live_lessons',
    )
    subject = models.ForeignKey(
        'academics.Subject', on_delete=models.CASCADE, related_name='live_lessons',
    )
    teacher = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, related_name='hosted_lessons',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=45)
    jitsi_room_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SCHEDULED,
    )

    class Meta:
        ordering = ['scheduled_at']
        verbose_name = 'Live Lesson'

    def save(self, *args, **kwargs):
        if not self.jitsi_room_name:
            import uuid
            self.jitsi_room_name = f"tabsforge-{self.school_id}-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    @property
    def jitsi_url(self):
        return f"https://meet.jit.si/{self.jitsi_room_name}"

    def __str__(self):
        return f"{self.title} – {self.school_class} ({self.scheduled_at:%Y-%m-%d %H:%M})"
