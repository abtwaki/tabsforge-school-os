"""Admissions models: application workflow and configurable admission numbering."""
from django.db import models, transaction
from datetime import date

from core.models import TenantModel


class AdmissionConfig(TenantModel):
    """Per-school configuration for admission number generation.

    Supports format like: {PREFIX}{SEP}{YEAR}{SEP}{SEQUENCE}
    Or a fully custom format string with {prefix}, {year}, {seq} placeholders.
    """
    prefix = models.CharField(max_length=20, default='ADM')
    include_year = models.BooleanField(default=True)
    year_format = models.CharField(
        max_length=10, default='%Y',
        help_text='strftime format for year part, e.g. %Y or %y',
    )
    separator = models.CharField(max_length=5, default='/')
    sequence_digits = models.PositiveSmallIntegerField(default=4)
    current_sequence = models.PositiveIntegerField(default=0)
    custom_format = models.CharField(
        max_length=200, blank=True,
        help_text='Optional override. Use {prefix}, {year}, {seq} placeholders. '
                  'Leave blank to use standard prefix/year/seq format.',
    )

    class Meta:
        verbose_name = 'Admission Config'
        verbose_name_plural = 'Admission Configs'
        unique_together = [['school']]

    def __str__(self):
        return f"Admission config for {self.school} (next: {self.preview()})"

    def preview(self):
        """Return what the next admission number will look like (without incrementing)."""
        return self._format(self.current_sequence + 1)

    def generate_next(self):
        """Atomically increment sequence and return the new admission number."""
        with transaction.atomic():
            config = AdmissionConfig.objects.select_for_update().get(pk=self.pk)
            config.current_sequence += 1
            config.save(update_fields=['current_sequence'])
            num = config._format(config.current_sequence)
        self.current_sequence = config.current_sequence
        return num

    def _format(self, seq):
        year_str = date.today().strftime(self.year_format)
        seq_str = str(seq).zfill(self.sequence_digits)
        if self.custom_format:
            return self.custom_format.format(
                prefix=self.prefix,
                year=year_str,
                seq=seq_str,
            )
        parts = [self.prefix]
        if self.include_year:
            parts.append(year_str)
        parts.append(seq_str)
        return self.separator.join(parts)


class Application(TenantModel):
    """A student admission application submitted to the school."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        UNDER_REVIEW = 'under_review', 'Under Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        WAITLISTED = 'waitlisted', 'Waitlisted'

    class Genders(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        OTHER = 'other', 'Other'

    # Applicant personal details
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=Genders.choices)
    address = models.TextField(blank=True)
    previous_school = models.CharField(max_length=255, blank=True)
    previous_class = models.CharField(max_length=100, blank=True)
    additional_info = models.TextField(blank=True)

    # Applying for
    applying_for_class = models.ForeignKey(
        'academics.Class', on_delete=models.SET_NULL, null=True,
        related_name='applications',
    )
    session = models.ForeignKey(
        'schools.AcademicSession', on_delete=models.CASCADE,
        related_name='applications',
    )

    # Guardian / parent contact
    guardian_name = models.CharField(max_length=200)
    guardian_relationship = models.CharField(max_length=50, default='guardian')
    guardian_phone = models.CharField(max_length=30)
    guardian_email = models.EmailField(blank=True)
    guardian_address = models.TextField(blank=True)

    # Document uploads
    passport_photo = models.ImageField(
        upload_to='admissions/photos/', blank=True, null=True,
    )
    birth_certificate = models.FileField(
        upload_to='admissions/docs/', blank=True, null=True,
    )
    previous_result = models.FileField(
        upload_to='admissions/docs/', blank=True, null=True,
    )
    other_document = models.FileField(
        upload_to='admissions/docs/', blank=True, null=True,
    )

    # Part 2: how the application was submitted
    intake_channel = models.CharField(
        max_length=20,
        choices=[('web', 'Web Form'), ('whatsapp', 'WhatsApp'), ('email_link', 'Email Link'), ('admin', 'Admin')],
        default='web',
    )

    # Review workflow
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING,
    )
    reviewed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_applications',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Set on approval
    generated_admission_number = models.CharField(max_length=50, blank=True)
    student = models.OneToOneField(
        'students.Student', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='application',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Application'
        verbose_name_plural = 'Applications'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.status}) – {self.school}"

    @property
    def applicant_full_name(self):
        return f"{self.first_name} {self.last_name}"
