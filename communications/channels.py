"""
Notification channel provider interface (Part 2).

Architecture: swappable provider pattern identical to payment gateways.
Providers: EmailProvider (default), WhatsAppProvider (WhatsApp Business Cloud API).
The dispatcher reads each user's preferred channel and routes accordingly.
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

try:
    import requests
    _requests_available = True
except ImportError:
    _requests_available = False

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


# ── Abstract base ────────────────────────────────────────────────────────────

class BaseChannelProvider(ABC):
    """Common interface every notification channel must implement."""

    @abstractmethod
    def send_otp(self, recipient: str, code: str, purpose: str) -> bool:
        """Send a one-time code. recipient is email or phone number."""

    @abstractmethod
    def send_notification(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        """Send a general notification."""

    @abstractmethod
    def send_message(self, recipient: str, message: str) -> bool:
        """Send a plain message (e.g. fee reminder, alert)."""


# ── Email provider ───────────────────────────────────────────────────────────

class EmailProvider(BaseChannelProvider):
    def send_otp(self, recipient: str, code: str, purpose: str) -> bool:
        subject_map = {
            'login': 'Your TabsForge Login Code',
            'password_reset': 'Reset Your TabsForge Password',
            'registration': 'Complete Your TabsForge Registration',
        }
        subject = subject_map.get(purpose, 'Your TabsForge Verification Code')
        body = (
            f"Your verification code is: {code}\n\n"
            f"This code expires in 10 minutes. Do not share it with anyone.\n\n"
            f"If you did not request this, please ignore this message.\n\n"
            f"-- TabsForge School OS"
        )
        try:
            send_mail(
                subject, body,
                settings.DEFAULT_FROM_EMAIL, [recipient],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error("EmailProvider.send_otp failed: %s", e)
            return False

    def send_notification(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
            return True
        except Exception as e:
            logger.error("EmailProvider.send_notification failed: %s", e)
            return False

    def send_message(self, recipient: str, message: str) -> bool:
        return self.send_notification(recipient, 'TabsForge Notification', message)


# ── WhatsApp Business Cloud API provider ─────────────────────────────────────

class WhatsAppProvider(BaseChannelProvider):
    """
    WhatsApp Business Cloud API (Meta).

    Required settings (set via environment / .env):
        WHATSAPP_TOKEN       — your permanent access token
        WHATSAPP_PHONE_ID    — Phone Number ID from Meta Business Manager
        WHATSAPP_VERSION     — API version, default 'v20.0'

    To obtain these:
    1. Create/verify a Meta Business account at business.facebook.com
    2. Add WhatsApp to your app at developers.facebook.com
    3. Go to WhatsApp > Getting Started > copy Phone Number ID and temp token
    4. Generate a permanent token via System Users
    """

    BASE = 'https://graph.facebook.com/{version}/{phone_id}/messages'

    def __init__(self):
        self.token = getattr(settings, 'WHATSAPP_TOKEN', os.environ.get('WHATSAPP_TOKEN', ''))
        self.phone_id = getattr(settings, 'WHATSAPP_PHONE_ID', os.environ.get('WHATSAPP_PHONE_ID', ''))
        self.version = getattr(settings, 'WHATSAPP_VERSION', 'v20.0')

    @property
    def url(self):
        return self.BASE.format(version=self.version, phone_id=self.phone_id)

    @property
    def headers(self):
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }

    def _send(self, to: str, payload: dict) -> bool:
        if not self.token or not self.phone_id:
            logger.warning("WhatsApp not configured (missing WHATSAPP_TOKEN/PHONE_ID). Logging as fallback.")
            logger.info("WA_FALLBACK→%s: %s", to, payload)
            return False
        if not _requests_available:
            logger.error("WhatsApp requires 'requests' package. Install: pip install requests")
            return False
        try:
            resp = requests.post(
                self.url,
                headers=self.headers,
                json={**payload, 'messaging_product': 'whatsapp', 'to': to},
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("WhatsAppProvider._send failed to %s: %s", to, e)
            return False

    def send_otp(self, recipient: str, code: str, purpose: str) -> bool:
        """Send OTP using a free-form text message (no template required during testing)."""
        purpose_text = {
            'login': 'log in to TabsForge',
            'password_reset': 'reset your TabsForge password',
            'registration': 'complete your TabsForge registration',
        }.get(purpose, 'verify your identity on TabsForge')
        msg = f"Your TabsForge code to {purpose_text} is: *{code}*\n\nExpires in 10 minutes. Do not share."
        return self._send(recipient, {'type': 'text', 'text': {'body': msg}})

    def send_notification(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        msg = f"*{subject}*\n\n{body}"
        return self._send(recipient, {'type': 'text', 'text': {'body': msg}})

    def send_message(self, recipient: str, message: str) -> bool:
        return self._send(recipient, {'type': 'text', 'text': {'body': message}})

    def send_template(self, recipient: str, template_name: str, params: list) -> bool:
        """Send a pre-approved WhatsApp message template."""
        return self._send(recipient, {
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': 'en_US'},
                'components': [{'type': 'body', 'parameters': [
                    {'type': 'text', 'text': p} for p in params
                ]}],
            },
        })


# ── Channel dispatcher ───────────────────────────────────────────────────────

_providers = {
    'email': EmailProvider,
    'whatsapp': WhatsAppProvider,
}


def get_provider(channel: str) -> BaseChannelProvider:
    cls = _providers.get(channel, EmailProvider)
    return cls()


def dispatch_otp(user, code: str, purpose: str) -> bool:
    """Send OTP via the user's preferred channel."""
    channel = getattr(user, 'notification_channel', 'email')
    if channel == 'whatsapp' and user.whatsapp_number:
        recipient = user.whatsapp_number
    else:
        recipient = user.email
        channel = 'email'
    return get_provider(channel).send_otp(recipient, code, purpose)


