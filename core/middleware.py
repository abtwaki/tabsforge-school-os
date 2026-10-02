"""Tenant middleware and utilities."""
from django.utils.deprecation import MiddlewareMixin


class TenantMiddleware(MiddlewareMixin):
    """
    Attaches ``request.current_school`` based on the authenticated user.

    - Super admins may have a ``None`` current school unless they explicitly
      request one via the ``?school_id=`` query parameter.
    - All other roles are pinned to their own ``user.school``.

    Note: suspension enforcement lives in ``api.permissions.IsSchoolActive``
    because token auth resolves the user at view time, not middleware time.
    """

    def process_request(self, request):
        request.current_school = None
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return

        user = request.user
        if user.is_superuser or user.role == user.Roles.SUPER_ADMIN:
            school_id = request.GET.get('school_id')
            if school_id:
                try:
                    from schools.models import School
                    request.current_school = School.objects.filter(pk=school_id).first()
                except (ValueError, School.DoesNotExist):
                    pass
        else:
            request.current_school = user.school


class SubdomainTenantMiddleware(MiddlewareMixin):
    """
    Part 9 — Subdomain-to-school resolver.

    Reads the Host header (e.g. modelschool.tabsforge.com), strips the base
    domain, and attaches request.subdomain_school so any view can use it.

    This works INDEPENDENTLY of authentication — even unauthenticated requests
    (e.g. the admission intake WhatsApp webhook) get the correct school context.

    Prerequisites (cannot be done from the VPS alone):
      1. Add a wildcard DNS record at your registrar (Qservers):
            *.tabsforge.com  →  A  →  37.59.205.38
      2. Apache config: add ServerAlias *.tabsforge.com in the VirtualHost block
      3. Wildcard SSL: run certbot with DNS-01 challenge (HTTP-01 does NOT cover wildcards):
            certbot certonly --manual --preferred-challenges=dns -d *.tabsforge.com
         or use an ACME DNS plugin for Qservers if available.

    The middleware does NOT block requests from the main domain — it simply sets
    request.subdomain_school = None for non-subdomain hosts.
    """

    BASE_DOMAINS = ('tabsforge.com', 'www.tabsforge.com', 'acemfs.futminna.edu.ng', 'localhost', '127.0.0.1')

    def process_request(self, request):
        request.subdomain_school = None
        host = request.get_host().split(':')[0].lower()  # strip port

        # Determine if this is a subdomain request
        subdomain = None
        for base in self.BASE_DOMAINS:
            if host == base:
                return  # main domain — no subdomain context
            if host.endswith('.' + base):
                subdomain = host[: -(len(base) + 1)]
                break

        if not subdomain:
            return

        try:
            from schools.models import School
            school = School.objects.filter(subdomain=subdomain, status='active').first()
            request.subdomain_school = school
        except Exception:
            pass
