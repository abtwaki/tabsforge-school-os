"""DRF serializers for the TabsForge API."""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import User
from academics.models import Class, ClassSubject, Section, Subject, Timetable
from attendance.models import Attendance
from communications.models import Announcement, Notice
from finance.models import Expense, FeeCategory, FeeStructure, Invoice, Payment
from gradebook.models import Assessment, Grade, ReportCard
from hostel.models import Hostel, HostelAllocation, Room
from library.models import Book, BorrowRecord
from notifications.models import EmailMessage, InAppNotification, SMSMessage
from schools.models import AcademicSession, School, Term
from staff.models import Staff
from students.models import Guardian, GuardianStudent, Student, StudentEnrollment
from transport.models import Route, Vehicle, VehicleAssignment


class TenantSerializer(serializers.ModelSerializer):
    """ModelSerializer that forces the tenant ``school`` field read-only.

    The school is injected by the viewset's ``perform_create`` from the
    authenticated user's tenant context — clients can never set it, which
    also prevents cross-tenant forgery via crafted payloads.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school_field = self.fields.get('school')
        if school_field is not None:
            school_field.read_only = True


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='full_name', read_only=True)
    tier = serializers.SerializerMethodField()
    school_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'first_name', 'last_name', 'full_name',
            'role', 'school', 'school_name', 'tier', 'phone', 'whatsapp_number',
            'notification_channel', 'is_support', 'totp_enabled', 'is_guest',
            'is_active', 'date_joined', 'tutorial_completed',
        ]
        read_only_fields = [
            'id', 'date_joined', 'name', 'school_name', 'tier', 'full_name',
            'email', 'school', 'is_support', 'totp_enabled', 'is_guest',
        ]

    def validate_role(self, value):
        """Prevent privilege escalation: only super admins may assign
        super_admin/group_owner roles."""
        request = self.context.get('request')
        if value in {User.Roles.SUPER_ADMIN, User.Roles.GROUP_OWNER}:
            if not request or not (
                request.user.is_superuser
                or request.user.role == User.Roles.SUPER_ADMIN
            ):
                raise serializers.ValidationError('You cannot assign this role.')
        return value

    def get_tier(self, obj):
        return obj.school.tier if obj.school else None

    def get_school_name(self, obj):
        return obj.school.name if obj.school else None


class UserCreateSerializer(TenantSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'role', 'school', 'phone', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class SchoolSerializer(serializers.ModelSerializer):
    student_count = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    report_template_url = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = [
            'id', 'name', 'logo', 'address', 'contact_info', 'tier', 'subdomain',
            'custom_domain', 'primary_color', 'secondary_color', 'status',
            'enabled_modules', 'report_template', 'report_template_url',
            'report_config', 'student_count', 'user_count',
            'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'report_template_url', 'is_archived', 'archived_at']

    def get_student_count(self, obj):
        return obj.students.count()

    def get_user_count(self, obj):
        return obj.users.count()

    def get_report_template_url(self, obj):
        return obj.report_template.url if obj.report_template else None


class AcademicSessionSerializer(TenantSerializer):
    class Meta:
        model = AcademicSession
        fields = ['id', 'school', 'name', 'start_date', 'end_date', 'is_current', 'created_at', 'updated_at', 'is_archived', 'archived_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class TermSerializer(TenantSerializer):
    class Meta:
        model = Term
        fields = ['id', 'school', 'session', 'name', 'start_date', 'end_date', 'is_current', 'created_at', 'updated_at', 'is_archived', 'archived_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class ClassSerializer(TenantSerializer):
    class Meta:
        model = Class
        fields = ['id', 'school', 'name', 'code', 'created_at', 'updated_at', 'is_archived', 'archived_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class SectionSerializer(TenantSerializer):
    class_name = serializers.CharField(source='school_class.name', read_only=True)
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = ['id', 'school', 'school_class', 'class_name', 'display_name', 'name', 'room', 'capacity', 'created_at', 'updated_at', 'is_archived', 'archived_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']

    def get_display_name(self, obj):
        return f"{obj.school_class.name} – {obj.name}"


class SubjectSerializer(TenantSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'school', 'name', 'code', 'description', 'created_at', 'updated_at', 'is_archived', 'archived_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class ClassSubjectSerializer(TenantSerializer):
    class Meta:
        model = ClassSubject
        fields = ['id', 'school', 'school_class', 'subject', 'teacher', 'created_at', 'updated_at', 'is_archived', 'archived_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class TimetableSerializer(TenantSerializer):
    section_name = serializers.CharField(source='section.name', read_only=True)
    class_name = serializers.CharField(source='section.school_class.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.full_name', read_only=True, allow_null=True)

    class Meta:
        model = Timetable
        fields = [
            'id', 'school', 'section', 'section_name', 'class_name', 'subject',
            'subject_name', 'teacher', 'teacher_name', 'day',
            'start_time', 'end_time', 'room', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class StudentSerializer(TenantSerializer):
    name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    section_id = serializers.SerializerMethodField()
    # Write-only helpers so one POST/PUT can place the pupil in a class and
    # attach or create a parent record at the same time.
    section = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.select_related('school_class'),
        required=False, write_only=True,
    )
    guardian = serializers.PrimaryKeyRelatedField(
        queryset=Guardian.objects.all(), required=False, write_only=True,
    )
    guardian_first_name = serializers.CharField(required=False, write_only=True, allow_blank=True)
    guardian_last_name = serializers.CharField(required=False, write_only=True, allow_blank=True)
    guardian_phone = serializers.CharField(required=False, write_only=True, allow_blank=True)
    guardian_email = serializers.EmailField(required=False, write_only=True, allow_blank=True)
    guardian_relationship = serializers.ChoiceField(
        choices=Guardian.Relationships.choices,
        default=Guardian.Relationships.GUARDIAN,
        required=False, write_only=True,
    )

    class Meta:
        model = Student
        fields = [
            'id', 'school', 'admission_number', 'user', 'first_name', 'last_name',
            'name', 'class_name', 'section_id', 'date_of_birth', 'gender',
            'address', 'enrollment_date',
            'section', 'guardian', 'guardian_first_name', 'guardian_last_name',
            'guardian_phone', 'guardian_email', 'guardian_relationship',
            'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'enrollment_date', 'created_at', 'updated_at', 'is_archived', 'archived_at']

    def _current_enrollment(self, obj):
        active = getattr(obj, 'active_enrollments', None)
        if active is not None:
            return active[0] if active else None
        return (obj.enrollments.filter(status=StudentEnrollment.Status.ACTIVE)
                .select_related('section', 'section__school_class').first())

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_class_name(self, obj):
        enr = self._current_enrollment(obj)
        return str(enr.section) if enr else None

    def get_section_id(self, obj):
        enr = self._current_enrollment(obj)
        return enr.section_id if enr else None

    def _pop_links(self, validated_data):
        return {
            'section': validated_data.pop('section', None),
            'guardian': validated_data.pop('guardian', None),
            'g_first': validated_data.pop('guardian_first_name', ''),
            'g_last': validated_data.pop('guardian_last_name', ''),
            'g_phone': validated_data.pop('guardian_phone', ''),
            'g_email': validated_data.pop('guardian_email', ''),
            'g_rel': validated_data.pop('guardian_relationship', Guardian.Relationships.GUARDIAN),
        }

    def _apply_links(self, student, links):
        """Enrol the pupil into a section and attach/create a guardian."""
        school = student.school
        section = links['section']
        if section is not None:
            if section.school_id != school.id:
                raise serializers.ValidationError({'section': 'Section belongs to a different school.'})
            term = (
                Term.objects.filter(school=school, is_current=True).first()
                or Term.objects.filter(school=school).order_by('-start_date').first()
            )
            if term is None:
                raise serializers.ValidationError({
                    'section': 'No academic term exists for this school yet — create a term before enrolling students.',
                })
            StudentEnrollment.objects.update_or_create(
                school=school,
                student=student,
                session=term.session,
                term=term,
                defaults={'section': section, 'status': StudentEnrollment.Status.ACTIVE},
            )

        guardian = links['guardian']
        if guardian is not None and guardian.school_id != school.id:
            raise serializers.ValidationError({'guardian': 'Guardian belongs to a different school.'})
        if guardian is None and (links['g_first'] or links['g_last'] or links['g_phone'] or links['g_email']):
            guardian = Guardian.objects.create(
                school=school,
                first_name=links['g_first'] or 'Parent',
                last_name=links['g_last'],
                phone=links['g_phone'],
                email=links['g_email'],
                relationship=links['g_rel'],
            )
        if guardian is not None:
            GuardianStudent.objects.get_or_create(
                school=school,
                guardian=guardian,
                student=student,
                defaults={'relationship': links['g_rel'], 'is_primary': True},
            )

    def _check_links(self, school, links):
        """Reject bad links before any write happens (create or update)."""
        if links['section'] is not None:
            if school is not None and links['section'].school_id != school.id:
                raise serializers.ValidationError({'section': 'Section belongs to a different school.'})
            if school is not None and not Term.objects.filter(school=school).exists():
                raise serializers.ValidationError({
                    'section': 'No academic term exists for this school yet — create a term before enrolling students.',
                })
        if links['guardian'] is not None and school is not None and links['guardian'].school_id != school.id:
            raise serializers.ValidationError({'guardian': 'Guardian belongs to a different school.'})

    def create(self, validated_data):
        links = self._pop_links(validated_data)
        self._check_links(validated_data.get('school'), links)
        student = super().create(validated_data)
        self._apply_links(student, links)
        return student

    def update(self, instance, validated_data):
        links = self._pop_links(validated_data)
        self._check_links(instance.school, links)
        student = super().update(instance, validated_data)
        self._apply_links(student, links)
        # The enrollment may have just changed — drop the prefetched cache so
        # the response serializes fresh data.
        student.__dict__.pop('active_enrollments', None)
        return student


class GuardianSerializer(TenantSerializer):
    full_name = serializers.SerializerMethodField()
    wards = serializers.SerializerMethodField()
    # Optional: link the guardian to an existing student on save.
    student = serializers.PrimaryKeyRelatedField(
        queryset=Student.objects.all(), required=False, write_only=True,
    )

    class Meta:
        model = Guardian
        fields = [
            'id', 'school', 'user', 'first_name', 'last_name', 'full_name', 'phone',
            'email', 'relationship', 'address', 'wards', 'student',
            'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def get_wards(self, obj):
        return ', '.join(str(link.student) for link in obj.wards.all()) or None

    def _link_student(self, guardian, student):
        if student is None:
            return
        if student.school_id != guardian.school_id:
            raise serializers.ValidationError({'student': 'Student belongs to a different school.'})
        GuardianStudent.objects.get_or_create(
            school=guardian.school,
            guardian=guardian,
            student=student,
            defaults={'relationship': guardian.relationship, 'is_primary': True},
        )

    def create(self, validated_data):
        student = validated_data.pop('student', None)
        guardian = super().create(validated_data)
        self._link_student(guardian, student)
        return guardian

    def update(self, instance, validated_data):
        student = validated_data.pop('student', None)
        guardian = super().update(instance, validated_data)
        self._link_student(guardian, student)
        return guardian


class GuardianStudentSerializer(TenantSerializer):
    class Meta:
        model = GuardianStudent
        fields = ['id', 'school', 'guardian', 'student', 'relationship', 'is_primary', 'created_at', 'updated_at', 'is_archived', 'archived_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class StudentEnrollmentSerializer(TenantSerializer):
    student_name = serializers.SerializerMethodField()
    section_name = serializers.CharField(source='section.name', read_only=True)
    class_name = serializers.CharField(source='section.school_class.name', read_only=True)
    session_name = serializers.CharField(source='session.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = StudentEnrollment
        fields = [
            'id', 'school', 'student', 'student_name', 'section', 'section_name',
            'class_name', 'session', 'session_name', 'term', 'term_name',
            'roll_number', 'status', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class StaffSerializer(TenantSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True, allow_null=True)
    user_email = serializers.CharField(source='user.email', read_only=True, allow_null=True)
    user_role = serializers.CharField(source='user.role', read_only=True, allow_null=True)
    # Write-only convenience fields — create a staff login account inline.
    email = serializers.EmailField(required=False, write_only=True)
    first_name = serializers.CharField(required=False, write_only=True, allow_blank=True)
    last_name = serializers.CharField(required=False, write_only=True, allow_blank=True)
    password = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = Staff
        fields = [
            'id', 'school', 'user', 'user_name', 'user_email', 'user_role',
            'email', 'first_name', 'last_name', 'password',
            'employee_id', 'designation', 'department',
            'employment_type', 'date_joined', 'assigned_classes',
            'assigned_subjects', 'is_active', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']
        extra_kwargs = {'user': {'required': False, 'allow_null': True}}

    def validate(self, attrs):
        attrs = super().validate(attrs)
        school = attrs.get('school') or getattr(self.instance, 'school', None)
        user = attrs.get('user')
        if user and school and user.school_id and user.school_id != school.id:
            raise serializers.ValidationError({'user': 'That account belongs to a different school.'})
        if not self.instance and not user and not attrs.get('email'):
            raise serializers.ValidationError({
                'email': 'Pick an existing user account or enter an email to create one.'
            })
        return attrs

    def create(self, validated_data):
        email = validated_data.pop('email', None)
        first = validated_data.pop('first_name', '')
        last = validated_data.pop('last_name', '')
        password = validated_data.pop('password', None)
        if not validated_data.get('user') and email:
            validate_password(password or '', user=None)
            role = self._staff_role(validated_data.get('designation'))
            user = User.objects.create_user(
                email=email.lower(), password=password,
                first_name=first, last_name=last,
                role=role, school=validated_data.get('school'),
            )
            validated_data['user'] = user
        return super().create(validated_data)

    @staticmethod
    def _staff_role(designation):
        """Map a free-text designation onto a login role."""
        d = (designation or '').lower()
        if 'librar' in d:
            return User.Roles.LIBRARIAN
        if 'account' in d or 'bursar' in d:
            return User.Roles.ACCOUNTANT
        if 'principal' in d or 'head' in d:
            return User.Roles.PRINCIPAL
        if 'exam' in d:
            return User.Roles.EXAM_OFFICER
        if 'hr' in d or 'admin' in d:
            return User.Roles.HR_ADMIN
        if 'teach' in d or 'class' in d:
            return User.Roles.TEACHER
        return User.Roles.STAFF


class AttendanceSerializer(TenantSerializer):
    student_name = serializers.SerializerMethodField()
    class_name = serializers.CharField(source='school_class.name', read_only=True)
    marked_by_name = serializers.CharField(source='marked_by.full_name', read_only=True, allow_null=True)

    class Meta:
        model = Attendance
        fields = [
            'id', 'school', 'student', 'student_name', 'school_class', 'class_name',
            'date', 'status', 'marked_by', 'marked_by_name', 'remarks',
            'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class AssessmentSerializer(TenantSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    class_name = serializers.CharField(source='school_class.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = Assessment
        fields = [
            'id', 'school', 'term', 'term_name', 'subject', 'subject_name',
            'school_class', 'class_name', 'name', 'type',
            'max_score', 'date', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class GradeSerializer(TenantSerializer):
    student_name = serializers.SerializerMethodField()
    assessment_name = serializers.CharField(source='assessment.name', read_only=True)
    subject_name = serializers.CharField(source='assessment.subject.name', read_only=True)
    max_score = serializers.CharField(source='assessment.max_score', read_only=True)

    class Meta:
        model = Grade
        fields = [
            'id', 'school', 'assessment', 'assessment_name', 'subject_name',
            'student', 'student_name', 'score', 'max_score', 'remarks',
            'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class ReportCardSerializer(TenantSerializer):
    class Meta:
        model = ReportCard
        fields = [
            'id', 'school', 'student', 'term', 'total_score', 'average_score',
            'position', 'status', 'teacher_comments', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class FeeCategorySerializer(TenantSerializer):
    class Meta:
        model = FeeCategory
        fields = ['id', 'school', 'name', 'description', 'is_mandatory', 'created_at', 'updated_at', 'is_archived', 'archived_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class FeeStructureSerializer(TenantSerializer):
    class Meta:
        model = FeeStructure
        fields = [
            'id', 'school', 'category', 'name', 'school_class', 'term',
            'amount', 'due_date', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class InvoiceSerializer(TenantSerializer):
    balance = serializers.ReadOnlyField()
    student_name = serializers.SerializerMethodField()
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'school', 'student', 'student_name', 'invoice_number', 'term',
            'term_name', 'issue_date',
            'due_date', 'total_amount', 'amount_paid', 'balance', 'status',
            'notes', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'invoice_number', 'issue_date', 'amount_paid', 'created_at', 'updated_at', 'is_archived', 'archived_at']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class PaymentSerializer(TenantSerializer):
    receipt_number = serializers.SerializerMethodField()
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'school', 'invoice', 'invoice_number', 'amount', 'method',
            'reference', 'receipt_number',
            'paid_at', 'recorded_by', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'paid_at', 'created_at', 'updated_at', 'is_archived', 'archived_at']

    def get_receipt_number(self, obj):
        try:
            return obj.receipt.receipt_number
        except Exception:
            return None


class AnnouncementSerializer(TenantSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)

    class Meta:
        model = Announcement
        fields = [
            'id', 'school', 'title', 'content', 'author', 'author_name',
            'target_roles', 'status', 'publish_at', 'expires_at',
            'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'school', 'author', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class NoticeSerializer(TenantSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True, allow_null=True)

    class Meta:
        model = Notice
        fields = [
            'id', 'school', 'title', 'content', 'author', 'author_name', 'priority',
            'is_read', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class BookSerializer(TenantSerializer):
    class Meta:
        model = Book
        fields = [
            'id', 'school', 'title', 'author', 'isbn', 'publisher',
            'published_year', 'copies_total', 'copies_available',
            'category', 'status', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class BorrowRecordSerializer(TenantSerializer):
    class Meta:
        model = BorrowRecord
        fields = [
            'id', 'school', 'book', 'student', 'borrowed_at', 'due_date',
            'returned_at', 'status', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'borrowed_at', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class RouteSerializer(TenantSerializer):
    class Meta:
        model = Route
        fields = [
            'id', 'school', 'name', 'start_location', 'end_location',
            'stops', 'distance_km', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class VehicleSerializer(TenantSerializer):
    class Meta:
        model = Vehicle
        fields = [
            'id', 'school', 'registration_number', 'make', 'model',
            'capacity', 'status', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class VehicleAssignmentSerializer(TenantSerializer):
    vehicle_label = serializers.CharField(source='vehicle.registration_number', read_only=True)
    route_name = serializers.CharField(source='route.name', read_only=True)

    class Meta:
        model = VehicleAssignment
        fields = [
            'id', 'school', 'vehicle', 'vehicle_label', 'route', 'route_name',
            'driver_name', 'driver_phone',
            'effective_date', 'end_date', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class HostelSerializer(TenantSerializer):
    class Meta:
        model = Hostel
        fields = [
            'id', 'school', 'name', 'address', 'warden_name', 'warden_phone',
            'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class RoomSerializer(TenantSerializer):
    vacancies = serializers.ReadOnlyField()
    hostel_name = serializers.CharField(source='hostel.name', read_only=True)
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            'id', 'school', 'hostel', 'hostel_name', 'display_name', 'room_number', 'capacity', 'occupied',
            'vacancies', 'amenities', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']

    def get_display_name(self, obj):
        return f"{obj.hostel.name} – Room {obj.room_number}"


class HostelAllocationSerializer(TenantSerializer):
    room_label = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = HostelAllocation
        fields = [
            'id', 'school', 'room', 'room_label', 'student', 'student_name', 'check_in', 'check_out',
            'status', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_archived', 'archived_at']

    def get_room_label(self, obj):
        return f"{obj.room.hostel.name} – Room {obj.room.room_number}"

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class EmailMessageSerializer(TenantSerializer):
    class Meta:
        model = EmailMessage
        fields = [
            'id', 'school', 'recipient', 'subject', 'body', 'status',
            'provider_ref', 'sent_at', 'error_message', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'status', 'provider_ref', 'sent_at', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class SMSMessageSerializer(TenantSerializer):
    class Meta:
        model = SMSMessage
        fields = [
            'id', 'school', 'recipient', 'message', 'status',
            'provider_ref', 'sent_at', 'error_message', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'status', 'provider_ref', 'sent_at', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class ExpenseSerializer(TenantSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = Expense
        fields = [
            'id', 'school', 'title', 'description', 'category', 'category_display',
            'amount', 'expense_date', 'term', 'recorded_by', 'receipt',
            'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'recorded_by', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class InAppNotificationSerializer(TenantSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True, allow_null=True)

    class Meta:
        model = InAppNotification
        fields = [
            'id', 'recipient', 'sender', 'sender_name', 'title', 'message',
            'is_read', 'school', 'created_at', 'updated_at', 'is_archived', 'archived_at'
    ]
        read_only_fields = ['id', 'sender', 'sender_name', 'created_at', 'updated_at', 'is_archived', 'archived_at']


class AuditLogSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True, allow_null=True)

    class Meta:
        from core.models import AuditLog
        model = AuditLog
        fields = [
            'id', 'school', 'school_name', 'actor', 'actor_email', 'actor_role',
            'action', 'object_type', 'object_id', 'object_repr', 'changes',
            'ip', 'created_at',
        ]
        read_only_fields = fields
