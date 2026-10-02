"""
Part 4 — Multi-Branch / Group of Schools views.

Endpoints:
  GET/POST        /api/groups/                    — list/create school groups
  GET/PATCH       /api/groups/<pk>/               — group detail/update
  GET             /api/groups/<pk>/dashboard/     — consolidated stats
  GET             /api/groups/<pk>/branches/      — list branch schools
  POST            /api/groups/<pk>/branches/      — add a branch school
  DELETE          /api/groups/<pk>/branches/<school_pk>/ — remove branch
  POST            /api/groups/<pk>/impersonate/<school_pk>/ — act-as branch admin
"""
import logging
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.permissions import IsSuperAdmin
from schools.models import School, SchoolGroup
from students.models import Student
from finance.models import Invoice, Payment
from accounts.models import User

logger = logging.getLogger(__name__)


# ── Serializers ──────────────────────────────────────────────────────────────

class SchoolGroupSerializer(serializers.ModelSerializer):
    branch_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SchoolGroup
        fields = [
            'id', 'name', 'description', 'logo', 'contact_email', 'contact_phone',
            'billing_mode', 'is_active', 'branch_count', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'branch_count']

    def get_branch_count(self, obj):
        return obj.branches.count()


class BranchSummarySerializer(serializers.ModelSerializer):
    student_count = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = ['id', 'name', 'subdomain', 'tier', 'status', 'student_count', 'staff_count']

    def get_student_count(self, obj):
        return Student.objects.filter(school=obj).count()

    def get_staff_count(self, obj):
        return User.objects.filter(school=obj, role__in=['staff', 'school_admin', 'accountant']).count()


# ── ViewSet ───────────────────────────────────────────────────────────────────

def is_group_owner_or_superadmin(user, group=None):
    if user.is_superuser or user.role == User.Roles.SUPER_ADMIN:
        return True
    if user.role == User.Roles.GROUP_OWNER and (group is None or user.school_group_id == group.pk):
        return True
    return False


class SchoolGroupViewSet(viewsets.ModelViewSet):
    serializer_class = SchoolGroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == User.Roles.SUPER_ADMIN:
            return SchoolGroup.objects.all()
        if user.role == User.Roles.GROUP_OWNER and user.school_group:
            return SchoolGroup.objects.filter(pk=user.school_group_id)
        return SchoolGroup.objects.none()

    def get_permissions(self):
        if self.action in ('create', 'destroy'):
            return [IsAuthenticated(), IsSuperAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=['get'], url_path='dashboard')
    def dashboard(self, request, pk=None):
        """Consolidated dashboard for a group owner."""
        group = self.get_object()
        if not is_group_owner_or_superadmin(request.user, group):
            return Response({'detail': 'Not permitted.'}, status=403)

        branches = School.objects.filter(group=group)
        branch_data = []
        total_students = 0
        total_revenue = 0
        total_outstanding = 0

        for branch in branches:
            students = Student.objects.filter(school=branch).count()
            invoices = Invoice.objects.filter(school=branch)
            revenue = sum(float(i.amount_paid) for i in invoices)
            outstanding = sum(float(i.balance) for i in invoices if i.balance > 0)
            total_students += students
            total_revenue += revenue
            total_outstanding += outstanding
            branch_data.append({
                'id': branch.id,
                'name': branch.name,
                'subdomain': branch.subdomain,
                'tier': branch.tier,
                'status': branch.status,
                'students': students,
                'revenue': round(revenue, 2),
                'outstanding': round(outstanding, 2),
            })

        return Response({
            'group': SchoolGroupSerializer(group).data,
            'summary': {
                'total_branches': len(branch_data),
                'total_students': total_students,
                'total_revenue': round(total_revenue, 2),
                'total_outstanding': round(total_outstanding, 2),
            },
            'branches': branch_data,
        })

    @action(detail=True, methods=['get', 'post'], url_path='branches')
    def branches(self, request, pk=None):
        group = self.get_object()
        if not is_group_owner_or_superadmin(request.user, group):
            return Response({'detail': 'Not permitted.'}, status=403)

        if request.method == 'GET':
            schools = School.objects.filter(group=group)
            return Response(BranchSummarySerializer(schools, many=True).data)

        # POST: attach an existing school to this group
        school_id = request.data.get('school_id')
        if not school_id:
            return Response({'detail': 'school_id required.'}, status=400)
        try:
            school = School.objects.get(pk=school_id)
        except School.DoesNotExist:
            return Response({'detail': 'School not found.'}, status=404)
        school.group = group
        school.save(update_fields=['group'])
        return Response({'detail': f'{school.name} added to {group.name}.'})

    @action(detail=True, methods=['delete'], url_path='branches/(?P<school_pk>[^/.]+)')
    def remove_branch(self, request, pk=None, school_pk=None):
        group = self.get_object()
        if not is_group_owner_or_superadmin(request.user, group):
            return Response({'detail': 'Not permitted.'}, status=403)
        try:
            school = School.objects.get(pk=school_pk, group=group)
        except School.DoesNotExist:
            return Response({'detail': 'Branch not found in this group.'}, status=404)
        school.group = None
        school.save(update_fields=['group'])
        return Response({'detail': f'{school.name} removed from group.'})

    @action(detail=True, methods=['post'], url_path='impersonate/(?P<school_pk>[^/.]+)')
    def impersonate(self, request, pk=None, school_pk=None):
        """
        Group Owner / Super Admin: get an auth token scoped to a specific branch.
        This does not create a new user — it returns the existing branch admin's token
        so the dashboard can switch context. Only available to Group Owner and Super Admin.
        """
        group = self.get_object()
        if not is_group_owner_or_superadmin(request.user, group):
            return Response({'detail': 'Not permitted.'}, status=403)
        try:
            school = School.objects.get(pk=school_pk, group=group)
        except School.DoesNotExist:
            return Response({'detail': 'Branch not found.'}, status=404)

        # Return the first school admin for that branch
        branch_admin = User.objects.filter(school=school, role=User.Roles.SCHOOL_ADMIN).first()
        if not branch_admin:
            return Response({'detail': 'No school admin found for this branch.'}, status=404)
        from rest_framework.authtoken.models import Token
        token, _ = Token.objects.get_or_create(user=branch_admin)
        return Response({
            'token': token.key,
            'school': school.name,
            'subdomain': school.subdomain,
            'admin_email': branch_admin.email,
        })
