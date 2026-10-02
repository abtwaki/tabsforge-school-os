"""Transport management models (Summit tier)."""
from django.db import models

from core.models import TenantModel


class Route(TenantModel):
    name = models.CharField(max_length=100)
    start_location = models.CharField(max_length=255)
    end_location = models.CharField(max_length=255)
    stops = models.JSONField(default=list, blank=True)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['name']
        unique_together = [['school', 'name']]

    def __str__(self):
        return self.name


class Vehicle(TenantModel):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        MAINTENANCE = 'maintenance', 'Maintenance'
        INACTIVE = 'inactive', 'Inactive'

    registration_number = models.CharField(max_length=50, db_index=True)
    make = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        unique_together = [['school', 'registration_number']]
        ordering = ['registration_number']

    def __str__(self):
        return f"{self.registration_number} - {self.make} {self.model}"


class VehicleAssignment(TenantModel):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='assignments')
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='assignments')
    driver_name = models.CharField(max_length=100, blank=True)
    driver_phone = models.CharField(max_length=30, blank=True)
    effective_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-effective_date']

    def __str__(self):
        return f"{self.vehicle} on {self.route}"
