"""DRF permission classes for TabsForge role-based access control."""
from rest_framework import permissions

from accounts.models import User

# Roles that manage the whole school (school admin + senior leadership).
ADMIN_SCOPE = {
    User.Roles.SCHOOL_ADMIN,
    User.Roles.PRINCIPAL,
    User.Roles.VICE_PRINCIPAL,
    User.Roles.ADMISSIONS_OFFICER,
    User.Roles.HR_ADMIN,
}
# Roles that may mark attendance / enter grades / manage academics.
TEACHING_SCOPE = {
    User.Roles.STAFF,
    User.Roles.TEACHER,
    User.Roles.FORM_TEACHER,
    User.Roles.EXAM_OFFICER,
    User.Roles.PRINCIPAL,
    User.Roles.VICE_PRINCIPAL,
    User.Roles.SCHOOL_ADMIN,
}
# Roles that manage fees, invoices, payments and expenses.
FINANCE_SCOPE = {
    User.Roles.ACCOUNTANT,
    User.Roles.SCHOOL_ADMIN,
}
# Roles that manage the library.
LIBRARY_SCOPE = {
    User.Roles.LIBRARIAN,
    User.Roles.SCHOOL_ADMIN,
    User.Roles.PRINCIPAL,
    User.Roles.VICE_PRINCIPAL,
}
# Roles that manage staff records / HR.
HR_SCOPE = {
    User.Roles.HR_ADMIN,
    User.Roles.SCHOOL_ADMIN,
    User.Roles.PRINCIPAL,
}
# Roles that can send invitations / manage users.
USER_MANAGER_SCOPE = {
    User.Roles.SCHOOL_ADMIN,
    User.Roles.PRINCIPAL,
    User.Roles.HR_ADMIN,
}


def _in(role_set):
    def check(request):
        return (
            request.user.is_authenticated
            and (request.user.is_superuser or request.user.role == User.Roles.SUPER_ADMIN
                 or request.user.role in role_set)
        )
    return check


class ReadOnlyForGuest(permissions.BasePermission):
    """
    Part 8 — Block all write operations for guest/demo accounts.
    Applied globally via DEFAULT_PERMISSION_CLASSES or per-viewset.
    """
    SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return True  # Let authentication handle this
        if getattr(request.user, 'is_guest', False):
            if request.method not in self.SAFE_METHODS:
                return False
        return True

    def has_object_permission(self, request, view, obj):
        if getattr(request.user, 'is_guest', False) and request.method not in self.SAFE_METHODS:
            return False
        return True


class IsSuperAdmin(permissions.BasePermission):
    """Allow only global super admins."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or request.user.role == request.user.Roles.SUPER_ADMIN
        )


class IsSchoolAdmin(permissions.BasePermission):
    """Allow school admins scoped to their own school."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.role == request.user.Roles.SUPER_ADMIN:
            return True
        if request.user.role == request.user.Roles.SCHOOL_ADMIN:
            return request.user.school is not None
        return False

    def has_object_permission(self, request, view, obj):
        return _belongs_to_user_school(request, obj)


class IsStaff(permissions.BasePermission):
    """Allow staff users (any school staff role, incl. leadership/operational roles)."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_superuser or request.user.role in {
            request.user.Roles.SUPER_ADMIN,
            *TEACHING_SCOPE,
        }

    def has_object_permission(self, request, view, obj):
        return _belongs_to_user_school(request, obj)


class IsAccountant(permissions.BasePermission):
    """Allow finance roles (accountant, school admin, super admin)."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.role in {
            request.user.Roles.SUPER_ADMIN,
            request.user.Roles.SCHOOL_ADMIN,
        }:
            return True
        return request.user.role in FINANCE_SCOPE

    def has_object_permission(self, request, view, obj):
        return _belongs_to_user_school(request, obj)


class IsFinanceOrFamilyReadOnly(IsAccountant):
    """Finance writes for finance roles; read-only access for parents and
    students, whose viewsets further scope records to their own children."""

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated and request.user.role in {
                request.user.Roles.PARENT,
                request.user.Roles.STUDENT,
                request.user.Roles.PRINCIPAL,
                request.user.Roles.VICE_PRINCIPAL,
            }
        return False


