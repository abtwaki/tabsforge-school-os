"""Custom User model for TabsForge School OS."""
import secrets
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractUser):
    class Roles(models.TextChoices):
        SUPER_ADMIN = 'super_admin', 'Super Admin'
        GROUP_OWNER = 'group_owner', 'Group/Proprietor Owner'
        SCHOOL_ADMIN = 'school_admin', 'School Admin'
        PRINCIPAL = 'principal', 'Principal / Head'
        VICE_PRINCIPAL = 'vice_principal', 'Vice Principal'
        ADMISSIONS_OFFICER = 'admissions_officer', 'Admissions Officer'
        TEACHER = 'teacher', 'Teacher'
        FORM_TEACHER = 'form_teacher', 'Form Teacher'
        EXAM_OFFICER = 'exam_officer', 'Exam Officer'
        HR_ADMIN = 'hr_admin', 'HR / Staff Admin'
        LIBRARIAN = 'librarian', 'Librarian'
        STAFF = 'staff', 'Staff'
        ACCOUNTANT = 'accountant', 'Accountant'
        PARENT = 'parent', 'Parent'
        STUDENT = 'student', 'Student'
        GUEST = 'guest', 'Guest/Demo'

    # Roles that count as teaching/academic staff for classroom operations.
    TEACHING_ROLES = {
        Roles.TEACHER, Roles.FORM_TEACHER, Roles.STAFF,
        Roles.PRINCIPAL, Roles.VICE_PRINCIPAL,
    }
    # Roles that can perform school-management write actions.
    ADMIN_LIKE_ROLES = {
        Roles.SCHOOL_ADMIN, Roles.PRINCIPAL, Roles.VICE_PRINCIPAL,
        Roles.ADMISSIONS_OFFICER, Roles.HR_ADMIN,
    }
    # Roles that can enter grades / manage assessments and results.
    GRADING_ROLES = {
        Roles.TEACHER, Roles.FORM_TEACHER, Roles.EXAM_OFFICER,
        Roles.PRINCIPAL, Roles.VICE_PRINCIPAL, Roles.SCHOOL_ADMIN, Roles.STAFF,
    }

    class NotifyChannel(models.TextChoices):
        EMAIL = 'email', 'Email'
        WHATSAPP = 'whatsapp', 'WhatsApp'

    username = None
    email = models.EmailField('email address', unique=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.STAFF)
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text='School this user belongs to. Null for global super admins.',
    )
    # Part 4: Group ownership
    school_group = models.ForeignKey(
        'schools.SchoolGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='group_users',
        help_text='Group this user owns/belongs to (Group Owner role).',
    )
    phone = models.CharField(max_length=30, blank=True)
    whatsapp_number = models.CharField(
        max_length=30, blank=True,
        help_text='WhatsApp number in E.164 format, e.g. +2348012345678',
    )
    notification_channel = models.CharField(
        max_length=10, choices=NotifyChannel.choices, default=NotifyChannel.EMAIL,
        help_text='Preferred channel for notifications and auth codes.',
    )
    is_support = models.BooleanField(default=False, help_text='Support flag for helpdesk staff.')
    # TOTP (Google Authenticator / any RFC 6238 app)
    totp_secret = models.CharField(max_length=64, blank=True)
    totp_enabled = models.BooleanField(default=False)
    tutorial_completed = models.BooleanField(
        default=False,
        help_text='True once the user has completed or dismissed the onboarding tutorial.',
    )
    # Part 8: read-only guest flag
    is_guest = models.BooleanField(default=False, help_text='True for sandbox/demo guest accounts.')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class OTPVerification(models.Model):
    """One-time password for login verification / password reset (Part 2)."""
    class Purpose(models.TextChoices):
        LOGIN = 'login', 'Login OTP'
        PASSWORD_RESET = 'password_reset', 'Password Reset'
        EMAIL_VERIFY = 'email_verify', 'Email Verification'
        REGISTRATION = 'registration', 'Registration Link'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=64)
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.LOGIN)
    channel = models.CharField(max_length=10, choices=User.NotifyChannel.choices, default=User.NotifyChannel.EMAIL)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    @classmethod
    def create_for_user(cls, user, purpose=Purpose.LOGIN, ttl_minutes=10):
        code = secrets.token_hex(3).upper()  # 6-char hex OTP
        exp = timezone.now() + timezone.timedelta(minutes=ttl_minutes)
        return cls.objects.create(
            user=user, code=code, purpose=purpose,
            channel=user.notification_channel, expires_at=exp,
        )

    @property
    def is_valid(self):
        return not self.used and self.expires_at > timezone.now() and self.attempts < 5
