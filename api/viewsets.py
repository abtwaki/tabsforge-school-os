"""DRF viewsets for the TabsForge API."""
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.models import User
from academics.models import Class, ClassSubject, Section, Subject, Timetable
from attendance.models import Attendance
from communications.models import Announcement, Notice
from core.permissions import IsTenantScoped
from core.utils import audit, date_param, dependent_counts, filter_by_school, get_current_school, int_param
from finance.models import Expense, FeeCategory, FeeStructure, Invoice, Payment
from gradebook.models import Assessment, Grade, ReportCard
from hostel.models import Hostel, HostelAllocation, Room
from library.models import Book, BorrowRecord
from notifications.models import EmailMessage, InAppNotification, SMSMessage
from schools.models import AcademicSession, School, Term
from staff.models import Staff
from students.models import Guardian, GuardianStudent, Student, StudentEnrollment
from transport.models import Route, Vehicle, VehicleAssignment

from . import permissions as perms
from . import serializers as ser


class TenantModelViewSet(viewsets.ModelViewSet):
    """
    Base viewset that enforces tenant isolation via ``filter_by_school``.

    Subclasses can override ``get_queryset`` and ``perform_create`` to
    inject ``school`` automatically.
    """
    permission_classes = [perms.IsTenantAdminOrReadOnly, perms.ReadOnlyForGuest]

    def get_queryset(self):
        qs = filter_by_school(super().get_queryset(), self.request)
        # Archived objects must stay reachable for restore/dependents/destroy.
        if self.action in ('restore', 'dependents', 'destroy'):
            return qs
        archived = self.request.query_params.get('archived')
        if archived == 'only':
            return qs.filter(is_archived=True)
        if archived in ('with', 'all'):
            return qs
        return qs.filter(is_archived=False)

    def destroy(self, request, *args, **kwargs):
        """Archive the record (soft delete). ``?permanent=1`` hard-deletes but
        only when nothing else references it."""
        obj = self.get_object()
        deps = dependent_counts(obj)
        if request.query_params.get('permanent') in ('1', 'true', 'yes'):
            if deps:
                return Response(
                    {'error': 'This record is linked to other records and cannot be '
                              'permanently deleted. Archive it instead — linked '
                              'records keep working.',
                     'dependents': deps},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            audit(request, 'record.delete_permanent', obj)
            obj.delete()
            return Response({'detail': 'Permanently deleted.'})
        if not obj.is_archived:
            obj.is_archived = True
            obj.archived_at = timezone.now()
            obj.save(update_fields=['is_archived', 'archived_at'])
        audit(request, 'record.archive', obj, {'dependents': deps})
        text = 'Archived — restore anytime from the archived view.'
        if deps:
            text = 'Archived — linked records keep working and everything is restored together.'
        return Response({'detail': text, 'dependents': deps})

    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """Bring an archived record back."""
        obj = self.get_object()
        obj.is_archived = False
        obj.archived_at = None
        obj.save(update_fields=['is_archived', 'archived_at'])
        audit(request, 'record.restore', obj)
        return Response({'detail': 'Restored.'})

    @action(detail=True, methods=['get'], url_path='dependents')
    def dependents(self, request, pk=None):
        """Report what other records are tied to this one."""
        return Response({'dependents': dependent_counts(self.get_object())})

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        if school is None:
            # Super admins must pass ?school_id= to write into a tenant.
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                'No school context. Platform admins must pass ?school_id=<id> '
                'when creating school-scoped records.'
            )
        serializer.save(school=school)


