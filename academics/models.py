"""Academic structure models."""
from django.db import models

from accounts.models import User
from core.models import TenantModel


class Class(TenantModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Class'
        verbose_name_plural = 'Classes'
        unique_together = [['school', 'name']]

    def __str__(self):
        return self.name


class Section(TenantModel):
    school_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=50)
    room = models.CharField(max_length=50, blank=True)
    capacity = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['school_class', 'name']
        verbose_name = 'Section'
        verbose_name_plural = 'Sections'
        unique_together = [['school', 'school_class', 'name']]

    def __str__(self):
        return f"{self.school_class} - {self.name}"


class Subject(TenantModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        unique_together = [['school', 'code']]

    def __str__(self):
        return self.name


class ClassSubject(TenantModel):
    school_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='class_subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='class_subjects')
    teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': User.Roles.STAFF},
        related_name='assigned_class_subjects',
    )

    class Meta:
        unique_together = [['school', 'school_class', 'subject']]
        verbose_name = 'Class Subject'
        verbose_name_plural = 'Class Subjects'

    def __str__(self):
        return f"{self.school_class} - {self.subject}"


class Timetable(TenantModel):
    DAYS = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ]

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='timetables')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='timetables')
    teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': User.Roles.STAFF},
        related_name='timetables',
    )
    day = models.CharField(max_length=10, choices=DAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['day', 'start_time']

    def __str__(self):
        return f"{self.section} {self.day} {self.start_time}-{self.end_time}"
