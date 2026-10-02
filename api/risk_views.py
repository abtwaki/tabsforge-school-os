"""
Part 5 — Academic Early-Warning AI.

Endpoints:
  POST /api/ai/run-risk-analysis/    — analyse all students in current term, create AtRiskFlag records
  GET  /api/ai/at-risk-students/     — list current at-risk flags with details
  POST /api/ai/at-risk-students/<pk>/resolve/  — mark a flag resolved
"""
import logging
from decimal import Decimal

from django.db.models import Avg, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers, viewsets

from api.permissions import IsTenantScoped
from api.viewsets import get_current_school
from gradebook.models import AtRiskFlag, ResultSummary
from notifications.models import InAppNotification
from schools.models import Term

logger = logging.getLogger(__name__)


# Configurable thresholds
ATTENDANCE_THRESHOLD = 75.0   # percent — below this is flagged
GRADE_DECLINE_TERMS = 2       # consecutive terms with declining average to trigger flag
MIN_GRADE_DECLINE = 5.0       # minimum total drop (percentage points) across consecutive terms


class AtRiskFlagSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField(read_only=True)
    student_admission_number = serializers.SerializerMethodField(read_only=True)
    student_class = serializers.SerializerMethodField(read_only=True)
    term_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AtRiskFlag
        fields = [
            'id', 'student', 'student_name', 'student_admission_number', 'student_class',
            'term', 'term_name', 'flag_type', 'reason', 'details',
            'resolved', 'notified_teacher', 'notified_parent', 'flagged_at',
        ]
        read_only_fields = ['id', 'flagged_at']

    def get_student_name(self, obj):
        s = obj.student
        return f"{s.first_name} {s.last_name}"

    def get_student_admission_number(self, obj):
        return obj.student.admission_number

    def get_student_class(self, obj):
        en = obj.student.enrollments.filter(status='active').order_by('-id').first()
        return en.section.school_class.name if en else None

    def get_term_name(self, obj):
        return obj.term.name if obj.term else None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def run_risk_analysis(request):
    """
    Run the early-warning analysis for the current (or specified) term.
    Creates/updates AtRiskFlag records and notifies teachers.
    Body: { "term_id": optional, "attendance_threshold": optional float, "notify_parents": optional bool }
    """
    school = get_current_school(request)
    if not school:
        return Response({'detail': 'School context required.'}, status=400)

    term_id = request.data.get('term_id')
    attendance_threshold = float(request.data.get('attendance_threshold', ATTENDANCE_THRESHOLD))
    notify_parents = bool(request.data.get('notify_parents', False))

    # Get term
    if term_id:
        try:
            term = Term.objects.get(pk=term_id, school=school)
        except Term.DoesNotExist:
            return Response({'detail': 'Term not found.'}, status=404)
    else:
        term = Term.objects.filter(school=school, is_current=True).first()
        if not term:
            return Response({'detail': 'No current term found.'}, status=404)

    flags_created = 0
    flags_updated = 0

    from students.models import Student
    from attendance.models import Attendance

    # ── Bulk grade-decline analysis using a single annotated query ────────────
    # Get last 2 terms before the current term, ordered most-recent first
    past_terms = list(
        Term.objects.filter(school=school)
        .exclude(pk=term.pk)
        .order_by('-start_date')[:2]
    )

    # Current term averages per student
    current_avgs = dict(
        ResultSummary.objects.filter(school=school, term=term)
        .values('student_id')
        .annotate(avg=Avg('total_score'))
        .values_list('student_id', 'avg')
    )
    students_analysed = len(current_avgs)

    # Previous term averages per student (if available)
    prev_avgs = {}
    if past_terms:
        prev_avgs = dict(
            ResultSummary.objects.filter(school=school, term=past_terms[0])
            .values('student_id')
            .annotate(avg=Avg('total_score'))
            .values_list('student_id', 'avg')
        )

    # Flag grade decline
    for sid, cur_avg in current_avgs.items():
        if sid not in prev_avgs:
            continue
        prev_avg = float(prev_avgs[sid])
        cur_avg_f = float(cur_avg)
        decline = prev_avg - cur_avg_f
        if decline >= MIN_GRADE_DECLINE:
            try:
                student = Student.objects.get(pk=sid)
            except Student.DoesNotExist:
                continue
            reason = (
                f"Average score dropped from {prev_avg:.1f}% to {cur_avg_f:.1f}% "
                f"({decline:.1f} point decline)."
            )
            details = {'prev_average': prev_avg, 'current_average': cur_avg_f, 'decline': decline}
            flag, created = AtRiskFlag.objects.update_or_create(
                school=school, student=student, term=term,
                flag_type=AtRiskFlag.FlagType.GRADE_DECLINE,
                defaults={'reason': reason, 'details': details, 'resolved': False},
            )
            if created:
                flags_created += 1
            else:
                flags_updated += 1
            _notify_teacher(flag, student, school)
            if notify_parents:
                _notify_parent(flag, student, school)

    # ── Bulk attendance analysis ──────────────────────────────────────────────
    # Get total and present counts per student in one query
    att_totals = dict(
        Attendance.objects.filter(school=school)
        .values('student_id')
        .annotate(total=Count('id'))
        .values_list('student_id', 'total')
    )
    att_present = dict(
        Attendance.objects.filter(school=school, status='present')
        .values('student_id')
        .annotate(present=Count('id'))
        .values_list('student_id', 'present')
    )

    for sid in current_avgs:
        total_days = att_totals.get(sid, 0)
        if total_days < 5:  # Skip students with too few records
            continue
        present_days = att_present.get(sid, 0)
        att_pct = (present_days / total_days) * 100
        if att_pct < attendance_threshold:
            try:
                student = Student.objects.get(pk=sid)
            except Student.DoesNotExist:
                continue
            reason = (
                f"Attendance is {att_pct:.1f}% "
                f"({present_days}/{total_days} days present), below the "
                f"{attendance_threshold:.0f}% threshold."
            )
            details = {
                'present': present_days, 'total': total_days,
                'percentage': round(att_pct, 1),
                'threshold': attendance_threshold,
            }
            flag, created = AtRiskFlag.objects.update_or_create(
                school=school, student=student, term=term,
                flag_type=AtRiskFlag.FlagType.LOW_ATTENDANCE,
                defaults={'reason': reason, 'details': details, 'resolved': False},
            )
            if created:
                flags_created += 1
            else:
                flags_updated += 1
            _notify_teacher(flag, student, school)
            if notify_parents:
                _notify_parent(flag, student, school)

    return Response({
        'detail': f'Risk analysis complete for {term.name}.',
        'students_analysed': students_analysed,
        'flags_created': flags_created,
        'flags_updated': flags_updated,
        'term': term.name,
        'attendance_threshold': attendance_threshold,
    })


