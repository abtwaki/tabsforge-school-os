"""Admissions workflow views."""
import logging
from datetime import timezone as dt_tz

from django.utils import timezone
from rest_framework import serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from admissions.models import AdmissionConfig, Application
from core.utils import get_current_school, filter_by_school
from students.models import Student, StudentEnrollment, Guardian, GuardianStudent
from academics.models import Class

from . import permissions as perms

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

class AdmissionConfigSerializer(drf_serializers.ModelSerializer):
    preview = drf_serializers.ReadOnlyField()

    class Meta:
        model = AdmissionConfig
        fields = [
            'id', 'school', 'prefix', 'include_year', 'year_format',
            'separator', 'sequence_digits', 'current_sequence',
            'custom_format', 'preview', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'school', 'current_sequence', 'created_at', 'updated_at']


class ApplicationSerializer(drf_serializers.ModelSerializer):
    applicant_full_name = drf_serializers.ReadOnlyField()
    class_name = drf_serializers.CharField(source='applying_for_class.name', read_only=True, allow_null=True)
    session_name = drf_serializers.CharField(source='session.name', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'school', 'first_name', 'last_name', 'applicant_full_name',
            'date_of_birth', 'gender', 'address', 'previous_school', 'previous_class',
            'additional_info', 'applying_for_class', 'class_name',
            'session', 'session_name',
            'guardian_name', 'guardian_relationship', 'guardian_phone',
            'guardian_email', 'guardian_address',
            'passport_photo', 'birth_certificate', 'previous_result', 'other_document',
            'status', 'reviewed_by', 'reviewed_at', 'review_notes',
            'generated_admission_number', 'student',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'school', 'reviewed_by', 'reviewed_at',
            'generated_admission_number', 'student', 'created_at', 'updated_at',
        ]


# ---------------------------------------------------------------------------
# ViewSets
# ---------------------------------------------------------------------------

class AdmissionConfigViewSet(viewsets.ModelViewSet):
    queryset = AdmissionConfig.objects.all()
    serializer_class = AdmissionConfigSerializer
    permission_classes = [perms.IsSchoolAdmin]

    def get_queryset(self):
        return filter_by_school(self.queryset, self.request)

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        serializer.save(school=school)


class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return filter_by_school(self.queryset, self.request)

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        serializer.save(school=school)

    @action(detail=True, methods=['post'], url_path='approve', permission_classes=[perms.IsSchoolAdmin])
    def approve(self, request, pk=None):
        """Approve an application: generate admission number and create student record."""
        app = self.get_object()
        if app.status == Application.Status.APPROVED:
            return Response({'detail': 'Already approved.'}, status=400)

        school = app.school

        # Get or create admission config
        config, _ = AdmissionConfig.objects.get_or_create(
            school=school, defaults={'prefix': school.subdomain[:3].upper()}
        )
        adm_num = config.generate_next()

        # Create the student record
        student = Student.objects.create(
            school=school,
            admission_number=adm_num,
            first_name=app.first_name,
            last_name=app.last_name,
            date_of_birth=app.date_of_birth,
            gender=app.gender,
            address=app.address,
        )

        # Enroll in the session
        if app.applying_for_class:
            section = app.applying_for_class.sections.first()
            if section:
                current_term = school.terms.filter(is_current=True).first()
                if current_term:
                    StudentEnrollment.objects.get_or_create(
                        school=school,
                        student=student,
                        session=app.session,
                        term=current_term,
                        defaults={'section': section, 'status': StudentEnrollment.Status.ACTIVE},
                    )

        # Create guardian record if guardian email provided
        if app.guardian_email:
            from accounts.models import User
            guardian_user = User.objects.filter(email=app.guardian_email, school=school).first()
            if not guardian_user:
                guardian_user = User.objects.create_user(
                    email=app.guardian_email,
                    first_name=app.guardian_name.split()[0] if app.guardian_name else 'Parent',
                    last_name=' '.join(app.guardian_name.split()[1:]) if len(app.guardian_name.split()) > 1 else '',
                    role=User.Roles.PARENT,
                    school=school,
                    password=User.objects.make_random_password(),
                )
            guardian, _ = Guardian.objects.get_or_create(
                school=school, user=guardian_user,
                defaults={
                    'first_name': guardian_user.first_name,
                    'last_name': guardian_user.last_name,
                    'phone': app.guardian_phone,
                    'email': app.guardian_email,
                    'relationship': app.guardian_relationship,
                },
            )
            GuardianStudent.objects.get_or_create(
                school=school, guardian=guardian, student=student,
                defaults={'relationship': app.guardian_relationship, 'is_primary': True},
            )

        # Update application
        app.status = Application.Status.APPROVED
        app.reviewed_by = request.user
        app.reviewed_at = timezone.now()
        app.generated_admission_number = adm_num
        app.student = student
        app.save()

        return Response({
            'detail': 'Application approved.',
            'admission_number': adm_num,
            'student_id': student.pk,
        })

    @action(detail=True, methods=['post'], url_path='reject', permission_classes=[perms.IsSchoolAdmin])
    def reject(self, request, pk=None):
        app = self.get_object()
        notes = request.data.get('notes', '')
        app.status = Application.Status.REJECTED
        app.reviewed_by = request.user
        app.reviewed_at = timezone.now()
        app.review_notes = notes
        app.save()
        return Response({'detail': 'Application rejected.'})

    @action(detail=True, methods=['post'], url_path='set-under-review', permission_classes=[perms.IsSchoolAdmin])
    def set_under_review(self, request, pk=None):
        app = self.get_object()
        app.status = Application.Status.UNDER_REVIEW
        app.save(update_fields=['status'])
        return Response({'detail': 'Status updated to Under Review.'})


# ---------------------------------------------------------------------------
# Admission config preview endpoint
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admission_number_preview(request):
    """Return the next admission number format without incrementing."""
    school = get_current_school(request)
    if not school:
        return Response({'error': 'No school context.'}, status=400)
    config = AdmissionConfig.objects.filter(school=school).first()
    if not config:
        return Response({'preview': 'ADM/2025/0001', 'configured': False})
    return Response({'preview': config.preview(), 'configured': True})
