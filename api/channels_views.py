"""
Part 2 — WhatsApp & Email channel views.

Endpoints:
  POST /api/auth/send-otp/             — send login/reset OTP to user's preferred channel
  POST /api/auth/verify-otp/           — verify OTP, return token on success
  POST /api/auth/request-registration/ — send email-link invite to a new user
  POST /api/auth/complete-registration/— complete account setup from email link
  GET  /api/whatsapp/webhook/          — Meta webhook verification
  POST /api/whatsapp/webhook/          — receive WhatsApp messages (admission bot + notifications)
  PATCH /api/users/<pk>/channel-preference/ — update notification_channel + whatsapp_number
"""
import hashlib
import hmac
import json
import logging

from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from accounts.models import OTPVerification
from communications.channels import dispatch_otp, dispatch_notification, get_admission_bot

User = get_user_model()
logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def send_otp(request):
    """
    Send a login OTP to the user's preferred channel.
    Body: { "email": "...", "purpose": "login"|"password_reset" }
    """
    email = request.data.get('email', '').strip().lower()
    purpose = request.data.get('purpose', 'login')
    if not email:
        return Response({'detail': 'email required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Don't reveal whether the user exists
        return Response({'detail': 'If that account exists, a code has been sent.'})

    otp = OTPVerification.create_for_user(user, purpose=purpose)
    sent = dispatch_otp(user, otp.code, purpose)
    channel = user.notification_channel
    if channel == 'whatsapp' and user.whatsapp_number:
        destination_hint = f"WhatsApp ({user.whatsapp_number[:4]}...)"
    else:
        domain = user.email.split('@')[-1]
        destination_hint = f"email @{domain}"

    return Response({
        'detail': f'Verification code sent to your {destination_hint}.',
        'channel': channel,
        # Include otp.id so the client can reference it on verify
        'otp_id': otp.id,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    """
    Verify OTP and (for login purpose) return an auth token.
    Body: { "otp_id": 1, "code": "AB12CD" }
    """
    otp_id = request.data.get('otp_id')
    code = request.data.get('code', '').strip().upper()
    if not otp_id or not code:
        return Response({'detail': 'otp_id and code required'}, status=400)
    try:
        otp = OTPVerification.objects.get(id=otp_id)
    except OTPVerification.DoesNotExist:
        return Response({'detail': 'Invalid code.'}, status=400)

    otp.attempts += 1
    otp.save(update_fields=['attempts'])

    if not otp.is_valid:
        return Response({'detail': 'Code expired or already used.'}, status=400)
    if otp.code != code:
        return Response({'detail': 'Incorrect code.'}, status=400)

    otp.used = True
    otp.save(update_fields=['used'])
    user = otp.user

    if otp.purpose == OTPVerification.Purpose.LOGIN:
        token, _ = Token.objects.get_or_create(user=user)
        from api.auth_views import _user_response
        return Response({'token': token.key, 'user': _user_response(user)})
    elif otp.purpose == OTPVerification.Purpose.PASSWORD_RESET:
        # Return a short-lived reset token stored in OTP
        return Response({'reset_token': token_for_reset(user), 'detail': 'Code verified.'})
    return Response({'detail': 'Verified.'})


def token_for_reset(user):
    """Generate a password-reset token (simple HMAC — not persistent)."""
    import secrets
    return secrets.token_urlsafe(32)


# ── TOTP (Google Authenticator / RFC 6238) ──────────────────────────────────

def _totp(user):
    import pyotp
    return pyotp.TOTP(user.totp_secret)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def totp_setup(request):
    """Begin authenticator-app enrolment: returns a fresh secret + otpauth URL.
    The secret is stored but not active until /totp/enable/ verifies a code."""
    import pyotp
    from django.conf import settings
    user = request.user
    user.totp_secret = pyotp.random_base32()
    user.totp_enabled = False
    user.save(update_fields=['totp_secret', 'totp_enabled'])
    issuer = getattr(settings, 'APP_NAME', 'TabsForge')
    uri = _totp(user).provisioning_uri(name=user.email, issuer_name=issuer)
    return Response({'secret': user.totp_secret, 'otpauth_url': uri})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def totp_enable(request):
    """Confirm enrolment: { "code": "123456" } — code must match the pending secret."""
    code = (request.data.get('code') or '').strip()
    user = request.user
    if not user.totp_secret:
        return Response({'detail': 'Call /auth/totp/setup/ first.'}, status=400)
    if not code or not _totp(user).verify(code, valid_window=1):
        return Response({'detail': 'Incorrect code — check the time on your device and try again.'}, status=400)
    user.totp_enabled = True
    user.save(update_fields=['totp_enabled'])
    return Response({'detail': 'Authenticator app enabled.', 'totp_enabled': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def totp_disable(request):
    """Disable TOTP: { "code": "123456" } — requires a valid code first."""
    code = (request.data.get('code') or '').strip()
    user = request.user
    if not user.totp_enabled:
        return Response({'detail': 'Authenticator app is not enabled.'}, status=400)
    if not code or not _totp(user).verify(code, valid_window=1):
        return Response({'detail': 'Incorrect code.'}, status=400)
    user.totp_enabled = False
    user.totp_secret = ''
    user.save(update_fields=['totp_enabled', 'totp_secret'])
    return Response({'detail': 'Authenticator app removed.', 'totp_enabled': False})


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
    Complete a password reset in one step. Two proofs accepted:

    1. Email/WhatsApp OTP: { "otp_id": 1, "code": "AB12CD", "new_password": "..." }
    2. Authenticator app:  { "email": "...", "totp_code": "123456", "new_password": "..." }
       (only for accounts that enrolled a TOTP app while signed in)

    On success the user's sessions are invalidated (all auth tokens dropped).
    """
    new_password = request.data.get('new_password') or ''
    totp_code = (request.data.get('totp_code') or '').strip()

    if len(new_password) < 8:
        return Response({'detail': 'Password must be at least 8 characters.'}, status=400)

    # ── Path 2: TOTP code ────────────────────────────────────────────────
    if totp_code:
        email = (request.data.get('email') or '').strip().lower()
        user = User.objects.filter(email=email).first()
        # Generic error — don't reveal whether the account/TOTP exists
        if not user or not user.totp_enabled or not _totp(user).verify(totp_code, valid_window=1):
            return Response({'detail': 'Incorrect authenticator code.'}, status=400)
        user.set_password(new_password)
        user.save(update_fields=['password'])
        Token.objects.filter(user=user).delete()
        return Response({'detail': 'Password updated. Sign in with your new password.'})

    # ── Path 1: OTP ──────────────────────────────────────────────────────
    otp_id = request.data.get('otp_id')
    code = request.data.get('code', '').strip().upper()
    if not otp_id or not code:
        return Response({'detail': 'otp_id and code — or an authenticator code — are required.'}, status=400)
    try:
        otp = OTPVerification.objects.get(id=otp_id)
    except OTPVerification.DoesNotExist:
        return Response({'detail': 'Invalid code.'}, status=400)
    if otp.purpose != OTPVerification.Purpose.PASSWORD_RESET:
        return Response({'detail': 'Invalid reset request.'}, status=400)

    otp.attempts += 1
    otp.save(update_fields=['attempts'])
    if not otp.is_valid:
        return Response({'detail': 'Code expired, already used, or too many attempts — request a new one.'}, status=400)
    if otp.code != code:
        return Response({'detail': 'Incorrect code.'}, status=400)

    otp.used = True
    otp.save(update_fields=['used'])
    user = otp.user
    user.set_password(new_password)
    user.save(update_fields=['password'])
    # Invalidate existing sessions so a stolen token can't keep working.
    Token.objects.filter(user=user).delete()
    return Response({'detail': 'Password updated. Sign in with your new password.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def request_registration_link(request):
    """
    Send a secure email-link registration invite (Part 2).
    Body: { "email": "...", "name": "...", "school_id": ... }
    Used by school admins to invite parents/staff without them navigating the site cold.
    """
    from django.conf import settings
    import secrets
    email = request.data.get('email', '').strip().lower()
    name = request.data.get('name', '')
    school_id = request.data.get('school_id')
    role = request.data.get('role', 'parent')

    if not email:
        return Response({'detail': 'email required'}, status=400)

    # Create or fetch a placeholder user for the invite
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'first_name': name.split()[0] if name else '',
            'last_name': ' '.join(name.split()[1:]) if name and len(name.split()) > 1 else '',
            'role': role,
            'is_active': False,  # not active until they complete registration
        }
    )
    if school_id and not user.school_id:
        from schools.models import School
        try:
            user.school = School.objects.get(pk=school_id)
            user.save(update_fields=['school'])
        except School.DoesNotExist:
            pass

    # Create registration OTP (longer TTL for links)
    otp = OTPVerification.create_for_user(user, purpose=OTPVerification.Purpose.REGISTRATION, ttl_minutes=2880)

    base_url = getattr(settings, 'FRONTEND_URL', 'https://tabsforge.com')
    reg_link = f"{base_url}/register?token={otp.code}&uid={user.pk}"

    from communications.channels import EmailProvider
    EmailProvider().send_notification(
        email,
        'Complete Your TabsForge Account Setup',
        f"Hello {name or email},\n\n"
        f"You have been invited to join TabsForge School OS.\n\n"
        f"Click the link below to set your password and complete your account:\n\n"
        f"{reg_link}\n\n"
        f"This link expires in 48 hours.\n\n-- TabsForge School OS"
    )
    return Response({'detail': f'Registration link sent to {email}.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def complete_registration(request):
    """
    Complete account setup from email-link.
    Body: { "uid": 5, "token": "...", "password": "...", "first_name": "...", "last_name": "..." }
    """
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    uid = request.data.get('uid')
    token = request.data.get('token', '').strip()
    password = request.data.get('password', '')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')

    if not uid or not token or not password:
        return Response({'detail': 'uid, token, and password required.'}, status=400)
    try:
        user = User.objects.get(pk=uid)
        otp = OTPVerification.objects.filter(
            user=user, code=token,
            purpose=OTPVerification.Purpose.REGISTRATION,
            used=False,
        ).order_by('-created_at').first()
    except User.DoesNotExist:
        return Response({'detail': 'Invalid registration link.'}, status=400)

    if not otp or not otp.is_valid:
        return Response({'detail': 'This registration link has expired.'}, status=400)

    try:
        validate_password(password, user)
    except ValidationError as e:
        return Response({'detail': e.messages}, status=400)

    user.first_name = first_name or user.first_name
    user.last_name = last_name or user.last_name
    user.is_active = True
    user.set_password(password)
    user.save()
    otp.used = True
    otp.save(update_fields=['used'])

    auth_token, _ = Token.objects.get_or_create(user=user)
    from api.auth_views import _user_response
    return Response({'token': auth_token.key, 'user': _user_response(user)})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_channel_preference(request, pk=None):
    """
    Update notification_channel and whatsapp_number for a user.
    Body: { "notification_channel": "whatsapp", "whatsapp_number": "+2348012345678" }
    """
    target_user = request.user
    if pk and str(pk) != str(request.user.pk):
        if not (request.user.is_superuser or request.user.role == User.Roles.SUPER_ADMIN):
            return Response({'detail': 'Not permitted.'}, status=403)
        try:
            target_user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=404)

    channel = request.data.get('notification_channel')
    wa_number = request.data.get('whatsapp_number', '').strip()

    if channel and channel not in ('email', 'whatsapp'):
        return Response({'detail': 'channel must be email or whatsapp.'}, status=400)
    if channel:
        target_user.notification_channel = channel
    if wa_number:
        if not wa_number.startswith('+'):
            return Response({'detail': 'WhatsApp number must be in E.164 format: +2348012345678'}, status=400)
        target_user.whatsapp_number = wa_number
    target_user.save(update_fields=['notification_channel', 'whatsapp_number'])
    return Response({'detail': 'Channel preference updated.', 'notification_channel': target_user.notification_channel})


# ── WhatsApp Webhook (Meta Business API) ────────────────────────────────────

@csrf_exempt
def whatsapp_webhook(request):
    """Handles WhatsApp Business Cloud API webhook — verification + message processing."""
    from django.conf import settings
    VERIFY_TOKEN = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', 'tabsforge_verify_token')

    if request.method == 'GET':
        # Webhook verification challenge from Meta
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponse('Forbidden', status=403)

    if request.method == 'POST':
        # Verify webhook signature
        signature = request.headers.get('X-Hub-Signature-256', '')
        app_secret = getattr(settings, 'WHATSAPP_APP_SECRET', '')
        if app_secret:
            expected = 'sha256=' + hmac.new(
                app_secret.encode(), request.body, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return HttpResponse('Invalid signature', status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse('Bad JSON', status=400)

        try:
            _process_whatsapp_event(data)
        except Exception as e:
            logger.error("WhatsApp webhook processing error: %s", e)

        return HttpResponse('EVENT_RECEIVED')

    return HttpResponse('Method not allowed', status=405)


def _process_whatsapp_event(data: dict):
    """Process an inbound WhatsApp webhook event."""
    bot = get_admission_bot()
    for entry in data.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            messages = value.get('messages', [])
            metadata = value.get('metadata', {})
            phone_number_id = metadata.get('phone_number_id', '')

            for msg in messages:
                sender_phone = msg.get('from', '')
                msg_type = msg.get('type', '')

                if msg_type == 'text':
                    text = msg.get('text', {}).get('body', '')
                    # Determine which school this WA number belongs to (by WHATSAPP_PHONE_ID)
                    from django.conf import settings
                    school_subdomain = getattr(settings, 'WHATSAPP_DEFAULT_SCHOOL', 'modelschool')
                    reply = bot.process_message(sender_phone, text, school_subdomain)
                    if reply:
                        from communications.channels import WhatsAppProvider
                        WhatsAppProvider().send_message(sender_phone, reply)