def _notify_teacher(flag: AtRiskFlag, student, school):
    """Send in-app notification to the student's class teacher."""
    if flag.notified_teacher:
        return
    try:
        en = student.enrollments.filter(status='active').order_by('-id').first()
        teacher = None
        if en:
            from staff.models import Staff
            teacher_staff = Staff.objects.filter(
                school=school, department__icontains='class'
            ).first()
            if teacher_staff:
                teacher = teacher_staff.user

        if not teacher:
            from accounts.models import User
            teacher = User.objects.filter(school=school, role__in=['staff', 'school_admin']).first()

        if teacher:
            InAppNotification.objects.create(
                school=school,
                user=teacher,
                title='At-Risk Student Alert',
                message=f"{student.first_name} {student.last_name} has been flagged: {flag.reason}",
                notification_type='alert',
                related_object_type='at_risk_flag',
                related_object_id=flag.pk,
            )
            flag.notified_teacher = True
            flag.save(update_fields=['notified_teacher'])
    except Exception as e:
        logger.error("_notify_teacher error: %s", e)


def _notify_parent(flag: AtRiskFlag, student, school):
    """Optionally notify the student's guardian."""
    if flag.notified_parent:
        return
    try:
        from students.models import GuardianStudent
        from communications.channels import dispatch_notification
        links = GuardianStudent.objects.filter(student=student).select_related('guardian__user')
        for link in links:
            guardian_user = link.guardian.user if hasattr(link.guardian, 'user') else None
            if guardian_user:
                dispatch_notification(
                    guardian_user,
                    'Academic Alert for Your Child',
                    f"Dear {link.guardian.name},\n\n"
                    f"We want to bring to your attention that "
                    f"{student.first_name} {student.last_name} "
                    f"requires some additional support:\n\n"
                    f"{flag.reason}\n\n"
                    f"Please contact the school to discuss next steps.\n\n"
                    f"-- TabsForge School OS"
                )
        flag.notified_parent = True
        flag.save(update_fields=['notified_parent'])
    except Exception as e:
        logger.error("_notify_parent error: %s", e)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def at_risk_students(request):
    """List at-risk students for the current school/term."""
    school = get_current_school(request)
    if not school:
        return Response({'detail': 'School context required.'}, status=400)

    term_id = request.query_params.get('term_id')
    resolved = request.query_params.get('resolved', 'false').lower() == 'true'

    qs = AtRiskFlag.objects.filter(school=school, resolved=resolved)
    if term_id:
        qs = qs.filter(term_id=term_id)
    else:
        current_term = Term.objects.filter(school=school, is_current=True).first()
        if current_term:
            qs = qs.filter(term=current_term)

    qs = qs.select_related('student', 'term')
    return Response({
        'count': qs.count(),
        'results': AtRiskFlagSerializer(qs, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resolve_risk_flag(request, pk=None):
    """Mark an at-risk flag as resolved."""
    school = get_current_school(request)
    try:
        flag = AtRiskFlag.objects.get(pk=pk, school=school)
    except AtRiskFlag.DoesNotExist:
        return Response({'detail': 'Flag not found.'}, status=404)
    flag.resolved = True
    flag.save(update_fields=['resolved'])
    return Response({'detail': 'Flag resolved.'})
