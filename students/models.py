"""Student and guardian models."""
from django.db import models

from accounts.models import User
from core.models import TenantModel


class Student(TenantModel):
    class Genders(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        OTHER = 'other', 'Other'

    class Religions(models.TextChoices):
        CHRISTIANITY = 'christianity', 'Christianity'
        ISLAM = 'islam', 'Islam'
        TRADITIONAL = 'traditional', 'Traditional'
        OTHER = 'other', 'Other'

    class BloodGroups(models.TextChoices):
        O_POS = 'O+', 'O+'
        O_NEG = 'O-', 'O-'
        A_POS = 'A+', 'A+'
        A_NEG = 'A-', 'A-'
        B_POS = 'B+', 'B+'
        B_NEG = 'B-', 'B-'
        AB_POS = 'AB+', 'AB+'
        AB_NEG = 'AB-', 'AB-'

    class Genotypes(models.TextChoices):
        AA = 'AA', 'AA'
        AS = 'AS', 'AS'
        SS = 'SS', 'SS'
        AC = 'AC', 'AC'
        SC = 'SC', 'SC'

    admission_number = models.CharField(max_length=50, db_index=True)
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': User.Roles.STUDENT},
        related_name='student_profile',
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Genders.choices, blank=True)
    address = models.TextField(blank=True)
    enrollment_date = models.DateField(auto_now_add=True)

    # Nigerian biodata — required by schools for WAEC registration, health
    # records, and state/LGA reporting.
    nationality = models.CharField(max_length=60, blank=True, default='Nigerian')
    state_of_origin = models.CharField(max_length=60, blank=True)
    lga = models.CharField('Local Government Area', max_length=100, blank=True)
    religion = models.CharField(max_length=20, choices=Religions.choices, blank=True)
    nin = models.CharField('National Identification Number', max_length=11, blank=True)
    blood_group = models.CharField(max_length=5, choices=BloodGroups.choices, blank=True)
    genotype = models.CharField(max_length=5, choices=Genotypes.choices, blank=True)
    medical_conditions = models.TextField(
        blank=True,
        help_text='Allergies, chronic conditions or medications staff should know about.',
    )
    previous_school = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        unique_together = [['school', 'admission_number']]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.admission_number})"


class Guardian(TenantModel):
    class Relationships(models.TextChoices):
        FATHER = 'father', 'Father'
        MOTHER = 'mother', 'Mother'
        GUARDIAN = 'guardian', 'Guardian'
        OTHER = 'other', 'Other'

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': User.Roles.PARENT},
        related_name='guardian_profile',
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    relationship = models.CharField(max_length=20, choices=Relationships.choices, default=Relationships.GUARDIAN)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class GuardianStudent(TenantModel):
    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, related_name='wards')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='guardians')
    relationship = models.CharField(max_length=20, default='guardian')
    is_primary = models.BooleanField(default=False)

    class Meta:
        unique_together = [['school', 'guardian', 'student']]
        verbose_name = 'Guardian-Student Link'
        verbose_name_plural = 'Guardian-Student Links'

    def __str__(self):
        return f"{self.guardian} -> {self.student}"


class StudentEnrollment(TenantModel):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    section = models.ForeignKey('academics.Section', on_delete=models.CASCADE, related_name='enrollments')
    session = models.ForeignKey('schools.AcademicSession', on_delete=models.CASCADE, related_name='enrollments')
    term = models.ForeignKey('schools.Term', on_delete=models.CASCADE, related_name='enrollments')
    roll_number = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        unique_together = [['school', 'student', 'session', 'term']]
        ordering = ['-session__start_date', 'student__last_name']

    def __str__(self):
        return f"{self.student} enrolled in {self.section} ({self.term})"
