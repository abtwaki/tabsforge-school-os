"""Project authentication classes."""
from rest_framework import exceptions
from rest_framework.authentication import SessionAuthentication, TokenAuthentication


def _assert_school_active(user):
    school = getattr(user, 'school', None)
    if school is not None and school.status == school.Status.SUSPENDED:
        raise exceptions.PermissionDenied(
            'This school account is currently suspended. Contact support.'
        )


class TenantTokenAuthentication(TokenAuthentication):
    """Token auth that rejects every request from a suspended school.

    School suspension must take effect immediately — including for sessions
    that logged in before the suspension — so enforcement happens at the
    authentication layer where every API request passes through.
    """

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        _assert_school_active(user)
        return user, token


class TenantSessionAuthentication(SessionAuthentication):
    """Same suspension check for session-authenticated requests."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            _assert_school_active(result[0])
        return result
