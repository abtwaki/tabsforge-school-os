"""
Part 8 — Guest / Demo Access mode.

Endpoints:
  POST /api/auth/guest-token/   — issue a read-only guest token for the demo school
  GET  /api/auth/demo-creds/    — return documented demo credentials list

The guest token is a real DRF token belonging to the pre-created GUEST user.
All mutating viewset actions check request.user.is_guest and return 403.
"""
import logging

from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.permissions import IsSuperAdmin

User = get_user_model()
logger = logging.getLogger(__name__)

# Demo school subdomain — matches the seeded demo school
DEMO_SUBDOMAIN = 'model-school'


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def school_entry(request, subdomain=None):
    """Path-based unique school URL entry point.

    Stores the intended tenant subdomain in the session and redirects to
    the app login. Falls back to the model school if the subdomain is unknown.
    """
    if not subdomain:
        subdomain = DEMO_SUBDOMAIN
    request.session['tenant_subdomain'] = subdomain
    return redirect(f'/login?tenant={subdomain}')


@api_view(['POST'])
@permission_classes([AllowAny])
def guest_token(request):
    """
    Issue a sandboxed read-only token for the demo/model school.
    No credentials required — anyone can get a guest token.
    The guest user's is_guest=True flag restricts all write operations.
    """
    guest_user = _get_or_create_guest()
    token, _ = Token.objects.get_or_create(user=guest_user)
    return Response({
        'token': token.key,
        'role': 'guest',
        'school': DEMO_SUBDOMAIN,
        'message': (
            'You are in READ-ONLY demo mode. '
            'You can browse students, classes, reports, and the AI Suite, '
            'but cannot create, edit, or delete any data.'
        ),
    })


def _get_or_create_guest():
    """Retrieve or create the singleton guest user for the demo school."""
    from schools.models import School
    # Try exact subdomain match first, fallback to any active school with students
    demo_school = (
        School.objects.filter(subdomain=DEMO_SUBDOMAIN).first()
        or School.objects.filter(status='active').first()
        or School.objects.first()
    )

    guest, created = User.objects.get_or_create(
        email='guest@tabsforge.com',
        defaults={
            'first_name': 'Guest',
            'last_name': 'Visitor',
            'role': User.Roles.GUEST,
            'school': demo_school,
            'is_guest': True,
            'is_active': True,
        },
    )
    update_fields = []
    if not guest.has_usable_password():
        import secrets
        guest.set_password(secrets.token_hex(32))
        update_fields.append('password')
    if demo_school and not guest.school_id:
        guest.school = demo_school
        update_fields.append('school')
    if update_fields:
        guest.save(update_fields=update_fields)
    return guest


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def demo_credentials(request):
    """Return demo account identifiers to platform super administrators."""
    return Response({
        'demo_school': {
            'name': 'Model Demo School',
            'subdomain': DEMO_SUBDOMAIN,
            'url': 'https://tabsforge.com',
        },
        'credentials': [
            {
                'role': 'Platform Super Admin (TabsForge)',
                'email': 'abtwaki@tabsforge.com',
                'note': 'Full platform access — all schools, all settings',
            },
            {
                'role': 'School Admin',
                'email': 'admin@modelschool.tf',
                'note': 'Full Model School access',
            },
            {
                'role': 'Teacher / Staff',
                'email': 'teacher1@modelschool.tf',
                'note': 'Attendance, grades, homework',
            },
            {
                'role': 'Accountant / Bursar',
                'email': 'bursar@modelschool.tf',
                'note': 'Finance, invoices, payments',
            },
            {
                'role': 'Parent',
                'email': 'parent1@modelschool.tf',
                'note': 'View child results, messages, fees',
            },
            {
                'role': 'Student',
                'email': 'student1@modelschool.tf',
                'note': 'Homework, results, timetable',
            },
            {
                'role': 'Guest (Read-Only)',
                'email': 'guest@tabsforge.com',
                'note': 'Obtain token via POST /api/auth/guest-token/ — no credentials required',
            },
        ],
    })
