"""Homework assignments, submissions, and live lesson API views."""
from django.utils import timezone
from rest_framework import serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.utils import filter_by_school, get_current_school
from homework.models import Assignment, LiveLesson, Submission
from accounts.models import User


class AssignmentSerializer(drf_serializers.ModelSerializer):
    class_name = drf_serializers.CharField(source='school_class.name', read_only=True)
    subject_name = drf_serializers.CharField(source='subject.name', read_only=True)
    teacher_name = drf_serializers.CharField(source='teacher.full_name', read_only=True, allow_null=True)

    class Meta:
        model = Assignment
        fields = [
            'id', 'school', 'school_class', 'class_name', 'subject', 'subject_name',
            'teacher', 'teacher_name', 'term', 'title', 'description', 'type',
            'due_date', 'max_points', 'attachment', 'is_published',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'school', 'teacher', 'created_at', 'updated_at']


class SubmissionSerializer(drf_serializers.ModelSerializer):
    student_name = drf_serializers.SerializerMethodField()
    assignment_title = drf_serializers.CharField(source='assignment.title', read_only=True)
    max_points = drf_serializers.DecimalField(
        source='assignment.max_points', read_only=True, max_digits=6, decimal_places=2)
    file_url = drf_serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            'id', 'school', 'assignment', 'assignment_title', 'student', 'student_name',
            'content', 'file', 'file_url', 'submitted_at', 'status', 'score',
            'feedback', 'max_points',
            'graded_at', 'graded_by', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'school', 'submitted_at', 'graded_at', 'graded_by',
            'created_at', 'updated_at',
        ]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_file_url(self, obj):
        return obj.file.url if obj.file else None


class LiveLessonSerializer(drf_serializers.ModelSerializer):
    class_name = drf_serializers.CharField(source='school_class.name', read_only=True)
    subject_name = drf_serializers.CharField(source='subject.name', read_only=True)
    teacher_name = drf_serializers.CharField(source='teacher.full_name', read_only=True, allow_null=True)
    jitsi_url = drf_serializers.ReadOnlyField()

    class Meta:
        model = LiveLesson
        fields = [
            'id', 'school', 'school_class', 'class_name', 'subject', 'subject_name',
            'teacher', 'teacher_name', 'title', 'description', 'scheduled_at',
            'duration_minutes', 'jitsi_room_name', 'jitsi_url', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'school', 'teacher', 'jitsi_room_name', 'jitsi_url', 'created_at', 'updated_at']


class AssignmentViewSet(viewsets.ModelViewSet):
    queryset = Assignment.objects.all()
    serializer_class = AssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = filter_by_school(self.queryset, self.request)
        user = self.request.user
        if user.role == User.Roles.STUDENT and hasattr(user, 'student_profile'):
            # Students see assignments for their enrolled classes
            enroll = user.student_profile.enrollments.select_related('section__school_class')
            classes = [e.section.school_class_id for e in enroll]
            qs = qs.filter(school_class__in=classes, is_published=True)
        elif user.role == User.Roles.PARENT and hasattr(user, 'guardian_profile'):
            # Parents see assignments for their children's classes
            from students.models import StudentEnrollment
            classes = StudentEnrollment.objects.filter(
                student__guardians__guardian=user.guardian_profile,
                school=user.school,
            ).values_list('section__school_class_id', flat=True)
            qs = qs.filter(school_class__in=classes, is_published=True)
        return qs

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        serializer.save(school=school, teacher=self.request.user)

    @action(detail=True, methods=['get'], url_path='submissions')
    def submissions(self, request, pk=None):
        assignment = self.get_object()
        subs = Submission.objects.filter(school=assignment.school, assignment=assignment)
        return Response(SubmissionSerializer(subs, many=True).data)


class SubmissionViewSet(viewsets.ModelViewSet):
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = filter_by_school(self.queryset, self.request)
        user = self.request.user
        params = self.request.query_params
        if params.get('assignment'):
            from core.utils import int_param
            qs = qs.filter(assignment_id=int_param(params, 'assignment'))
        if user.role == User.Roles.STUDENT and hasattr(user, 'student_profile'):
            qs = qs.filter(student=user.student_profile)
        elif user.role == User.Roles.PARENT and hasattr(user, 'guardian_profile'):
            qs = qs.filter(student__guardians__guardian=user.guardian_profile)
        return qs.select_related('student', 'assignment')

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        user = self.request.user
        student = getattr(user, 'student_profile', None)
        if student is None:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                'Your account is not linked to a student record — ask your '
                'school admin to link it before submitting work.')
        from datetime import date
        assignment = serializer.validated_data.get('assignment')
        late = assignment and date.today() > assignment.due_date
        serializer.save(
            school=school,
            student=student,
            status=Submission.Status.LATE if late else Submission.Status.SUBMITTED,
        )

    def _require_staff(self, request):
        if request.user.role in (User.Roles.STUDENT, User.Roles.PARENT, User.Roles.GUEST):
            return Response(
                {'error': 'Only staff can grade submissions.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    @action(detail=True, methods=['post'], url_path='grade')
    def grade(self, request, pk=None):
        denied = self._require_staff(request)
        if denied:
            return denied
        submission = self.get_object()
        score = request.data.get('score')
        feedback = request.data.get('feedback', '')
        if score is None or score == '':
            return Response({'score': 'A score is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from decimal import Decimal
            score = Decimal(str(score))
        except Exception:
            return Response({'score': 'Score must be a number.'}, status=status.HTTP_400_BAD_REQUEST)
        max_pts = submission.assignment.max_points
        if score < 0 or (max_pts is not None and score > max_pts):
            return Response(
                {'score': f'Score must be between 0 and {max_pts}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        submission.score = score
        submission.feedback = feedback
        submission.graded_at = timezone.now()
        submission.graded_by = request.user
        submission.status = Submission.Status.GRADED
        submission.save()
        from core.utils import audit
        audit(request, 'submission.grade', submission,
              {'score': str(score), 'assignment': submission.assignment.title})
        return Response(SubmissionSerializer(submission).data)

    @action(detail=True, methods=['post'], url_path='return')
    def return_to_student(self, request, pk=None):
        """Mark a graded submission as returned to the student."""
        denied = self._require_staff(request)
        if denied:
            return denied
        submission = self.get_object()
        if submission.status != Submission.Status.GRADED:
            return Response(
                {'error': 'Grade the submission first — only graded work can be returned.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        submission.status = Submission.Status.RETURNED
        submission.save(update_fields=['status'])
        return Response(SubmissionSerializer(submission).data)


class LiveLessonViewSet(viewsets.ModelViewSet):
    queryset = LiveLesson.objects.all()
    serializer_class = LiveLessonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return filter_by_school(self.queryset, self.request)

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        serializer.save(school=school, teacher=self.request.user)

    @action(detail=True, methods=['post'], url_path='go-live')
    def go_live(self, request, pk=None):
        lesson = self.get_object()
        lesson.status = LiveLesson.Status.LIVE
        lesson.save(update_fields=['status'])
        return Response({'jitsi_url': lesson.jitsi_url, 'status': 'live'})

    @action(detail=True, methods=['post'], url_path='end')
    def end(self, request, pk=None):
        lesson = self.get_object()
        lesson.status = LiveLesson.Status.COMPLETED
        lesson.save(update_fields=['status'])
        return Response({'status': 'completed'})
