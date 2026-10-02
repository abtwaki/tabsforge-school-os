"""Result computation and report card views."""
import logging
from django.db.models import Exists, OuterRef
from django.http import HttpResponse
from rest_framework import serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.utils import audit, filter_by_school, get_current_school, int_param
from gradebook.models import GradeBoundary, GradingScheme, ReportCard, ResultSummary
from accounts.models import User
from schools.models import Term

from .result_engine import compute_results_for_term
from . import permissions as perms

logger = logging.getLogger(__name__)


class GradingSchemeSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = GradingScheme
        fields = [
            'id', 'school', 'name', 'is_default',
            'ca1_weight', 'ca2_weight', 'exam_weight',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'school', 'created_at', 'updated_at']


class GradeBoundarySerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = GradeBoundary
        fields = [
            'id', 'school', 'scheme', 'label', 'remark',
            'min_score', 'max_score', 'points', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'school', 'created_at', 'updated_at']


class ResultSummarySerializer(drf_serializers.ModelSerializer):
    student_name = drf_serializers.SerializerMethodField()
    subject_name = drf_serializers.CharField(source='subject.name', read_only=True)
    class_name = drf_serializers.CharField(source='school_class.name', read_only=True, allow_null=True)
    term_name = drf_serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = ResultSummary
        fields = [
            'id', 'school', 'student', 'student_name', 'term', 'term_name',
            'subject', 'subject_name', 'school_class', 'class_name',
            'ca1_score', 'ca2_score', 'exam_score', 'total_score',
            'grade', 'grade_remark', 'grade_points',
            'subject_position', 'class_position', 'teacher_comment',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'school', 'created_at', 'updated_at']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class ReportCardSerializer(drf_serializers.ModelSerializer):
    student_name = drf_serializers.SerializerMethodField()
    term_name = drf_serializers.CharField(source='term.name', read_only=True)
    session_name = drf_serializers.CharField(source='term.session.name', read_only=True)
    class_name = drf_serializers.CharField(source='school_class.name', read_only=True, allow_null=True)

    class Meta:
        model = ReportCard
        fields = [
            'id', 'school', 'student', 'student_name', 'term', 'term_name',
            'session_name', 'school_class', 'class_name',
            'total_score', 'average_score', 'subjects_count',
            'position', 'class_size', 'status',
            'teacher_comments', 'principal_comments', 'next_term_begins',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'school', 'created_at', 'updated_at']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class GradingSchemeViewSet(viewsets.ModelViewSet):
    queryset = GradingScheme.objects.all()
    serializer_class = GradingSchemeSerializer
    permission_classes = [perms.IsSchoolAdmin]

    def get_queryset(self):
        return filter_by_school(self.queryset, self.request)

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        # If setting is_default=True, unset others
        if serializer.validated_data.get('is_default'):
            GradingScheme.objects.filter(school=school).update(is_default=False)
        serializer.save(school=school)


class GradeBoundaryViewSet(viewsets.ModelViewSet):
    queryset = GradeBoundary.objects.all()
    serializer_class = GradeBoundarySerializer
    permission_classes = [perms.IsSchoolAdmin]

    def get_queryset(self):
        return filter_by_school(self.queryset, self.request)

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        serializer.save(school=school)


class ResultSummaryViewSet(viewsets.ModelViewSet):
    queryset = ResultSummary.objects.all()
    serializer_class = ResultSummarySerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Only grading-capable staff may edit computed rows (editable preview).
        if self.request.method in ('PATCH', 'PUT', 'POST', 'DELETE'):
            return [perms.IsSchoolStaffOrReadOnly()]
        return super().get_permissions()

    def update(self, request, *args, **kwargs):
        # Whitelist the fields staff may adjust on the preview.
        # request.data populates _full_data, which is what the serializer reads.
        allowed = {'teacher_comment', 'grade_remark'}
        request._full_data = {
            k: v for k, v in request.data.items() if k in allowed
        }
        return super().update(request, *args, **kwargs)

    def get_queryset(self):
        qs = filter_by_school(self.queryset, self.request)
        user = self.request.user
        params = self.request.query_params

        if user.role in {User.Roles.STUDENT, User.Roles.PARENT, User.Roles.GUEST}:
            # Families only see results whose report card has been released.
            if user.role == User.Roles.STUDENT and hasattr(user, 'student_profile'):
                qs = qs.filter(student=user.student_profile)
            elif user.role == User.Roles.PARENT and hasattr(user, 'guardian_profile'):
                qs = qs.filter(student__guardians__guardian=user.guardian_profile)
            school = get_current_school(request) or user.school
            published = ReportCard.objects.filter(
                school=school, status=ReportCard.Status.PUBLISHED,
                student_id=OuterRef('student_id'), term_id=OuterRef('term_id'),
            )
            qs = qs.filter(Exists(published))
        elif user.role == User.Roles.STAFF and hasattr(user, 'staff_profile'):
            staff = user.staff_profile
            qs = qs.filter(subject__in=staff.assigned_subjects.all())

        if params.get('term'):
            qs = qs.filter(term_id=int_param(params, 'term'))
        if params.get('student'):
            qs = qs.filter(student_id=int_param(params, 'student'))
        if params.get('subject'):
            qs = qs.filter(subject_id=int_param(params, 'subject'))
        if params.get('class'):
            qs = qs.filter(school_class_id=int_param(params, 'class'))

        return qs.select_related('student', 'subject', 'term', 'school_class')


