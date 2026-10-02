"""Schools and academic calendar models."""
from django.db import models

from core.models import TimestampModel


class SchoolGroup(TimestampModel):
    """A Group/Proprietor account that owns multiple branch schools (Part 4)."""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='groups/logos/', blank=True, null=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    billing_mode = models.CharField(
        max_length=20,
        choices=[('consolidated', 'Consolidated'), ('per_branch', 'Per Branch')],
        default='per_branch',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'School Group'

    def __str__(self):
        return self.name


class School(TimestampModel):
    class Tiers(models.TextChoices):
        SPROUT = 'Sprout', 'Sprout'
        ROOTS = 'Roots', 'Roots'
        BLOOM = 'Bloom', 'Bloom'
        SUMMIT = 'Summit', 'Summit'

    class Status(models.TextChoices):
        ONBOARDING = 'onboarding', 'Onboarding'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'

    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='schools/logos/', blank=True, null=True)
    address = models.TextField(blank=True)
    contact_info = models.JSONField(default=dict, blank=True)
    tier = models.CharField(max_length=20, choices=Tiers.choices, default=Tiers.SPROUT)
    subdomain = models.SlugField(unique=True, db_index=True, help_text='Unique subdomain for the school.')
    custom_domain = models.CharField(max_length=255, blank=True, db_index=True)
    primary_color = models.CharField(max_length=7, default='#3B82F6')
    secondary_color = models.CharField(max_length=7, default='#10B981')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ONBOARDING)
    # Module access control: empty list = all modules allowed by tier.
    # Otherwise a list of module path keys (e.g. 'library', 'transport').
    enabled_modules = models.JSONField(default=list, blank=True)
    # School's own report-card template (PDF/DOCX/XLSX) and adopted layout config.
    report_template = models.FileField(
        upload_to='schools/report_templates/', blank=True, null=True,
    )
    report_config = models.JSONField(default=dict, blank=True)
    # Internal review notes — platform admins only; never shown to the school.
    admin_notes = models.TextField(blank=True)
    # Modules the school asked for during onboarding that sit above its tier.
    requested_modules = models.JSONField(default=list, blank=True)
    # Part 4: multi-branch grouping
    group = models.ForeignKey(
        SchoolGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='branches',
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'School'
        verbose_name_plural = 'Schools'

    def __str__(self):
        return self.name


class DemoLead(TimestampModel):
    """A marketing lead generated from the 'Book a Free Demo' form."""
    school_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    student_count_range = models.CharField(max_length=30, blank=True)
    message = models.TextField(blank=True)
    contacted = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']


class AcademicSession(TimestampModel):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='academic_sessions')
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']
        unique_together = [['school', 'name']]
        verbose_name = 'Academic Session'
        verbose_name_plural = 'Academic Sessions'

    def __str__(self):
        return f"{self.name} ({self.school})"


class Term(TimestampModel):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='terms')
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='terms')
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['start_date']
        unique_together = [['school', 'session', 'name']]
        verbose_name = 'Term'
        verbose_name_plural = 'Terms'

    def __str__(self):
        return f"{self.name} - {self.session.name}"
