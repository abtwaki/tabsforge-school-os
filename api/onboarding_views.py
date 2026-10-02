"""School onboarding endpoints."""
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from api.permissions import IsSuperAdmin
from billing.models import Subscription
from billing.providers import create_subscription, tier_price
from notifications.utils import queue_email
from schools.models import AcademicSession, School, Term

from . import serializers as ser


# Canonical module catalogue — (key, label, minimum tier). Mirrors the
# frontend menu map; used by /onboarding/tiers/ and module-grant reviews.
MODULE_CATALOG = [
    ('applications', 'Admissions', 'Sprout'),
    ('students', 'Students', 'Sprout'),
    ('guardians', 'Guardians', 'Sprout'),
    ('classes', 'Classes & Arms', 'Sprout'),
    ('sections', 'Sections', 'Sprout'),
    ('subjects', 'Subjects', 'Sprout'),
    ('academic-sessions', 'Sessions', 'Sprout'),
    ('terms', 'Terms', 'Sprout'),
    ('staff', 'Staff', 'Sprout'),
    ('announcements', 'Announcements', 'Sprout'),
    ('messages', 'Messaging', 'Sprout'),
    ('users-roles', 'Users & Roles', 'Sprout'),
    ('branding', 'Branding', 'Sprout'),
    ('csv-import', 'Data Import', 'Sprout'),
    ('data-export', 'Data Export', 'Sprout'),
    ('audit-log', 'Audit Log', 'Sprout'),
    ('attendance', 'Attendance', 'Roots'),
    ('grades', 'Results & Grades', 'Roots'),
    ('report-cards', 'Report Cards', 'Roots'),
    ('grading-schemes', 'Grading Schemes', 'Roots'),
    ('timetable', 'Timetable', 'Roots'),
    ('assignments', 'Assignments', 'Roots'),
    ('rollover', 'Promotion & Rollover', 'Roots'),
    ('fees', 'Finance Overview', 'Roots'),
    ('invoices', 'Invoices', 'Roots'),
    ('payments', 'Payments', 'Roots'),
    ('expenses', 'Expenses', 'Roots'),
    ('library', 'Library', 'Bloom'),
    ('live-lessons', 'Live Lessons', 'Bloom'),
    ('transport', 'Transport', 'Summit'),
    ('hostel', 'Hostel', 'Summit'),
]
MODULE_KEYS = {m[0] for m in MODULE_CATALOG}
TIER_ORDER = ['Sprout', 'Roots', 'Bloom', 'Summit']
TIER_INFO = {
    'Sprout': {
        'tagline': 'Essential records',
        'suitable': 'New and small schools digitising student records for the first time.',
    },
    'Roots': {
        'tagline': 'Run daily operations',
        'suitable': 'Established schools that need attendance, results, and fee management day-to-day.',
    },
    'Bloom': {
        'tagline': 'Grow your resources',
        'suitable': 'Growing schools adding a library and live online lessons.',
    },
    'Summit': {
        'tagline': 'The complete campus',
        'suitable': 'Large or boarding schools managing transport routes and hostels.',
    },
}


def _tier_catalog():
    """Pricing + modules per plan, for the onboarding picker."""
    from billing.providers import SIZE_TIERS
    base = SIZE_TIERS[0]
    catalog = []
    for i, tier in enumerate(TIER_ORDER):
        modules = [
            {'key': k, 'label': l}
            for k, l, t in MODULE_CATALOG
            if TIER_ORDER.index(t) <= i
        ]
        extras = [
            {'key': k, 'label': l}
            for k, l, t in MODULE_CATALOG
            if TIER_ORDER.index(t) > i
        ]
        catalog.append({
            'id': tier.lower(), 'name': tier,
            'tagline': TIER_INFO[tier]['tagline'],
            'suitable': TIER_INFO[tier]['suitable'],
            'setup_fee': base['setup_fee'],
            'rate_per_student': base['rate'],
            'billing': f"₦{base['setup_fee']:,} setup · ₦{base['rate']:,}/student/term",
            'modules': modules,
            'extra_modules': extras,
        })
    return catalog


@api_view(['GET'])
@permission_classes([AllowAny])
def tiers_view(request):
    """Public: plan catalogue with pricing, modules, and fit guidance."""
    return Response({'tiers': _tier_catalog()})