class EnhancedReportCardViewSet(viewsets.ModelViewSet):
    queryset = ReportCard.objects.all()
    serializer_class = ReportCardSerializer
    permission_classes = [IsAuthenticated, perms.IsSchoolStaffOrReadOnly]

    def get_queryset(self):
        qs = filter_by_school(self.queryset, self.request)
        user = self.request.user
        params = self.request.query_params

        if user.role == User.Roles.STUDENT and hasattr(user, 'student_profile'):
            qs = qs.filter(student=user.student_profile, status=ReportCard.Status.PUBLISHED)
        elif user.role == User.Roles.PARENT and hasattr(user, 'guardian_profile'):
            qs = qs.filter(
                student__guardians__guardian=user.guardian_profile,
                status=ReportCard.Status.PUBLISHED,
            )
        elif user.role == User.Roles.GUEST:
            qs = qs.filter(status=ReportCard.Status.PUBLISHED)

        if params.get('term'):
            qs = qs.filter(term_id=int_param(params, 'term'))
        if params.get('student'):
            qs = qs.filter(student_id=int_param(params, 'student'))
        if params.get('class'):
            qs = qs.filter(school_class_id=int_param(params, 'class'))

        return qs.select_related('student', 'term', 'term__session', 'school_class')

    def update(self, request, *args, **kwargs):
        # 'status' (publish/release) may only change via the publish/unpublish/
        # release-class actions, which are restricted to IsResultPublisher.
        # request.data populates request._full_data, which is what the
        # serializer reads — reassign it to strip the field.
        user = request.user
        if 'status' in request.data and not (
            user.is_superuser or user.role in perms.IsResultPublisher.RELEASE_ROLES
        ):
            request._full_data = {
                k: v for k, v in request.data.items() if k != 'status'
            }
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        """Download a PDF report card."""
        rc = self.get_object()
        from .pdf_reports import generate_report_card_pdf
        try:
            pdf_bytes = generate_report_card_pdf(rc)
        except Exception as exc:
            logger.exception('PDF generation error: %s', exc)
            return Response({'error': str(exc)}, status=500)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        student_name = f"{rc.student.first_name}_{rc.student.last_name}".replace(' ', '_')
        response['Content-Disposition'] = (
            f'attachment; filename="report_card_{student_name}_{rc.term.name}.pdf"'
        )
        return response

    @action(detail=True, methods=['post'], url_path='publish',
            permission_classes=[perms.IsResultPublisher])
    def publish(self, request, pk=None):
        """Release a report card to the student/parent portals."""
        rc = self.get_object()
        rc.status = ReportCard.Status.PUBLISHED
        rc.save(update_fields=['status'])
        audit(request, 'report_card.publish', rc)
        return Response({'detail': 'Report card published.', 'status': rc.status})

    @action(detail=True, methods=['post'], url_path='unpublish',
            permission_classes=[perms.IsResultPublisher])
    def unpublish(self, request, pk=None):
        """Withdraw a released report card back to draft."""
        rc = self.get_object()
        rc.status = ReportCard.Status.DRAFT
        rc.save(update_fields=['status'])
        audit(request, 'report_card.unpublish', rc)
        return Response({'detail': 'Report card returned to draft.', 'status': rc.status})

    @action(detail=False, methods=['post'], url_path='release-class',
            permission_classes=[perms.IsResultPublisher])
    def release_class(self, request):
        """Release (or withdraw) report cards for a whole class + term."""
        school = get_current_school(request)
        term_id = request.data.get('term_id')
        class_id = request.data.get('class_id')
        publish = request.data.get('publish', True)
        qs = ReportCard.objects.filter(school=school)
        if term_id:
            qs = qs.filter(term_id=term_id)
        if class_id:
            qs = qs.filter(school_class_id=class_id)
        new_status = (
            ReportCard.Status.PUBLISHED if publish else ReportCard.Status.DRAFT
        )
        count = qs.update(status=new_status)
        audit(request, 'report_card.release_class', None,
              {'term_id': term_id, 'class_id': class_id,
               'publish': bool(publish), 'count': count})
        return Response({'detail': f'{count} report cards set to {new_status}.', 'count': count})

    @action(detail=False, methods=['get'], url_path='preview')
    def preview(self, request):
        """Editable preview: computed results for a class+term, with release state."""
        school = get_current_school(request)
        term_id = request.query_params.get('term_id')
        class_id = request.query_params.get('class_id')
        qs = ResultSummary.objects.filter(school=school)
        cards = ReportCard.objects.filter(school=school)
        if term_id:
            qs = qs.filter(term_id=term_id)
            cards = cards.filter(term_id=term_id)
        if class_id:
            qs = qs.filter(school_class_id=class_id)
            cards = cards.filter(school_class_id=class_id)
        card_by_student = {c.student_id: c for c in cards}
        out = {}
        for row in qs.select_related('student', 'subject'):
            entry = out.setdefault(row.student_id, {
                'student': row.student_id,
                'student_name': f'{row.student.first_name} {row.student.last_name}',
                'subjects': [],
                'report_card': None,
            })
            entry['subjects'].append(ResultSummarySerializer(row).data)
            card = card_by_student.get(row.student_id)
            if card:
                entry['report_card'] = ReportCardSerializer(card).data
        return Response({'results': list(out.values())})

    @action(detail=False, methods=['post'], url_path='compute', permission_classes=[perms.IsSchoolAdmin])
    def compute(self, request):
        """Trigger result computation for a term."""
        term_id = request.data.get('term_id')
        school = get_current_school(request)
        if not term_id:
            return Response({'error': 'term_id is required.'}, status=400)
        try:
            term = Term.objects.get(pk=term_id, school=school)
        except Term.DoesNotExist:
            return Response({'error': 'Term not found.'}, status=404)

        try:
            count = compute_results_for_term(school, term)
        except Exception as exc:
            logger.exception('Result computation error: %s', exc)
            return Response({'error': str(exc)}, status=500)

        return Response({
            'detail': f'Results computed for {count} student-subject entries.',
            'term': term.name,
        })