def dispatch_notification(user, subject: str, body: str, **kwargs) -> bool:
    """Send notification via the user's preferred channel."""
    channel = getattr(user, 'notification_channel', 'email')
    if channel == 'whatsapp' and user.whatsapp_number:
        recipient = user.whatsapp_number
    else:
        recipient = user.email
        channel = 'email'
    return get_provider(channel).send_notification(recipient, subject, body, **kwargs)


def dispatch_to_all(users, subject: str, body: str):
    """Send a notification to a list of users, each on their preferred channel."""
    results = []
    for user in users:
        ok = dispatch_notification(user, subject, body)
        results.append((user.id, ok))
    return results


# ── WhatsApp Admission Intake Bot ────────────────────────────────────────────

class AdmissionBotSession:
    """
    In-memory/cache state machine for WhatsApp-based admission intake (Part 2).
    Each sender phone number has a session tracking which step they're on.
    """
    STEPS = [
        ('student_first_name', "Welcome to TabsForge Admissions!\n\nPlease enter the *student's first name*:"),
        ('student_last_name', "Thank you! Please enter the *student's last name*:"),
        ('date_of_birth', "Enter the *date of birth* (YYYY-MM-DD, e.g. 2015-03-22):"),
        ('gender', "Enter *gender* (M or F):"),
        ('applying_for_class', "Which *class* is the student applying for? (e.g. Primary 1, JSS 1):"),
        ('guardian_name', "Enter the *parent/guardian full name*:"),
        ('guardian_phone', "Enter the *guardian's phone number*:"),
        ('guardian_email', "Enter the *guardian's email address* (or type NONE):"),
        ('address', "Enter the *student's home address*:"),
        ('previous_school', "Enter the *previous school name* (or type NONE):"),
    ]
    DONE_MSG = (
        "Thank you! Your admission application has been submitted.\n\n"
        "You will receive a confirmation shortly. "
        "The school admin will review your application and contact you.\n\n"
        "Ref: {ref}"
    )

    def __init__(self):
        # In production: use Django cache or Redis keyed by phone number
        # Here we use a module-level dict (sufficient for single-process demos)
        self._sessions = {}

    def get_step(self, phone: str) -> int:
        return self._sessions.get(phone, {}).get('step', 0)

    def get_data(self, phone: str) -> dict:
        return self._sessions.get(phone, {}).get('data', {})

    def reset(self, phone: str):
        self._sessions.pop(phone, None)

    def process_message(self, phone: str, text: str, school_subdomain: str) -> str:
        """Process incoming WhatsApp message and return reply. Returns None when done."""
        text = text.strip()
        session = self._sessions.setdefault(phone, {'step': 0, 'data': {}})

        # Allow restart
        if text.lower() in ('start', 'apply', 'admission', 'hi', 'hello'):
            session['step'] = 0
            session['data'] = {}

        step_idx = session['step']
        if step_idx >= len(self.STEPS):
            return "Your application is already submitted. Type START to begin a new one."

        key, prompt = self.STEPS[step_idx]

        if step_idx == 0:
            # First message — show first prompt
            session['step'] = 1
            return prompt

        # Validate and store answer to previous step
        prev_key, _ = self.STEPS[step_idx - 1]
        val = text

        # Gender normalise
        if prev_key == 'gender':
            val = 'M' if text.upper() in ('M', 'MALE', 'BOY') else 'F'

        # NONE normalise
        if text.upper() in ('NONE', 'NIL', 'N/A', '-') and prev_key in ('guardian_email', 'previous_school'):
            val = ''

        session['data'][prev_key] = val
        session['step'] += 1

        if session['step'] <= len(self.STEPS):
            _, next_prompt = self.STEPS[session['step'] - 1]
            return next_prompt

        # All steps done — create application
        data = session['data']
        try:
            from schools.models import School
            from admissions.models import Application, AdmissionConfig
            school = School.objects.get(subdomain=school_subdomain)
            config = AdmissionConfig.objects.filter(school=school).first()
            session_obj = school.academic_sessions.filter(is_current=True).first()
            app = Application.objects.create(
                school=school,
                first_name=data.get('student_first_name', ''),
                last_name=data.get('student_last_name', ''),
                date_of_birth=data.get('date_of_birth') or '2010-01-01',
                gender=data.get('gender', 'M'),
                address=data.get('address', ''),
                applying_for_class=data.get('applying_for_class', ''),
                session=session_obj,
                guardian_name=data.get('guardian_name', ''),
                guardian_relationship='parent',
                guardian_phone=data.get('guardian_phone', phone),
                guardian_email=data.get('guardian_email', ''),
                previous_school=data.get('previous_school', ''),
                intake_channel='whatsapp',
            )
            self.reset(phone)
            return self.DONE_MSG.format(ref=f"TF-{app.id:06d}")
        except Exception as e:
            logger.error("AdmissionBot create_application error: %s", e)
            self.reset(phone)
            return "There was an error submitting your application. Please contact the school directly."


# Singleton bot session manager
_admission_bot = AdmissionBotSession()


def get_admission_bot() -> AdmissionBotSession:
    return _admission_bot
