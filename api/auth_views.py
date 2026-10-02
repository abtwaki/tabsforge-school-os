"""Authentication-related API views."""
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from core.utils import audit
from . import serializers as ser


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Log in a user and return an auth token + user profile."""
    email = (request.data.get('email') or request.data.get('username') or '').strip().lower()
    password = request.data.get('password', '')
    if not email or not password:
        return Response(
            {'detail': 'Please provide both email and password.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response(
            {'detail': 'Invalid credentials.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if user.school and user.school.status != user.school.Status.ACTIVE:
        return Response(
            {'detail': 'Your school is awaiting approval or is currently suspended.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    token, _ = Token.objects.get_or_create(user=user)
    user_data = ser.UserSerializer(user).data
    user_data['branding'] = _school_branding(user.school)
    return Response({
        'token': token.key,
        'user': user_data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Invalidate the user's current token."""
    Token.objects.filter(user=request.user).delete()
    return Response({'detail': 'Logged out successfully.'})


def _school_branding(school):
    """Branding payload the portal applies for an active school."""
    if school is None:
        return None
    logo_url = school.logo.url if school.logo else None
    return {
        'id': school.id,
        'name': school.name,
        'subdomain': school.subdomain,
        'logo': logo_url,
        'primary_color': school.primary_color,
        'secondary_color': school.secondary_color,
        'tier': school.tier,
        'status': school.status,
        'modules': school.enabled_modules,
        'report_config': school.report_config,
    }


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """Get or update the authenticated user's profile + school branding."""
    if request.method == 'PATCH':
        allowed = {
            'first_name', 'last_name', 'phone', 'whatsapp_number',
            'notification_channel',
        }
        for field in allowed & request.data.keys():
            setattr(request.user, field, request.data[field])
        request.user.save(update_fields=list(allowed & request.data.keys()))
    data = ser.UserSerializer(request.user).data
    data['branding'] = _school_branding(request.user.school)
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Authenticated password change for every role (admin, staff, parent, student…)."""
    user = request.user
    if getattr(user, 'is_guest', False):
        return Response(
            {'detail': 'Guest demo accounts cannot change their password.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    current_password = request.data.get('current_password', '')
    new_password = request.data.get('new_password', '')
    if not current_password or not new_password:
        return Response(
            {'detail': 'Both current and new password are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not user.check_password(current_password):
        return Response(
            {'current_password': 'Current password is incorrect.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        return Response(
            {'new_password': list(exc.messages)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(new_password)
    user.save(update_fields=['password'])

    # Rotate the auth token so only the current session stays signed in.
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    audit(request, 'user.change_password', user)
    return Response({'detail': 'Password updated successfully.', 'token': token.key})


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Public health check endpoint."""
    return Response({'status': 'ok'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_tutorial(request):
    """Mark the current user's tutorial as completed."""
    request.user.tutorial_completed = True
    request.user.save(update_fields=['tutorial_completed'])
    return Response({'detail': 'Tutorial marked as completed.'})
