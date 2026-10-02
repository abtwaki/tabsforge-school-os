"""Base tenant-scoped DRF permission."""
from rest_framework import permissions

from accounts.models import User


class IsTenantScoped(permissions.BasePermission):
    """
    Base permission allowing any authenticated user associated with a school.

    Super admins may access any tenant data, optionally scoped via
    ``?school_id=``. School-scoped users must belong to a school.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        user = request.user
        if user.is_superuser or user.role == User.Roles.SUPER_ADMIN:
            return True
        if user.school_id is None:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or user.role == User.Roles.SUPER_ADMIN:
            return True
        school = getattr(obj, 'school', None)
        return bool(school and school.id == user.school_id)