class IsParent(permissions.BasePermission):
    """Allow parents. Object-level filtering is handled in viewsets."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_superuser or request.user.role in {
            request.user.Roles.SUPER_ADMIN,
            request.user.Roles.SCHOOL_ADMIN,
            request.user.Roles.PARENT,
        }

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or user.role in {user.Roles.SUPER_ADMIN, user.Roles.SCHOOL_ADMIN}:
            return _belongs_to_user_school(request, obj)
        if user.role == user.Roles.PARENT:
            return _parent_owns_object(user, obj)
        return False


class IsStudent(permissions.BasePermission):
    """Allow students. Object-level filtering is handled in viewsets."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_superuser or request.user.role in {
            request.user.Roles.SUPER_ADMIN,
            request.user.Roles.SCHOOL_ADMIN,
            request.user.Roles.STUDENT,
        }

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or user.role in {user.Roles.SUPER_ADMIN, user.Roles.SCHOOL_ADMIN}:
            return _belongs_to_user_school(request, obj)
        if user.role == user.Roles.STUDENT:
            return _object_is_for_student(user.student_profile, obj)
        return False


# Helpers ----------------------------------------------------------------

def _belongs_to_user_school(request, obj):
    user = request.user
    if user.is_superuser or user.role == user.Roles.SUPER_ADMIN:
        return True
    school = getattr(obj, 'school', None)
    if school is None:
        return True
    return school == user.school


def _parent_owns_object(user, obj):
    try:
        guardian = user.guardian_profile
    except Exception:
        return False
    student = getattr(obj, 'student', None)
    if student is None:
        return False
    return guardian.wards.filter(student=student).exists()


def _object_is_for_student(student_profile, obj):
    if student_profile is None:
        return False
    student = getattr(obj, 'student', None)
    if student is not None:
        return student == student_profile
    # For user-related objects that don't expose `student`.
    return False


class IsTenantAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_superuser or request.user.role == request.user.Roles.SUPER_ADMIN or request.user.school is not None
        return request.user.is_superuser or request.user.role in {
            request.user.Roles.SUPER_ADMIN,
            *ADMIN_SCOPE,
        }

    def has_object_permission(self, request, view, obj):
        return _belongs_to_user_school(request, obj)


class IsSchoolStaffOrReadOnly(IsTenantAdminOrReadOnly):
    """Read for any school member; write for teaching staff and leadership roles."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return super().has_permission(request, view)
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_superuser or request.user.role in {
            request.user.Roles.SUPER_ADMIN,
            *TEACHING_SCOPE,
        }


class IsHROrReadOnly(IsTenantAdminOrReadOnly):
    """Read for any school member; write for HR / staff-admin roles."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return super().has_permission(request, view)
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_superuser or request.user.role in {
            request.user.Roles.SUPER_ADMIN,
            *HR_SCOPE,
        }


class IsLibrarianOrReadOnly(IsTenantAdminOrReadOnly):
    """Read for any school member; write for librarian/admin roles."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return super().has_permission(request, view)
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_superuser or request.user.role in {
            request.user.Roles.SUPER_ADMIN,
            *LIBRARY_SCOPE,
        }


class IsSchoolActive(permissions.BasePermission):
    """Reject all API access for users of a suspended school.

    Applied globally via DEFAULT_PERMISSION_CLASSES so suspension takes effect
    immediately for existing sessions — not just at next login. Platform-level
    accounts (no school) are unaffected; the auth endpoints use AllowAny so
    login itself can return the friendlier "awaiting approval" message.
    """

    message = 'This school account is currently suspended. Contact support.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return True
        school = getattr(user, 'school', None)
        if school is None:
            return True
        return school.status != school.Status.SUSPENDED


class IsResultPublisher(permissions.BasePermission):
    """Roles allowed to release/unrelease report cards to family portals."""

    RELEASE_ROLES = {
        User.Roles.SUPER_ADMIN, User.Roles.SCHOOL_ADMIN,
        User.Roles.PRINCIPAL, User.Roles.VICE_PRINCIPAL,
        User.Roles.EXAM_OFFICER,
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.role == User.Roles.SUPER_ADMIN:
            return True
        return request.user.role in self.RELEASE_ROLES and request.user.school is not None

    def has_object_permission(self, request, view, obj):
        return _belongs_to_user_school(request, obj)


class IsUserManager(permissions.BasePermission):
    """Allow roles that may invite/manage users in their school."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.role == User.Roles.SUPER_ADMIN:
            return True
        return request.user.role in USER_MANAGER_SCOPE and request.user.school is not None

    def has_object_permission(self, request, view, obj):
        return _belongs_to_user_school(request, obj)


class IsTenantScoped(permissions.BasePermission):
    """Allow any authenticated user that belongs to a school (used by tenant-scoped viewsets)."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.role == request.user.Roles.SUPER_ADMIN:
            return True
        return request.user.school is not None

    def has_object_permission(self, request, view, obj):
        return _belongs_to_user_school(request, obj)