# ---------------------------------------------------------------------------
# Financial PDF download views
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fee_collection_pdf(request):
    """Download Fee Collection Summary PDF."""
    school = get_current_school(request)
    term_id = request.query_params.get('term_id')
    if not term_id:
        return Response({'error': 'term_id is required.'}, status=400)
    try:
        term = Term.objects.get(pk=term_id, school=school)
    except Term.DoesNotExist:
        return Response({'error': 'Term not found.'}, status=404)

    from .pdf_reports import generate_fee_collection_summary
    pdf_bytes = generate_fee_collection_summary(school, term)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="fee_summary_{term.name}.pdf"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def debtors_pdf(request):
    """Download Outstanding Debtors PDF."""
    school = get_current_school(request)
    term_id = request.query_params.get('term_id')
    if not term_id:
        return Response({'error': 'term_id is required.'}, status=400)
    try:
        term = Term.objects.get(pk=term_id, school=school)
    except Term.DoesNotExist:
        return Response({'error': 'Term not found.'}, status=404)

    from .pdf_reports import generate_debtors_report
    pdf_bytes = generate_debtors_report(school, term)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="debtors_{term.name}.pdf"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def income_expenditure_pdf(request):
    """Download Income & Expenditure PDF."""
    school = get_current_school(request)
    term_id = request.query_params.get('term_id')
    if not term_id:
        return Response({'error': 'term_id is required.'}, status=400)
    try:
        term = Term.objects.get(pk=term_id, school=school)
    except Term.DoesNotExist:
        return Response({'error': 'Term not found.'}, status=404)

    from .pdf_reports import generate_income_expenditure
    pdf_bytes = generate_income_expenditure(school, term)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="income_expenditure_{term.name}.pdf"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_ledger_pdf(request):
    """Download student fee ledger PDF."""
    school = get_current_school(request)
    student_id = request.query_params.get('student_id')
    term_id = request.query_params.get('term_id')
    if not student_id:
        return Response({'error': 'student_id is required.'}, status=400)

    from students.models import Student
    try:
        student = Student.objects.get(pk=student_id, school=school)
    except Student.DoesNotExist:
        return Response({'error': 'Student not found.'}, status=404)

    term = None
    if term_id:
        try:
            term = Term.objects.get(pk=term_id, school=school)
        except Term.DoesNotExist:
            pass

    from .pdf_reports import generate_student_fee_ledger
    pdf_bytes = generate_student_fee_ledger(school, student, term)
    name = f"{student.first_name}_{student.last_name}".replace(' ', '_')
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ledger_{name}.pdf"'
    return response
