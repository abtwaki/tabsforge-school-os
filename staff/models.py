"""Staff profile and assignment models."""
from django.db import models

from accounts.models import User
from core.models import TenantModel


class Staff(TenantModel):
    class EmploymentTypes(models.TextChoices):
        FULL_TIME = 'full_time', 'Full Time'
        PART_TIME = 'part_time', 'Part Time'
        CONTRACT = 'contract', 'Contract'

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='staff_profile',
        limit_choices_to={'role': User.Roles.STAFF},
    )
    employee_id = models.CharField(max_length=50, db_index=True)
    designation = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    employment_type = models.CharField(
        max_length=20, choices=EmploymentTypes.choices, default=EmploymentTypes.FULL_TIME
    )
    date_joined = models.DateField(null=True, blank=True)
    assigned_classes = models.ManyToManyField('academics.Class', blank=True, related_name='assigned_staff')
    assigned_subjects = models.ManyToManyField('academics.Subject', blank=True, related_name='assigned_staff')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['employee_id']
        verbose_name = 'Staff Member'
        verbose_name_plural = 'Staff'
        unique_together = [['school', 'employee_id']]

    def __str__(self):
        return f"{self.employee_id} - {self.user.full_name}"
