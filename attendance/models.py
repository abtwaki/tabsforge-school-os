"""Student attendance models."""
from django.db import models

from accounts.models import User
from core.models import TenantModel


class Attendance(TenantModel):
    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        ABSENT = 'absent', 'Absent'
        LATE = 'late', 'Late'
        EXCUSED = 'excused', 'Excused'

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='attendances')
    school_class = models.ForeignKey('academics.Class', on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    marked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marked_attendances',
    )
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-date', 'student__last_name']
        unique_together = [['school', 'student', 'school_class', 'date']]
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendance Records'

    def __str__(self):
        return f"{self.student} - {self.date} - {self.get_status_display()}"