def onboard_school(data, commit=True):
    """
    Validate and optionally create a school onboarding record.

    Returns a tuple (errors, school, admin_user). `school` and `admin_user`
    are None when `commit` is False or when validation fails.
    """
    required = [
        'school_name', 'address', 'subdomain', 'tier',
        'admin_email', 'admin_name', 'admin_password',
    ]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return [f"Missing fields: {', '.join(missing)}"], None, None

    subdomain = str(data['subdomain']).strip().lower()
    if not _valid_subdomain(subdomain):
        return ['Subdomain must be 3-63 characters, use only letters, numbers and single hyphens, and cannot be reserved.'], None, None
    if School.objects.filter(subdomain=subdomain).exists():
        return ['Subdomain is already in use.'], None, None

    admin_email = str(data['admin_email']).strip().lower()
    try:
        validate_email(admin_email)
    except ValidationError:
        return ['Enter a valid admin email address.'], None, None
    if User.objects.filter(email__iexact=admin_email).exists():
        return ['An account with this admin email already exists.'], None, None

    admin_name = str(data['admin_name']).strip()
    if len(admin_name) < 2:
        return ['Admin name must contain at least 2 characters.'], None, None
    try:
        validate_password(data['admin_password'])
    except ValidationError as exc:
        return [exc.messages[0]], None, None

    tier = data['tier']
    if not _valid_tier(tier):
        return ['Invalid feature tier.'], None, None

    billing_cycle = data.get('billing_cycle') or 'termly'
    if billing_cycle != 'termly':
        return ['Billing cycle must be termly.'], None, None

    requested_modules = data.get('requested_modules') or []
    if not isinstance(requested_modules, list):
        return ['requested_modules must be a list of module keys.'], None, None
    requested_modules = [m for m in requested_modules if m in MODULE_KEYS]

    if not commit:
        return [], None, None

    try:
        with transaction.atomic():
            school = School.objects.create(
                name=str(data['school_name']).strip(),
                address=str(data['address']).strip(),
                contact_info=data.get('contact_info', {}),
                subdomain=subdomain,
                tier=tier,
                status=School.Status.ONBOARDING,
                primary_color=data.get('primary_color', '#125A0F'),
                secondary_color=data.get('secondary_color', '#0B367B'),
                requested_modules=requested_modules,
            )

            today = timezone.now().date()
            session = AcademicSession.objects.create(
                school=school,
                name=f'{today.year}-{today.year + 1} Session',
                start_date=today,
                end_date=today + timedelta(days=365),
                is_current=True,
            )
            Term.objects.create(
                school=school,
                session=session,
                name='First Term',
                start_date=today,
                end_date=today + timedelta(days=120),
                is_current=True,
            )

            first, last = _split_name(admin_name)
            admin_user = User.objects.create_user(
                email=admin_email,
                password=data['admin_password'],
                first_name=first,
                last_name=last,
                role=User.Roles.SCHOOL_ADMIN,
                school=school,
                is_staff=True,
            )

            subject = f'Welcome to {school.name} on TabsForge'
            body = (
                f'Your school admin account has been created for {school.name}.\n\n'
                f'Sign in at https://tabsforge.com/login\n'
                f'Email: {admin_user.email}'
            )
            transaction.on_commit(
                lambda: queue_email(school, admin_user.email, subject, body)
            )

            amount = tier_price(school.tier, billing_cycle)
            sub_result = create_subscription(amount, 'NGN', metadata={'school': school.pk})
            Subscription.objects.create(
                school=school,
                tier=school.tier,
                billing_cycle=billing_cycle,
                amount=amount,
                currency='NGN',
                status=Subscription.Status.TRIAL,
                provider=sub_result['provider'],
                provider_ref=sub_result['provider_ref'],
            )
    except IntegrityError:
        return ['The subdomain or admin email is already in use.'], None, None

    return [], school, admin_user


