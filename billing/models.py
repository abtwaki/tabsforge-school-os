"""Billing / subscription models for TabsForge School OS."""
from django.db import models

from core.models import TenantModel
from schools.models import School


class Subscription(TenantModel):
    """A school's subscription record."""
    class Status(models.TextChoices):
        TRIAL = 'trial', 'Trial'
        ACTIVE = 'active', 'Active'
        PAST_DUE = 'past_due', 'Past Due'
        CANCELLED = 'cancelled', 'Cancelled'
        SUSPENDED = 'suspended', 'Suspended'

    class Providers(models.TextChoices):
        PAYSTACK = 'paystack', 'Paystack'
        FLUTTERWAVE = 'flutterwave', 'Flutterwave'
        MANUAL = 'manual', 'Manual'

    school = models.OneToOneField(
        School,
        on_delete=models.CASCADE,
        related_name='subscription',
    )
    tier = models.CharField(
        max_length=20,
        choices=School.Tiers.choices,
        default=School.Tiers.SPROUT,
    )
    billing_cycle = models.CharField(
        max_length=20,
        choices=[('monthly', 'Monthly'), ('termly', 'Termly'), ('annual', 'Annual')],
        default='termly',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='NGN')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIAL,
    )
    provider = models.CharField(
        max_length=20,
        choices=Providers.choices,
        default=Providers.MANUAL,
    )
    provider_ref = models.CharField(max_length=255, blank=True)
    starts_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.school.name} — {self.tier} ({self.status})"