class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = ser.SchoolSerializer
    permission_classes = [perms.IsSchoolAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == User.Roles.SUPER_ADMIN:
            return self.queryset
        if user.school_id:
            return self.queryset.filter(pk=user.school_id)
        return self.queryset.none()

    def create(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Schools are created through the onboarding endpoint.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def perform_update(self, serializer):
        # Only platform super admins may change privileged school fields:
        # tier, status, module entitlements. School admins can change
        # branding fields (logo, colors, address, contact_info).
        user = self.request.user
        if not (user.is_superuser or user.role == User.Roles.SUPER_ADMIN):
            for field in ('tier', 'status', 'enabled_modules', 'subdomain', 'group'):
                serializer.validated_data.pop(field, None)
        serializer.save()
        audit(self.request, 'school.update', serializer.instance,
              {'fields': sorted(serializer.validated_data.keys())})

    def _platform_admin(self, request):
        return request.user.is_superuser or request.user.role == User.Roles.SUPER_ADMIN

    @action(detail=True, methods=['post'], url_path='suspend')
    def suspend(self, request, pk=None):
        """Suspend an entire school — blocks all its users from logging in."""
        if not self._platform_admin(request):
            return Response({'error': 'Platform admins only.'}, status=403)
        school = self.get_object()
        school.status = School.Status.SUSPENDED
        school.save(update_fields=['status'])
        audit(request, 'school.suspend', school)
        return Response({'detail': f'{school.name} suspended.', 'status': school.status})

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        """Re-activate a suspended school."""
        if not self._platform_admin(request):
            return Response({'error': 'Platform admins only.'}, status=403)
        school = self.get_object()
        school.status = School.Status.ACTIVE
        school.save(update_fields=['status'])
        audit(request, 'school.activate', school)
        return Response({'detail': f'{school.name} activated.', 'status': school.status})

    @action(detail=True, methods=['post'], url_path='create-admin')
    def create_admin(self, request, pk=None):
        """Create a school_admin (school super admin) account for this school."""
        if not self._platform_admin(request):
            return Response({'error': 'Platform admins only.'}, status=403)
        school = self.get_object()
        email = (request.data.get('email') or '').strip().lower()
        password = request.data.get('password') or ''
        if not email or not password:
            return Response({'error': 'email and password are required.'}, status=400)
        if User.objects.filter(email=email).exists():
            return Response({'error': 'A user with this email already exists.'}, status=400)
        user = User.objects.create_user(
            email=email, password=password,
            first_name=request.data.get('first_name', ''),
            last_name=request.data.get('last_name', ''),
            role=User.Roles.SCHOOL_ADMIN, school=school,
        )
        audit(request, 'user.create_admin', user, {'school': school.name})
        return Response(ser.UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='report-template')
    def report_template(self, request, pk=None):
        """Upload the school's report-card format file (PDF/DOCX/XLSX).

        For XLSX/DOCX, grading-band tables (min, max, label, remark) are
        parsed and adopted into the school's default grading scheme.
        For PDF, the file is stored as the school's reference template.
        """
        school = self.get_object()
        user = request.user
        if not (
            self._platform_admin(request)
            or (user.school_id == school.id and user.role in {
                User.Roles.SCHOOL_ADMIN, User.Roles.PRINCIPAL, User.Roles.EXAM_OFFICER,
            })
        ):
            return Response({'error': 'Not permitted.'}, status=403)
        upload = request.FILES.get('file')
        if not upload:
            return Response({'error': 'file is required.'}, status=400)
        ext = upload.name.rsplit('.', 1)[-1].lower()
        if ext not in {'pdf', 'docx', 'xlsx', 'xls', 'csv'}:
            return Response({'error': 'Upload a PDF, DOCX, XLSX or CSV file.'}, status=400)

        school.report_template = upload
        adopted = self._adopt_template(school, upload, ext)
        config = dict(school.report_config or {})
        config['template_name'] = upload.name
        config['adopted'] = adopted
        school.report_config = config
        school.save(update_fields=['report_template', 'report_config'])
        return Response({
            'detail': 'Report template uploaded.',
            'adopted': adopted,
            'report_config': school.report_config,
            'report_template_url': school.report_template.url,
        })

    @action(detail=True, methods=['patch'], url_path='report-config')
    def report_config_update(self, request, pk=None):
        """Update the school's report-card layout config (JSON merge)."""
        school = self.get_object()
        user = request.user
        if not (
            self._platform_admin(request)
            or (user.school_id == school.id and user.role in {
                User.Roles.SCHOOL_ADMIN, User.Roles.PRINCIPAL, User.Roles.EXAM_OFFICER,
            })
        ):
            return Response({'error': 'Not permitted.'}, status=403)
        allowed = {
            'show_position', 'show_class_size', 'show_grade_points',
            'show_teacher_comment', 'show_principal_comment',
            'show_attendance_summary', 'footer_note', 'signature_labels',
        }
        config = dict(school.report_config or {})
        config.update({k: v for k, v in request.data.items() if k in allowed})

        # Score weights: {ca1: %, ca2: %, exam: %} — must be positive numbers.
        if 'weights' in request.data:
            w = request.data['weights'] or {}
            try:
                weights = {k: float(w[k]) for k in ('ca1', 'ca2', 'exam')}
            except (KeyError, TypeError, ValueError):
                return Response(
                    {'error': 'weights must contain ca1, ca2 and exam numbers.'},
                    status=400)
            if min(weights.values()) < 0:
                return Response({'error': 'weights cannot be negative.'}, status=400)
            config['weights'] = weights

        # Grade bands: [{min, label, remark, points}] — replaces scheme lookup.
        if 'grade_bands' in request.data:
            bands = request.data['grade_bands']
            if not isinstance(bands, list):
                return Response({'error': 'grade_bands must be a list.'}, status=400)
            clean = []
            for b in bands:
                try:
                    clean.append({
                        'min': float(b['min']),
                        'label': str(b['label'])[:10],
                        'remark': str(b.get('remark', ''))[:50],
                        'points': float(b.get('points', 0)),
                    })
                except (KeyError, TypeError, ValueError):
                    return Response(
                        {'error': 'Each grade band needs min, label, remark, points.'},
                        status=400)
            config['grade_bands'] = clean

        school.report_config = config
        school.save(update_fields=['report_config'])
        return Response({'report_config': config})

    @staticmethod
    def _adopt_template(school, upload, ext):
        """Parse an uploaded sheet/doc for grading bands and import them.

        Returns a summary dict describing what was adopted.
        """
        from gradebook.models import GradeBoundary, GradingScheme

        rows = []
        try:
            if ext in {'xlsx', 'xls', 'csv'}:
                import openpyxl
                wb = openpyxl.load_workbook(upload, read_only=True, data_only=True)
                for sheet in wb.worksheets:
                    for row in sheet.iter_rows(values_only=True):
                        rows.append([c for c in row if c is not None])
                wb.close()
            elif ext == 'docx':
                import docx
                doc = docx.Document(upload)
                for table in doc.tables:
                    for row in table.rows:
                        rows.append([cell.text.strip() for cell in row.cells])
        except Exception:
            return {'bands': 0, 'note': 'Stored as reference; no gradable table detected.'}

        # Detect band rows: first two cells numeric (min, max), then label + remark.
        bands = []
        for row in rows:
            if len(row) < 3:
                continue
            try:
                lo, hi = float(row[0]), float(row[1])
            except (TypeError, ValueError):
                continue
            label = str(row[2])[:10]
            remark = str(row[3])[:50] if len(row) > 3 else ''
            points = int(float(row[4])) if len(row) > 4 else 0
            bands.append((lo, hi, label, remark, points))

        if not bands:
            return {'bands': 0, 'note': 'Stored as reference; no grading-band table detected.'}

        scheme = GradingScheme.objects.filter(school=school, is_default=True).first()
        if not scheme:
            scheme = GradingScheme.objects.create(
                school=school, name='Imported scheme', is_default=True,
            )
        created = 0
        for lo, hi, label, remark, points in bands:
            _, was_created = GradeBoundary.objects.update_or_create(
                school=school, scheme=scheme, label=label,
                defaults={
                    'min_score': lo, 'max_score': hi,
                    'remark': remark, 'points': points,
                },
            )
            created += was_created
        return {
            'bands': len(bands), 'created': created,
            'scheme': scheme.name,
            'note': f'Adopted {len(bands)} grading bands into scheme "{scheme.name}".',
        }


class AcademicSessionViewSet(TenantModelViewSet):
    queryset = AcademicSession.objects.all()
    serializer_class = ser.AcademicSessionSerializer


class TermViewSet(TenantModelViewSet):
    queryset = Term.objects.all()
    serializer_class = ser.TermSerializer


class ClassViewSet(TenantModelViewSet):
    queryset = Class.objects.all()
    serializer_class = ser.ClassSerializer


class SectionViewSet(TenantModelViewSet):
    queryset = Section.objects.all()
    serializer_class = ser.SectionSerializer


class SubjectViewSet(TenantModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = ser.SubjectSerializer


class ClassSubjectViewSet(TenantModelViewSet):
    queryset = ClassSubject.objects.all()
    serializer_class = ser.ClassSubjectSerializer


TEACHING_SCOPE_ROLES = {
    User.Roles.STAFF, User.Roles.TEACHER, User.Roles.FORM_TEACHER,
    User.Roles.EXAM_OFFICER, User.Roles.PRINCIPAL, User.Roles.VICE_PRINCIPAL,
}


def _is_teacherish(user):
    """True for roles that teach/mark attendance (may carry a staff_profile)."""
    return user.role in TEACHING_SCOPE_ROLES


class TimetableViewSet(TenantModelViewSet):
    queryset = Timetable.objects.all()
    serializer_class = ser.TimetableSerializer
    permission_classes = [perms.IsSchoolStaffOrReadOnly, perms.ReadOnlyForGuest]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params
        if params.get('section'):
            qs = qs.filter(section_id=int_param(params, 'section'))
        if params.get('teacher'):
            qs = qs.filter(teacher_id=int_param(params, 'teacher'))
        if _is_teacherish(user) and hasattr(user, 'staff_profile'):
            staff = user.staff_profile
            qs = qs.filter(
                Q(teacher=user)
                | Q(section__school_class__in=staff.assigned_classes.all())
                | Q(subject__in=staff.assigned_subjects.all())
            )
        return qs.select_related('section', 'section__school_class', 'subject', 'teacher')


class StudentViewSet(TenantModelViewSet):
    queryset = Student.objects.all()
    serializer_class = ser.StudentSerializer

    def get_queryset(self):
        from django.db.models import Prefetch
        qs = super().get_queryset()
        qs = qs.prefetch_related(
            Prefetch(
                'enrollments',
                queryset=StudentEnrollment.objects.filter(
                    status=StudentEnrollment.Status.ACTIVE,
                ).select_related('section', 'section__school_class'),
                to_attr='active_enrollments',
            ),
            'guardians__guardian',
        )
        user = self.request.user
        params = self.request.query_params
        if params.get('section'):
            qs = qs.filter(enrollments__section_id=int_param(params, 'section'),
                           enrollments__status=StudentEnrollment.Status.ACTIVE)
        if params.get('school_class'):
            qs = qs.filter(enrollments__section__school_class_id=int_param(params, 'school_class'),
                           enrollments__status=StudentEnrollment.Status.ACTIVE)
        if user.role == User.Roles.STUDENT and hasattr(user, 'student_profile'):
            qs = qs.filter(pk=user.student_profile.pk)
        elif user.role == User.Roles.PARENT and hasattr(user, 'guardian_profile'):
            qs = qs.filter(guardians__guardian=user.guardian_profile)
        elif _is_teacherish(user) and hasattr(user, 'staff_profile'):
            staff = user.staff_profile
            qs = qs.filter(
                enrollments__section__school_class__in=staff.assigned_classes.all()
            )
        return qs.distinct()


class GuardianViewSet(TenantModelViewSet):
    queryset = Guardian.objects.all()
    serializer_class = ser.GuardianSerializer


class GuardianStudentViewSet(TenantModelViewSet):
    queryset = GuardianStudent.objects.all()
    serializer_class = ser.GuardianStudentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == User.Roles.PARENT and hasattr(user, 'guardian_profile'):
            qs = qs.filter(guardian=user.guardian_profile)
        return qs


class StudentEnrollmentViewSet(TenantModelViewSet):
    queryset = StudentEnrollment.objects.all()
    serializer_class = ser.StudentEnrollmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params
        if params.get('section'):
            qs = qs.filter(section_id=int_param(params, 'section'))
        if params.get('school_class'):
            qs = qs.filter(section__school_class_id=int_param(params, 'school_class'))
        if params.get('session'):
            qs = qs.filter(session_id=int_param(params, 'session'))
        if params.get('term'):
            qs = qs.filter(term_id=int_param(params, 'term'))
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if user.role == User.Roles.STUDENT and hasattr(user, 'student_profile'):
            qs = qs.filter(student=user.student_profile)
        elif user.role == User.Roles.PARENT and hasattr(user, 'guardian_profile'):
            qs = qs.filter(student__guardians__guardian=user.guardian_profile)
        elif _is_teacherish(user) and hasattr(user, 'staff_profile'):
            staff = user.staff_profile
            qs = qs.filter(section__school_class__in=staff.assigned_classes.all())
        return qs.select_related('student', 'section', 'section__school_class', 'session', 'term')


class StaffViewSet(TenantModelViewSet):
    queryset = Staff.objects.all()
    serializer_class = ser.StaffSerializer
    permission_classes = [perms.IsHROrReadOnly, perms.ReadOnlyForGuest]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if _is_teacherish(user) and hasattr(user, 'staff_profile'):
            qs = qs.filter(pk=user.staff_profile.pk)
        return qs.select_related('user')


class AttendanceViewSet(TenantModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = ser.AttendanceSerializer
    permission_classes = [perms.IsSchoolStaffOrReadOnly, perms.ReadOnlyForGuest]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params
        if params.get('date'):
            qs = qs.filter(date=date_param(params, 'date'))
        if params.get('date_from'):
            qs = qs.filter(date__gte=date_param(params, 'date_from'))
        if params.get('date_to'):
            qs = qs.filter(date__lte=date_param(params, 'date_to'))
        if params.get('school_class'):
            qs = qs.filter(school_class_id=int_param(params, 'school_class'))
        if params.get('student'):
            qs = qs.filter(student_id=int_param(params, 'student'))
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if user.role == User.Roles.STUDENT and hasattr(user, 'student_profile'):
            qs = qs.filter(student=user.student_profile)
        elif user.role == User.Roles.PARENT and hasattr(user, 'guardian_profile'):
            qs = qs.filter(student__guardians__guardian=user.guardian_profile)
        elif _is_teacherish(user) and hasattr(user, 'staff_profile'):
            staff = user.staff_profile
            qs = qs.filter(school_class__in=staff.assigned_classes.all())
        return qs.select_related('student', 'school_class', 'marked_by')

    def perform_create(self, serializer):
        serializer.save(school=get_current_school(self.request), marked_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='bulk-mark')
    def bulk_mark(self, request):
        """Atomically mark attendance for a whole class on a date.

        Payload: {school_class, date, marks: [{student, status, remarks}]}
        Creates or updates one row per student (unique per school+student+class+date).
        """
        from django.db import transaction
        school = get_current_school(request)
        if school is None:
            raise PermissionDenied('No active school.')
        class_id = request.data.get('school_class')
        date = request.data.get('date')
        marks = request.data.get('marks') or []
        if not class_id or not date or not isinstance(marks, list) or not marks:
            return Response({'detail': 'school_class, date and marks are required.'}, status=400)
        if not Class.objects.filter(pk=class_id, school=school).exists():
            return Response({'detail': 'Class not found.'}, status=404)
        valid_statuses = {c[0] for c in Attendance.Status.choices}
        valid_students = set(
            Student.objects.filter(
                school=school, pk__in=[m.get('student') for m in marks if m.get('student')],
            ).values_list('pk', flat=True)
        )
        saved, errors = 0, []
        with transaction.atomic():
            for m in marks:
                st = m.get('status', 'present')
                sid = m.get('student')
                if st not in valid_statuses or not sid:
                    errors.append({'student': sid, 'error': 'Invalid student or status.'})
                    continue
                if sid not in valid_students:
                    errors.append({'student': sid, 'error': 'Student not found.'})
                    continue
                Attendance.objects.update_or_create(
                    school=school, student_id=sid, school_class_id=class_id, date=date,
                    defaults={
                        'status': st,
                        'remarks': m.get('remarks', ''),
                        'marked_by': request.user,
                    },
                )
                saved += 1
        return Response({'saved': saved, 'errors': errors})


class AssessmentViewSet(TenantModelViewSet):
    queryset = Assessment.objects.all()
    serializer_class = ser.AssessmentSerializer
    permission_classes = [perms.IsSchoolStaffOrReadOnly, perms.ReadOnlyForGuest]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params
        if params.get('term'):
            qs = qs.filter(term_id=int_param(params, 'term'))
        if params.get('subject'):
            qs = qs.filter(subject_id=int_param(params, 'subject'))
        if params.get('school_class'):
            qs = qs.filter(school_class_id=int_param(params, 'school_class'))
        if _is_teacherish(user) and hasattr(user, 'staff_profile'):
            staff = user.staff_profile
            qs = qs.filter(
                Q(school_class__in=staff.assigned_classes.all())
                | Q(subject__in=staff.assigned_subjects.all())
            )
        return qs.select_related('term', 'subject', 'school_class')


class GradeViewSet(TenantModelViewSet):
    queryset = Grade.objects.all()
    serializer_class = ser.GradeSerializer
    permission_classes = [perms.IsSchoolStaffOrReadOnly, perms.ReadOnlyForGuest]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params
        if params.get('assessment'):
            qs = qs.filter(assessment_id=int_param(params, 'assessment'))
        if params.get('student'):
            qs = qs.filter(student_id=int_param(params, 'student'))
        if user.role == User.Roles.STUDENT and hasattr(user, 'student_profile'):
            qs = qs.filter(student=user.student_profile)
        elif user.role == User.Roles.PARENT and hasattr(user, 'guardian_profile'):
            qs = qs.filter(student__guardians__guardian=user.guardian_profile)
        return qs.select_related('student', 'assessment', 'assessment__subject')

    @action(detail=False, methods=['post'], url_path='bulk-enter')
    def bulk_enter(self, request):
        """Atomically enter/update scores for an assessment.

        Payload: {assessment, scores: [{student, score, remarks}]}
        """
        from django.db import transaction
        from django.core.exceptions import ValidationError as DjangoValidationError
        school = get_current_school(request)
        if school is None:
            raise PermissionDenied('No active school.')
        assessment_id = request.data.get('assessment')
        scores = request.data.get('scores') or []
        if not assessment_id or not isinstance(scores, list) or not scores:
            return Response({'detail': 'assessment and scores are required.'}, status=400)
        try:
            assessment = Assessment.objects.get(pk=assessment_id, school=school)
        except Assessment.DoesNotExist:
            return Response({'detail': 'Assessment not found.'}, status=404)
        valid_students = set(
            Student.objects.filter(
                school=school, pk__in=[s.get('student') for s in scores if s.get('student')],
            ).values_list('pk', flat=True)
        )
        saved, errors = 0, []
        with transaction.atomic():
            for s in scores:
                sid, score = s.get('student'), s.get('score')
                if sid is None or score is None or score == '':
                    errors.append({'student': sid, 'error': 'Missing student or score.'})
                    continue
                if sid not in valid_students:
                    errors.append({'student': sid, 'error': 'Student not found.'})
                    continue
                try:
                    score = float(score)
                    if score < 0 or score > float(assessment.max_score):
                        raise ValueError
                except (TypeError, ValueError):
                    errors.append({'student': sid, 'error': f'Score must be 0–{assessment.max_score}.'})
                    continue
                Grade.objects.update_or_create(
                    school=school, assessment=assessment, student_id=sid,
                    defaults={'score': score, 'remarks': s.get('remarks', '')},
                )
                saved += 1
        audit(request, 'grade.bulk_enter', assessment,
              {'saved': saved, 'errors': len(errors)})
        return Response({'saved': saved, 'errors': errors})


class ReportCardViewSet(TenantModelViewSet):
    queryset = ReportCard.objects.all()
    serializer_class = ser.ReportCardSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == User.Roles.STUDENT and hasattr(user, 'student_profile'):
            qs = qs.filter(student=user.student_profile)
        elif user.role == User.Roles.PARENT and hasattr(user, 'guardian_profile'):
            qs = qs.filter(student__guardians__guardian=user.guardian_profile)
        return qs


class FeeCategoryViewSet(TenantModelViewSet):
    queryset = FeeCategory.objects.all()
    serializer_class = ser.FeeCategorySerializer
    permission_classes = [perms.IsAccountant]


class FeeStructureViewSet(TenantModelViewSet):
    queryset = FeeStructure.objects.all()
    serializer_class = ser.FeeStructureSerializer
    permission_classes = [perms.IsAccountant]


class InvoiceViewSet(TenantModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = ser.InvoiceSerializer
    permission_classes = [perms.IsFinanceOrFamilyReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params
        if params.get('student'):
            qs = qs.filter(student_id=int_param(params, 'student'))
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if user.role == User.Roles.PARENT and hasattr(user, 'guardian_profile'):
            qs = qs.filter(student__guardians__guardian=user.guardian_profile)
        elif user.role == User.Roles.STUDENT and hasattr(user, 'student_profile'):
            qs = qs.filter(student=user.student_profile)
        return qs.select_related('student', 'term')

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        number = (self.request.data.get('invoice_number') or '').strip()
        if not number:
            from django.db import transaction
            from schools.models import School
            with transaction.atomic():
                # Lock the school row so concurrent invoice creation serialises
                # on it — counting without a lock produces duplicate numbers
                # when the school has few or zero invoices.
                locked_school = School.objects.select_for_update().get(pk=school.pk)
                count = Invoice.objects.filter(school=locked_school).count() + 1
                year = timezone.now().year
                sub = (school.subdomain or 'SCH').upper() if school else 'SCH'
                number = f"INV/{sub}/{year}/{count:05d}"
        serializer.save(school=school, invoice_number=number)
        audit(self.request, 'invoice.create', serializer.instance)

    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk(self, request):
        """Generate invoices for a whole class/section/everyone in one go.

        Body: {
            "term": <id>,                     # required
            "school_class": <id>,             # optional — all classes if omitted
            "section": <id>,                  # optional — narrower than class
            "due_date": "YYYY-MM-DD",         # required
            "status": "sent" | "draft",       # default "sent"
            "notes": "...",                   # optional
        }
        Amount per student = sum of FeeStructure rows for the student's
        class + this term. Students with an existing non-cancelled invoice
        for the term are skipped, so re-running is safe.
        """
        school = get_current_school(request)
        if school is None:
            return Response(
                {'error': 'No school context — pick a school first.'}, status=400)
        term_id = request.data.get('term')
        class_id = request.data.get('school_class')
        section_id = request.data.get('section')
        due_date = request.data.get('due_date')
        inv_status = request.data.get('status', Invoice.Status.SENT)
        notes = request.data.get('notes', '')
        if not term_id or not due_date:
            return Response({'error': 'term and due_date are required.'}, status=400)
        if inv_status not in (Invoice.Status.SENT, Invoice.Status.DRAFT):
            return Response({'error': 'status must be "sent" or "draft".'}, status=400)
        try:
            term = Term.objects.get(pk=term_id, school=school)
        except (Term.DoesNotExist, ValueError, TypeError):
            return Response({'term': 'Term not found in this school.'}, status=404)

        enrollments = StudentEnrollment.objects.filter(
            school=school, term=term, status=StudentEnrollment.Status.ACTIVE,
        ).select_related('student', 'section__school_class')
        if section_id:
            enrollments = enrollments.filter(section_id=section_id)
        elif class_id:
            enrollments = enrollments.filter(section__school_class_id=class_id)

        if not enrollments.exists():
            return Response({
                'error': 'No active enrollments found for that scope — enroll '
                         'students into this term first (Students → Enrollments).',
            }, status=400)

        # Pre-compute each class's bill for the term.
        from collections import defaultdict
        class_totals = defaultdict(lambda: {'total': 0, 'items': []})
        for fs in FeeStructure.objects.filter(school=school, term=term):
            class_totals[fs.school_class_id]['total'] += fs.amount
            class_totals[fs.school_class_id]['items'].append(fs.name)

        already = set(
            Invoice.objects.filter(school=school, term=term)
            .exclude(status=Invoice.Status.CANCELLED)
            .values_list('student_id', flat=True)
        )

        from django.db import transaction
        created, skipped, total_billed = [], [], 0
        with transaction.atomic():
            locked = School.objects.select_for_update().get(pk=school.pk)
            count = Invoice.objects.filter(school=locked).count()
            year = timezone.now().year
            sub = (school.subdomain or 'SCH').upper()
            for enr in enrollments:
                student = enr.student
                name = f'{student.first_name} {student.last_name}'
                if student.id in already:
                    skipped.append({'student': name, 'reason': 'already invoiced this term'})
                    continue
                bill = class_totals.get(enr.section.school_class_id)
                if not bill or not bill['total']:
                    skipped.append({
                        'student': name,
                        'reason': f'no fee structure for {enr.section.school_class.name} this term',
                    })
                    continue
                count += 1
                inv = Invoice.objects.create(
                    school=school, student=student, term=term,
                    invoice_number=f'INV/{sub}/{year}/{count:05d}',
                    due_date=due_date, total_amount=bill['total'],
                    status=inv_status,
                    notes=notes or ' · '.join(bill['items']),
                )
                created.append({'id': inv.id, 'student': name,
                                'invoice_number': inv.invoice_number,
                                'total_amount': str(inv.total_amount)})
                total_billed += inv.total_amount

        from core.utils import audit
        audit(request, 'invoice.bulk_create', term, {
            'created': len(created), 'skipped': len(skipped),
            'class_id': class_id, 'section_id': section_id,
        })
        return Response({
            'created': len(created), 'skipped': skipped,
            'invoices': created, 'total_billed': str(total_billed),
        }, status=201 if created else 200)


class PaymentViewSet(TenantModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = ser.PaymentSerializer
    permission_classes = [perms.IsFinanceOrFamilyReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params
        if params.get('invoice'):
            qs = qs.filter(invoice_id=int_param(params, 'invoice'))
        if user.role == User.Roles.PARENT and hasattr(user, 'guardian_profile'):
            qs = qs.filter(invoice__student__guardians__guardian=user.guardian_profile)
        return qs.select_related('invoice', 'recorded_by')

    def perform_create(self, serializer):
        """Record a payment atomically with its receipt + invoice update.

        The post_save signal (receipt creation, receipt-number sequence,
        invoice balance/status update) runs inside this transaction, so a
        payment can never exist without its receipt or with a half-applied
        balance.
        """
        from django.db import transaction
        school = get_current_school(self.request)
        with transaction.atomic():
            serializer.save(school=school, recorded_by=self.request.user)
        audit(self.request, 'payment.record', serializer.instance,
              {'amount': str(serializer.instance.amount)})


class AnnouncementViewSet(TenantModelViewSet):
    queryset = Announcement.objects.all()
    serializer_class = ser.AnnouncementSerializer
    permission_classes = [perms.IsSchoolStaffOrReadOnly, perms.ReadOnlyForGuest]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        # Non-authoring roles only see published announcements targeted at them
        # (or everyone). Authors/admins see everything.
        privileged = (
            user.is_superuser
            or user.role in {User.Roles.SUPER_ADMIN, *perms.ADMIN_SCOPE}
        )
        if not privileged:
            # Role keys this user should match: their own role plus umbrella
            # labels used by the UI ('staff' covers all school-staff roles).
            matched = {user.role}
            if user.role in TEACHING_SCOPE_ROLES:
                matched |= {User.Roles.STAFF, 'teacher', 'staff'}
            qs = qs.filter(status=Announcement.Status.PUBLISHED)
            q = Q(target_roles=[])
            for key in matched:
                q |= Q(target_roles__contains=[key])
            qs = qs.filter(q)
        return qs.select_related('author')

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        if school is None and not (
            self.request.user.is_superuser
            or self.request.user.role == User.Roles.SUPER_ADMIN
        ):
            raise PermissionDenied('Cannot create an announcement without an active school.')
        instance = serializer.save(author=self.request.user, school=school)
        if instance.status == Announcement.Status.PUBLISHED:
            _notify_users(instance, self.request.user)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.status == Announcement.Status.PUBLISHED:
            _notify_users(instance, self.request.user)


class NoticeViewSet(TenantModelViewSet):
    queryset = Notice.objects.all()
    serializer_class = ser.NoticeSerializer
    permission_classes = [perms.IsSchoolStaffOrReadOnly, perms.ReadOnlyForGuest]

    def perform_create(self, serializer):
        serializer.save(school=get_current_school(self.request), author=self.request.user)


class BookViewSet(TenantModelViewSet):
    queryset = Book.objects.all()
    serializer_class = ser.BookSerializer
    permission_classes = [perms.IsLibrarianOrReadOnly, perms.ReadOnlyForGuest]

    def get_queryset(self):
        self._check_library_tier()
        return super().get_queryset()

    def _check_library_tier(self):
        school = getattr(self.request, 'current_school', None)
        if school and school.tier not in {School.Tiers.BLOOM, School.Tiers.SUMMIT}:
            raise PermissionDenied('Library is only available on Bloom tier or above.')


class BorrowRecordViewSet(TenantModelViewSet):
    queryset = BorrowRecord.objects.all()
    serializer_class = ser.BorrowRecordSerializer
    permission_classes = [perms.IsLibrarianOrReadOnly, perms.ReadOnlyForGuest]

    def get_queryset(self):
        self._check_library_tier()
        qs = super().get_queryset()
        user = self.request.user
        if user.role == User.Roles.STUDENT and hasattr(user, 'student_profile'):
            qs = qs.filter(student=user.student_profile)
        return qs

    def _check_library_tier(self):
        school = getattr(self.request, 'current_school', None)
        if school and school.tier not in {School.Tiers.BLOOM, School.Tiers.SUMMIT}:
            raise PermissionDenied('Library is only available on Bloom tier or above.')


class RouteViewSet(TenantModelViewSet):
    queryset = Route.objects.all()
    serializer_class = ser.RouteSerializer

    def get_queryset(self):
        self._check_transport_tier()
        return super().get_queryset()

    def _check_transport_tier(self):
        school = getattr(self.request, 'current_school', None)
        if school and school.tier != School.Tiers.SUMMIT:
            raise PermissionDenied('Transport is only available on Summit tier.')


class VehicleViewSet(TenantModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = ser.VehicleSerializer

    def get_queryset(self):
        self._check_transport_tier()
        return super().get_queryset()

    def _check_transport_tier(self):
        school = getattr(self.request, 'current_school', None)
        if school and school.tier != School.Tiers.SUMMIT:
            raise PermissionDenied('Transport is only available on Summit tier.')


class VehicleAssignmentViewSet(TenantModelViewSet):
    queryset = VehicleAssignment.objects.all()
    serializer_class = ser.VehicleAssignmentSerializer

    def get_queryset(self):
        self._check_transport_tier()
        return super().get_queryset()

    def _check_transport_tier(self):
        school = getattr(self.request, 'current_school', None)
        if school and school.tier != School.Tiers.SUMMIT:
            raise PermissionDenied('Transport is only available on Summit tier.')


class HostelViewSet(TenantModelViewSet):
    queryset = Hostel.objects.all()
    serializer_class = ser.HostelSerializer

    def get_queryset(self):
        self._check_hostel_tier()
        return super().get_queryset()

    def _check_hostel_tier(self):
        school = getattr(self.request, 'current_school', None)
        if school and school.tier != School.Tiers.SUMMIT:
            raise PermissionDenied('Hostel is only available on Summit tier.')


class RoomViewSet(TenantModelViewSet):
    queryset = Room.objects.all()
    serializer_class = ser.RoomSerializer

    def get_queryset(self):
        self._check_hostel_tier()
        return super().get_queryset()

    def _check_hostel_tier(self):
        school = getattr(self.request, 'current_school', None)
        if school and school.tier != School.Tiers.SUMMIT:
            raise PermissionDenied('Hostel is only available on Summit tier.')


class HostelAllocationViewSet(TenantModelViewSet):
    queryset = HostelAllocation.objects.all()
    serializer_class = ser.HostelAllocationSerializer

    def get_queryset(self):
        self._check_hostel_tier()
        qs = super().get_queryset()
        user = self.request.user
        if user.role == User.Roles.STUDENT and hasattr(user, 'student_profile'):
            qs = qs.filter(student=user.student_profile)
        return qs

    def _check_hostel_tier(self):
        school = getattr(self.request, 'current_school', None)
        if school and school.tier != School.Tiers.SUMMIT:
            raise PermissionDenied('Hostel is only available on Summit tier.')


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = ser.UserSerializer
    permission_classes = [perms.IsUserManager]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role == user.Roles.SUPER_ADMIN:
            # Honor the platform-admin school-context switcher (?school_id=).
            school_id = int_param(self.request.query_params, 'school_id')
            if school_id:
                return qs.filter(school_id=school_id)
            return qs
        return qs.filter(school=user.school)

    def get_serializer_class(self):
        if self.action == 'create':
            return ser.UserCreateSerializer
        return ser.UserSerializer

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        user = self.request.user
        # Platform super admins may create accounts for a specific school
        # (e.g. a school_admin for a school) by passing `school` in the payload.
        if (user.is_superuser or user.role == User.Roles.SUPER_ADMIN) and self.request.data.get('school'):
            school = School.objects.get(pk=self.request.data['school'])
        serializer.save(school=school)
        audit(self.request, 'user.create', serializer.instance,
              {'role': serializer.instance.role})

    def perform_update(self, serializer):
        before_role = serializer.instance.role
        before_active = serializer.instance.is_active
        serializer.save()
        changes = {}
        if serializer.instance.role != before_role:
            changes['role'] = [before_role, serializer.instance.role]
        if serializer.instance.is_active != before_active:
            changes['is_active'] = [before_active, serializer.instance.is_active]
        audit(self.request, 'user.update', serializer.instance, changes)

    def create(self, request, *args, **kwargs):
        """Validate with UserCreateSerializer, respond with UserSerializer."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        out = ser.UserSerializer(serializer.instance)
        headers = self.get_success_headers(out.data)
        return Response(out.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'], url_path='suspend')
    def suspend(self, request, pk=None):
        """Suspend/block a user account (sets is_active=False)."""
        target = self.get_object()
        if target == request.user:
            return Response({'error': 'You cannot suspend your own account.'}, status=400)
        if target.role == User.Roles.SUPER_ADMIN and not request.user.is_superuser:
            return Response({'error': 'Cannot suspend a super admin.'}, status=403)
        target.is_active = False
        target.save(update_fields=['is_active'])
        audit(request, 'user.suspend', target)
        return Response({'detail': f'{target.email} suspended.', 'is_active': False})

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        """Re-activate a suspended/blocked account."""
        target = self.get_object()
        target.is_active = True
        target.save(update_fields=['is_active'])
        audit(request, 'user.activate', target)
        return Response({'detail': f'{target.email} activated.', 'is_active': True})

    @action(detail=True, methods=['post'], url_path='set-password')
    def set_password(self, request, pk=None):
        """Admin-set a user's password (e.g. user lost access to email +
        authenticator). Invalidates all existing sessions."""
        target = self.get_object()
        if target.role == User.Roles.SUPER_ADMIN and not request.user.is_superuser:
            return Response({'error': 'Cannot reset a super admin password.'}, status=403)
        if target == request.user:
            return Response({'error': 'Use the profile page to change your own password.'}, status=400)
        password = request.data.get('password') or ''
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_password(password, user=target)
        except DjangoValidationError as exc:
            return Response({'error': ' '.join(exc.messages)}, status=400)
        target.set_password(password)
        target.save(update_fields=['password'])
        Token.objects.filter(user=target).delete()
        audit(request, 'user.reset_password', target)
        return Response({'detail': f'Password reset for {target.email}.'})

    def destroy(self, request, *args, **kwargs):
        target = self.get_object()
        if target == request.user:
            return Response({'error': 'You cannot delete your own account.'}, status=400)
        if target.role == User.Roles.SUPER_ADMIN and not request.user.is_superuser:
            return Response({'error': 'Cannot delete a super admin.'}, status=403)
        return super().destroy(request, *args, **kwargs)


class EmailMessageViewSet(TenantModelViewSet):
    queryset = EmailMessage.objects.all()
    serializer_class = ser.EmailMessageSerializer


class SMSMessageViewSet(TenantModelViewSet):
    queryset = SMSMessage.objects.all()
    serializer_class = ser.SMSMessageSerializer


def _role_map(role):
    """Expand an announcement audience label into concrete User.Roles values."""
    role = (role or '').lower()
    if role in {'teacher', 'staff'}:
        return set(TEACHING_SCOPE_ROLES)
    if role == 'admin':
        return {User.Roles.SCHOOL_ADMIN, User.Roles.PRINCIPAL}
    return {role}


def _notify_users(announcement, sender):
    """Create an InAppNotification for each user targeted by an announcement."""
    target_roles = announcement.target_roles or []
    if not target_roles:
        users = User.objects.filter(school=announcement.school)
    else:
        roles = set()
        for r in target_roles:
            roles |= _role_map(r)
        users = User.objects.filter(role__in=roles)
    if announcement.school:
        users = users.filter(school=announcement.school)
    notifications = [
        InAppNotification(
            recipient=user,
            sender=sender,
            title=announcement.title,
            message=announcement.content,
            school=announcement.school,
        )
        for user in users
    ]
    if notifications:
        InAppNotification.objects.bulk_create(notifications)


class ExpenseViewSet(TenantModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ser.ExpenseSerializer
    permission_classes = [perms.IsAccountant]

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        serializer.save(school=school, recorded_by=self.request.user)


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = InAppNotification.objects.all()
    serializer_class = ser.InAppNotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(recipient=self.request.user)

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'detail': 'Marked as read.'})

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})



class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only audit trail. School leaders see their own school's events;
    platform admins see everything (optionally scoped via ?school_id=)."""
    serializer_class = ser.AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from core.models import AuditLog
        qs = AuditLog.objects.select_related('actor', 'school')
        user = self.request.user
        if user.is_superuser or user.role == User.Roles.SUPER_ADMIN:
            sid = int_param(self.request.query_params, 'school_id')
            if sid:
                qs = qs.filter(school_id=sid)
        elif user.role in {
            User.Roles.SCHOOL_ADMIN, User.Roles.PRINCIPAL,
            User.Roles.VICE_PRINCIPAL, User.Roles.GROUP_OWNER,
        }:
            qs = qs.filter(school=user.school)
        else:
            return qs.none()
        params = self.request.query_params
        if params.get('action'):
            qs = qs.filter(action__icontains=params['action'])
        if params.get('object_type'):
            qs = qs.filter(object_type__icontains=params['object_type'])
        if params.get('actor'):
            qs = qs.filter(actor_email__icontains=params['actor'])
        if date_param(params, 'date_from'):
            qs = qs.filter(created_at__date__gte=date_param(params, 'date_from'))
        if date_param(params, 'date_to'):
            qs = qs.filter(created_at__date__lte=date_param(params, 'date_to'))
        return qs