@api_view(['POST'])
@permission_classes([AllowAny])
def onboarding_view(request):
    """
    Public self-service school signup.

    The school is created in ``onboarding`` status: it cannot be logged
    into (login rejects non-active schools) until a super admin approves
    it via ``/api/onboarding/approvals/<id>/approve/``. Super admins can
    also use this endpoint to onboard a school directly.
    """
    errors, school, admin_user = onboard_school(request.data, commit=True)
    if errors:
        return Response({'detail': errors[0]}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            **ser.SchoolSerializer(school).data,
            'admin_email': admin_user.email,
            'message': 'School created. Awaiting super-admin approval before going fully live.',
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def check_subdomain_view(request):
    """Check whether a subdomain is available."""
    subdomain = request.GET.get('subdomain', '').strip().lower()
    if not subdomain:
        return Response(
            {'detail': 'subdomain query parameter is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    valid = _valid_subdomain(subdomain)
    available = valid and not School.objects.filter(subdomain=subdomain).exists()
    return Response({'available': available, 'valid': valid})


def _approval_payload(school):
    """School + its applicant admin account + subscription, for the review UI."""
    data = ser.SchoolSerializer(school).data
    admin = school.users.filter(role=User.Roles.SCHOOL_ADMIN).order_by('date_joined').first()
    data['admin'] = (
        {'id': admin.id, 'email': admin.email,
         'name': admin.get_full_name(), 'is_active': admin.is_active}
        if admin else None
    )
    data['admin_notes'] = school.admin_notes
    data['requested_modules'] = school.requested_modules or []
    data['module_labels'] = {k: l for k, l, _ in MODULE_CATALOG}
    tier_idx = TIER_ORDER.index(school.tier) if school.tier in TIER_ORDER else 0
    data['tier_modules'] = [
        k for k, _, t in MODULE_CATALOG if TIER_ORDER.index(t) <= tier_idx]
    data['enabled_modules'] = school.enabled_modules or []
    try:
        sub = school.subscription
        data['subscription'] = {
            'tier': sub.tier, 'status': str(sub.status),
            'amount': str(sub.amount), 'billing_cycle': sub.billing_cycle,
        }
    except Subscription.DoesNotExist:
        data['subscription'] = None
    return data


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def onboarding_approvals_view(request):
    """List schools awaiting super-admin approval (enriched for review)."""
    schools = School.objects.filter(status=School.Status.ONBOARDING).order_by('created_at')
    return Response([_approval_payload(s) for s in schools])


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def approval_detail_view(request, pk):
    """
    GET   — full onboarding request detail (school + admin + subscription).
    PATCH — edit the request before approving: school fields plus the
            applicant admin's name/email. Body keys:
              name, address, subdomain, tier, custom_domain,
              primary_color, secondary_color, enabled_modules,
              contact_email, contact_phone, admin_notes,
              admin_name, admin_email
    """
    from core.utils import audit
    try:
        school = School.objects.get(pk=pk)
    except School.DoesNotExist:
        raise NotFound('School not found.')

    if request.method == 'GET':
        return Response(_approval_payload(school))

    data = request.data
    changed = {}

    school_fields = ['name', 'address', 'custom_domain', 'primary_color',
                     'secondary_color', 'admin_notes']
    for field in school_fields:
        if field in data:
            new = str(data[field]).strip()
            if getattr(school, field) != new:
                changed[field] = {'from': getattr(school, field), 'to': new}
                setattr(school, field, new)

    if 'subdomain' in data:
        sub = str(data['subdomain']).strip().lower()
        if sub != school.subdomain:
            if not _valid_subdomain(sub):
                return Response({'detail': 'Invalid subdomain.'}, status=400)
            if School.objects.filter(subdomain=sub).exclude(pk=school.pk).exists():
                return Response({'detail': 'Subdomain is already in use.'}, status=400)
            changed['subdomain'] = {'from': school.subdomain, 'to': sub}
            school.subdomain = sub

    if 'tier' in data and data['tier'] != school.tier:
        if not _valid_tier(data['tier']):
            return Response({'detail': 'Invalid tier.'}, status=400)
        changed['tier'] = {'from': school.tier, 'to': data['tier']}
        school.tier = data['tier']

    if 'enabled_modules' in data:
        mods = data['enabled_modules']
        if not isinstance(mods, list):
            return Response({'detail': 'enabled_modules must be a list.'}, status=400)
        changed['enabled_modules'] = {'from': school.enabled_modules, 'to': mods}
        school.enabled_modules = mods

    if 'requested_modules' in data:
        mods = [m for m in (data['requested_modules'] or []) if m in MODULE_KEYS]
        if mods != school.requested_modules:
            changed['requested_modules'] = {'from': school.requested_modules, 'to': mods}
            school.requested_modules = mods

    contact = dict(school.contact_info or {})
    if 'contact_email' in data:
        contact['email'] = str(data['contact_email']).strip()
    if 'contact_phone' in data:
        contact['phone'] = str(data['contact_phone']).strip()
    if contact != school.contact_info:
        changed['contact_info'] = {'from': school.contact_info, 'to': contact}
        school.contact_info = contact

    if changed:
        school.save()

    # Applicant admin account edits
    admin = school.users.filter(role=User.Roles.SCHOOL_ADMIN).order_by('date_joined').first()
    if admin:
        admin_changed = {}
        if 'admin_email' in data:
            email = str(data['admin_email']).strip().lower()
            if email != admin.email:
                try:
                    validate_email(email)
                except ValidationError:
                    return Response({'detail': 'Enter a valid admin email address.'}, status=400)
                if User.objects.filter(email__iexact=email).exclude(pk=admin.pk).exists():
                    return Response({'detail': 'An account with this email already exists.'}, status=400)
                admin_changed['admin_email'] = {'from': admin.email, 'to': email}
                admin.email = email
        if 'admin_name' in data:
            first, last = _split_name(data['admin_name'])
            if first and (first != admin.first_name or last != admin.last_name):
                admin_changed['admin_name'] = {
                    'from': admin.get_full_name(), 'to': data['admin_name']}
                admin.first_name, admin.last_name = first, last
        if admin_changed:
            admin.save()
            changed.update(admin_changed)

    if changed:
        audit(request, 'school.onboarding_edit', school, changes=changed)
    return Response(_approval_payload(school))


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def approve_school_view(request, pk):
    """Approve an onboarding school and activate it."""
    from core.utils import audit
    try:
        school = School.objects.get(pk=pk)
    except School.DoesNotExist:
        raise NotFound('School not found.')
    school.status = School.Status.ACTIVE
    school.save(update_fields=['status'])
    try:
        subscription = school.subscription
        subscription.status = Subscription.Status.ACTIVE
        subscription.save(update_fields=['status'])
    except Subscription.DoesNotExist:
        pass
    audit(request, 'school.approve', school,
          changes={'note': request.data.get('note', '')})
    return Response({'detail': f'{school.name} has been approved and activated.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def flag_school_view(request, pk):
    """Flag/suspend an onboarding school for review."""
    from core.utils import audit
    try:
        school = School.objects.get(pk=pk)
    except School.DoesNotExist:
        raise NotFound('School not found.')
    school.status = School.Status.SUSPENDED
    school.save(update_fields=['status'])
    audit(request, 'school.flag', school,
          changes={'reason': request.data.get('reason', '')})
    return Response({'detail': f'{school.name} has been flagged and suspended.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def reject_school_view(request, pk):
    """
    Permanently reject an onboarding request — deletes the school record,
    its applicant admin account, default session/term, and trial subscription.
    Only allowed while the school is still in ``onboarding`` status.
    """
    from core.utils import audit
    try:
        school = School.objects.get(pk=pk)
    except School.DoesNotExist:
        raise NotFound('School not found.')
    if school.status != School.Status.ONBOARDING:
        return Response(
            {'detail': 'Only pending onboarding requests can be rejected — suspend the school instead.'},
            status=400)
    reason = str(request.data.get('reason', '')).strip()
    audit(request, 'school.reject', school,
          changes={'reason': reason, 'subdomain': school.subdomain})
    with transaction.atomic():
        school.users.all().delete()  # SET_NULL would orphan applicant accounts
        school.delete()              # cascades session, term, subscription
    return Response({'detail': 'Onboarding request rejected and removed.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def resend_welcome_view(request, pk):
    """Re-send the welcome email to the applicant admin."""
    from core.utils import audit
    try:
        school = School.objects.get(pk=pk)
    except School.DoesNotExist:
        raise NotFound('School not found.')
    admin = school.users.filter(role=User.Roles.SCHOOL_ADMIN).order_by('date_joined').first()
    if not admin:
        return Response({'detail': 'No admin account is linked to this request.'}, status=400)
    queue_email(
        school, admin.email,
        f'Welcome to {school.name} on TabsForge',
        f'Your school admin account for {school.name} is ready.\n\n'
        f'Sign in at https://tabsforge.com/login\n'
        f'Email: {admin.email}'
    )
    audit(request, 'school.resend_welcome', school)
    return Response({'detail': f'Welcome email re-sent to {admin.email}.'})


def _valid_tier(tier):
    return tier in {c[0] for c in School.Tiers.choices}


def _valid_subdomain(subdomain):
    reserved = {'admin', 'api', 'app', 'mail', 'support', 'www'}
    return (
        3 <= len(subdomain) <= 63
        and subdomain not in reserved
        and slugify(subdomain) == subdomain
        and '--' not in subdomain
    )


def _split_name(full_name):
    parts = str(full_name).strip().split(' ', 1)
    return parts[0], parts[1] if len(parts) > 1 else ''
