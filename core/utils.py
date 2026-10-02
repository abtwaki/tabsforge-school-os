"""Shared tenant helpers."""
def dependent_counts(obj):
    """
    Count records directly tied to ``obj`` through reverse relations.

    Reports ``{verbose_name_plural: count}`` for every reverse FK/O2O/M2M
    accessor that has rows — this is what would cascade on a hard delete and
    what stays linked (and working) under soft-delete. Uses COUNT queries, so
    no related rows are loaded into memory.
    """
    counts = {}
    for f in obj._meta.get_fields(include_hidden=True):
        if not f.auto_created or f.concrete:
            continue
        if not (f.one_to_many or f.one_to_one or f.many_to_many):
            continue
        accessor = f.get_accessor_name()
        if not accessor:
            continue
        try:
            n = getattr(obj, accessor).count()
        except Exception:
            continue
        if n:
            label = str(
                f.related_model._meta.verbose_name_plural
                or f.related_model.__name__
            ).title()
            counts[label] = counts.get(label, 0) + n
    return counts


def _get_user_model():
    from accounts.models import User
    return User


def _get_school_model():
    from schools.models import School
    return School


def get_current_school(request):
    """Resolve the active school for the request, taking auth timing into account."""
    current = getattr(request, 'current_school', None)
    if current is not None:
        return current

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None

    User = _get_user_model()
    School = _get_school_model()

    if user.is_superuser or user.role == User.Roles.SUPER_ADMIN:
        school_id = request.GET.get('school_id')
        if school_id:
            try:
                return School.objects.get(pk=school_id)
            except School.DoesNotExist:
                return None
        return None

    return user.school


def filter_by_school(qs, request):
    """
    Restrict a queryset to the request's current school.

    Super admins with no explicit ``school_id`` filter get the unfiltered
    queryset.
    """
    current_school = get_current_school(request)
    if current_school is not None:
        return qs.filter(school=current_school)

    user = getattr(request, 'user', None)
    if user and (user.is_superuser or user.role == User.Roles.SUPER_ADMIN):
        return qs

    return qs.none()


def can_access_school(user, school):
    """Return True if the user is allowed to access data for ``school``."""
    if not user or not user.is_authenticated:
        return False
    User = _get_user_model()
    if user.is_superuser or user.role == User.Roles.SUPER_ADMIN:
        return True
    return user.school_id == school.id


def int_param(params, key):
    """Parse an integer query param; raise 400 rather than crash on junk.

    Viewsets filter PKs straight from query params — a non-numeric value
    (``?term=abc``) otherwise surfaces as a 500 IntegrityError/ValueError.
    """
    value = params.get(key)
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({key: 'Expected an integer.'})


def date_param(params, key):
    """Parse an ISO date query param; raise 400 rather than crash on junk."""
    import datetime
    value = params.get(key)
    if value in (None, ''):
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({key: 'Expected a YYYY-MM-DD date.'})


def audit(request, action, obj=None, changes=None, school=None):
    """Write an AuditLog row. Never raises — logging must not break requests.

    ``action`` is a dotted verb like ``user.suspend`` or ``invoice.bulk_create``.
    ``obj`` is the affected record (its type/id/repr are captured).
    ``changes`` is a small dict of before→after or payload details.
    """
    try:
        from core.models import AuditLog
        user = getattr(request, 'user', None)
        if user is not None and not getattr(user, 'is_authenticated', False):
            user = None
        if school is None:
            school = get_current_school(request)
            if school is None and obj is not None:
                school = getattr(obj, 'school', None)
                if obj is not None and obj.__class__.__name__ == 'School':
                    school = obj
        meta = getattr(request, 'META', {})
        ip = meta.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or meta.get('REMOTE_ADDR') or None
        AuditLog.objects.create(
            school=school,
            actor=user,
            actor_email=getattr(user, 'email', '') or '',
            actor_role=getattr(user, 'role', '') or '',
            action=action,
            object_type=obj._meta.label_lower if obj is not None else '',
            object_id=str(obj.pk) if obj is not None else '',
            object_repr=str(obj)[:200] if obj is not None else '',
            changes=changes or {},
            ip=ip[:45] if ip else None,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception('audit log failed for %s', action)
