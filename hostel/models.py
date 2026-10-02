"""Hostel management models (Summit tier)."""
from django.db import models

from core.models import TenantModel


class Hostel(TenantModel):
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    warden_name = models.CharField(max_length=100, blank=True)
    warden_phone = models.CharField(max_length=30, blank=True)

    class Meta:
        unique_together = [['school', 'name']]
        ordering = ['name']

    def __str__(self):
        return self.name


class Room(TenantModel):
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField(default=1)
    occupied = models.PositiveIntegerField(default=0)
    amenities = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [['school', 'hostel', 'room_number']]
        ordering = ['room_number']

    @property
    def vacancies(self):
        return max(0, self.capacity - self.occupied)

    def __str__(self):
        return f"{self.hostel.name} - {self.room_number}"


class HostelAllocation(TenantModel):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        CHECKED_OUT = 'checked_out', 'Checked Out'

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='allocations')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='hostel_allocations')
    check_in = models.DateField()
    check_out = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        unique_together = [['school', 'room', 'student', 'check_in']]
        ordering = ['-check_in']

    def __str__(self):
        return f"{self.student} in {self.room}"
