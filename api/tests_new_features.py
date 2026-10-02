"""Tests for the admin-controls / messaging / result-release feature set.

Covers: school suspension enforcement (live sessions), user suspend/delete
guards, school module entitlements, report-format config validation, result
compute honoring report_config, publish gating, exports, and the messaging
contact matrix.
"""
from decimal import Decimal
from io import BytesIO

from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import User
from academics.models import Class, Section, Subject
from gradebook.models import Assessment, Grade, ReportCard, ResultSummary
from schools.models import AcademicSession, School, Term
from staff.models import Staff
from students.models import Guardian, GuardianStudent, Student, StudentEnrollment


class FeatureBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(
            name='Feature School', subdomain='feature-school',
            tier='Summit', status=School.Status.ACTIVE,
        )
        self.other = School.objects.create(
            name='Other School', subdomain='other-school',
            tier='Summit', status=School.Status.ACTIVE,
        )

        def mk(email, role, school):
            u = User.objects.create_user(
                email=email, password='Pass1234!', role=role, school=school,
                first_name=email.split('@')[0].title(), last_name='User')
            return u

        self.super = User.objects.create_superuser(
            email='root@x.com', password='Pass1234!')
        self.super.role = User.Roles.SUPER_ADMIN
        self.super.save()

        self.admin = mk('admin@x.com', User.Roles.SCHOOL_ADMIN, self.school)
        self.teacher = mk('teacher@x.com', User.Roles.TEACHER, self.school)
        self.staff = Staff.objects.create(
            school=self.school, user=self.teacher, employee_id='T1')
        self.parent = mk('parent@x.com', User.Roles.PARENT, self.school)
        self.outsider_parent = mk('op@x.com', User.Roles.PARENT, self.school)
        self.other_admin = mk('oadmin@x.com', User.Roles.SCHOOL_ADMIN, self.other)

        self.session = AcademicSession.objects.create(
            school=self.school, name='2026/27', start_date='2026-09-01',
            end_date='2027-08-01', is_current=True)
        self.term = Term.objects.create(
            school=self.school, session=self.session, name='Term 1',
            start_date='2026-09-01', end_date='2026-12-15', is_current=True)
        self.klass = Class.objects.create(school=self.school, name='JSS 1')
        self.section = Section.objects.create(
            school=self.school, school_class=self.klass, name='A')
        self.subject = Subject.objects.create(
            school=self.school, name='Maths', code='MTH')
        self.student = Student.objects.create(
            school=self.school, first_name='Ada', last_name='Okafor',
            admission_number='FS/001', gender='female')
        StudentEnrollment.objects.create(
            school=self.school, student=self.student,
            section=self.section, term=self.term, session=self.session)
        self.staff.assigned_classes.add(self.klass)
        guardian = Guardian.objects.create(
            school=self.school, user=self.parent,
            phone='0800000000')
        GuardianStudent.objects.create(
            school=self.school, guardian=guardian, student=self.student)

        self.tokens = {}
        for name, u in [('super', self.super), ('admin', self.admin),
                        ('teacher', self.teacher), ('parent', self.parent),
                        ('op', self.outsider_parent),
                        ('oadmin', self.other_admin)]:
            self.tokens[name], _ = Token.objects.get_or_create(user=u)

    def auth(self, who):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Token {self.tokens[who].key}')


class SchoolSuspensionTests(FeatureBase):
    def test_suspended_school_blocks_existing_session(self):
        self.auth('teacher')
        r = self.client.get('/api/students/')
        self.assertEqual(r.status_code, 200)
        self.school.status = School.Status.SUSPENDED
        self.school.save(update_fields=['status'])
        r = self.client.get('/api/students/')
        self.assertEqual(r.status_code, 403)

    def test_suspended_school_login_rejected(self):
        self.school.status = School.Status.SUSPENDED
        self.school.save(update_fields=['status'])
        r = self.client.post('/api/auth/login/', {
            'email': 'teacher@x.com', 'password': 'Pass1234!'})
        self.assertEqual(r.status_code, 403)

    def test_suspend_activate_school_requires_platform_admin(self):
        self.auth('admin')
        r = self.client.post(f'/api/schools/{self.school.id}/suspend/')
        self.assertIn(r.status_code, (403, 404))
        self.auth('super')
        r = self.client.post(f'/api/schools/{self.school.id}/suspend/')
        self.assertEqual(r.status_code, 200)
        self.school.refresh_from_db()
        self.assertEqual(self.school.status, 'suspended')
        r = self.client.post(f'/api/schools/{self.school.id}/activate/')
        self.assertEqual(r.status_code, 200)

    def test_create_admin_and_modules(self):
        self.auth('super')
        r = self.client.post(f'/api/schools/{self.school.id}/create-admin/', {
            'email': 'newadmin@x.com', 'password': 'Pass1234!',
            'first_name': 'New', 'last_name': 'Admin'})
        self.assertEqual(r.status_code, 201)
        u = User.objects.get(email='newadmin@x.com')
        self.assertEqual(u.role, User.Roles.SCHOOL_ADMIN)
        self.assertEqual(u.school, self.school)

        r = self.client.patch(f'/api/schools/{self.school.id}/', {
            'enabled_modules': ['students', 'grades'],
        }, format='json')
        self.assertEqual(r.status_code, 200)
        self.school.refresh_from_db()
        self.assertEqual(self.school.enabled_modules, ['students', 'grades'])

    def test_school_admin_cannot_change_tier(self):
        # Platform admin restricts the school's modules first.
        self.auth('super')
        self.client.patch(f'/api/schools/{self.school.id}/', {
            'enabled_modules': ['students', 'grades']}, format='json')
        # A school admin then tries to clear the restriction and drop the tier.
        self.auth('admin')
        r = self.client.patch(f'/api/schools/{self.school.id}/', {
            'tier': 'Sprout', 'enabled_modules': []}, format='json')
        self.assertEqual(r.status_code, 200)
        self.school.refresh_from_db()
        # perform_update strips privileged fields for non-platform admins
        self.assertEqual(self.school.tier, 'Summit')
        self.assertEqual(self.school.enabled_modules, ['students', 'grades'])


class UserAdminTests(FeatureBase):
    def test_suspend_delete_guards(self):
        self.auth('admin')
        # cannot suspend self
        r = self.client.post(f'/api/users/{self.admin.id}/suspend/')
        self.assertEqual(r.status_code, 400)
        # can suspend teacher
        r = self.client.post(f'/api/users/{self.teacher.id}/suspend/')
        self.assertEqual(r.status_code, 200)
        self.teacher.refresh_from_db()
        self.assertFalse(self.teacher.is_active)
        # reactivate
        r = self.client.post(f'/api/users/{self.teacher.id}/activate/')
        self.assertEqual(r.status_code, 200)
        # cannot delete self
        r = self.client.delete(f'/api/users/{self.admin.id}/')
        self.assertEqual(r.status_code, 400)

    def test_cross_tenant_user_admin_blocked(self):
        self.auth('oadmin')
        r = self.client.post(f'/api/users/{self.teacher.id}/suspend/')
        self.assertIn(r.status_code, (403, 404))
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.is_active)


class ReportConfigTests(FeatureBase):
    def test_report_config_weights_and_bands(self):
        self.auth('admin')
        r = self.client.patch(f'/api/schools/{self.school.id}/report-config/', {
            'weights': {'ca1': 10, 'ca2': 20, 'exam': 70},
            'grade_bands': [
                {'min': 70, 'label': 'A', 'remark': 'Distinction', 'points': 5},
                {'min': 50, 'label': 'C', 'remark': 'Credit', 'points': 3},
            ],
            'show_position': False,
        }, format='json')
        self.assertEqual(r.status_code, 200)
        cfg = r.data['report_config']
        self.assertEqual(cfg['weights']['exam'], 70.0)
        self.assertEqual(len(cfg['grade_bands']), 2)
        self.assertFalse(cfg['show_position'])

    def test_report_config_rejects_bad_weights(self):
        self.auth('admin')
        r = self.client.patch(f'/api/schools/{self.school.id}/report-config/', {
            'weights': {'ca1': 'x', 'ca2': 20, 'exam': 70}}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_engine_honors_config_bands(self):
        self.school.report_config = {
            'weights': {'ca1': 25, 'ca2': 25, 'exam': 50},
            'grade_bands': [
                {'min': 60, 'label': 'P1', 'remark': 'Top', 'points': 4},
                {'min': 0, 'label': 'P0', 'remark': 'Low', 'points': 0},
            ],
        }
        self.school.save(update_fields=['report_config'])
        for atype, name in [('ca1', 'CA1'), ('ca2', 'CA2'), ('exam', 'Exam')]:
            a = Assessment.objects.create(
                school=self.school, name=name, type=atype, max_score=100,
                date='2026-12-01', term=self.term, subject=self.subject,
                school_class=self.klass)
            Grade.objects.create(
                school=self.school, assessment=a, student=self.student,
                score=Decimal('80'))
        from api.result_engine import compute_results_for_term
        compute_results_for_term(self.school, self.term)
        rs = ResultSummary.objects.get(student=self.student, subject=self.subject)
        # total = 80 → label P1 per custom band
        self.assertEqual(rs.grade, 'P1')
        self.assertEqual(rs.grade_remark, 'Top')
        card = ReportCard.objects.get(student=self.student)
        # New cards must start DRAFT (not auto-published)
        self.assertEqual(card.status, 'draft')


class ResultReleaseTests(FeatureBase):
    def _mk_card(self, status='draft'):
        return ReportCard.objects.create(
            school=self.school, student=self.student, term=self.term,
            school_class=self.klass, total_score=80, average_score=80,
            status=status)

    def test_parent_cannot_see_draft_card(self):
        card = self._mk_card('draft')
        self.auth('parent')
        r = self.client.get(f'/api/report-cards/{card.id}/')
        self.assertIn(r.status_code, (403, 404))
        r = self.client.get('/api/report-cards/')
        self.assertEqual(len(r.data.get('results', r.data)), 0)

    def test_parent_sees_published_card(self):
        card = self._mk_card('published')
        self.auth('parent')
        r = self.client.get('/api/report-cards/')
        rows = r.data.get('results', r.data)
        self.assertEqual(len(rows), 1)

    def test_publish_restricted_to_release_roles(self):
        card = self._mk_card('draft')
        self.auth('teacher')
        r = self.client.post(f'/api/report-cards/{card.id}/publish/')
        self.assertEqual(r.status_code, 403)
        self.auth('admin')
        r = self.client.post(f'/api/report-cards/{card.id}/publish/')
        self.assertEqual(r.status_code, 200)
        card.refresh_from_db()
        self.assertEqual(card.status, 'published')

    def test_teacher_cannot_patch_status(self):
        card = self._mk_card('draft')
        self.auth('teacher')
        r = self.client.patch(f'/api/report-cards/{card.id}/',
                              {'status': 'published'}, format='json')
        card.refresh_from_db()
        self.assertEqual(card.status, 'draft')

    def test_release_class_bulk(self):
        self._mk_card('draft')
        self.auth('admin')
        r = self.client.post('/api/report-cards/release-class/', {
            'term_id': self.term.id, 'class_id': self.klass.id,
            'publish': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            ReportCard.objects.filter(status='published').count(), 1)


class ExportTests(FeatureBase):
    def test_xlsx_and_docx_exports(self):
        self.auth('admin')
        r = self.client.get(f'/api/exports/students/xlsx/?term_id={self.term.id}')
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])
        self.assertTrue(b''.join(r.streaming_content if hasattr(r, 'streaming_content') else [r.content]).startswith(b'PK')
                        or r.content[:2] == b'PK')

        r = self.client.get(f'/api/exports/students/docx/?term_id={self.term.id}')
        self.assertEqual(r.status_code, 200)
        self.assertIn('wordprocessingml', r['Content-Type'])

    def test_parent_cannot_export(self):
        self.auth('parent')
        r = self.client.get(f'/api/exports/students/xlsx/?term_id={self.term.id}')
        self.assertEqual(r.status_code, 403)

    def test_results_export_tenant_scoped(self):
        # A foreign term_id must yield no data — the export is school-scoped.
        self.auth('oadmin')
        r = self.client.get(f'/api/exports/results/csv/?term_id={self.term.id}')
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        # title + header rows only — zero data rows for a foreign school
        self.assertLessEqual(len(body.strip().splitlines()), 2)


class MessagingMatrixTests(FeatureBase):
    def test_contacts_and_dm_pairs(self):
        # teacher can DM the linked parent (assigned class)
        self.auth('teacher')
        r = self.client.post('/api/conversations/start-dm/',
                             {'user_id': self.parent.id}, format='json')
        self.assertIn(r.status_code, (200, 201))

        # parent can DM admin
        self.auth('parent')
        r = self.client.post('/api/conversations/start-dm/',
                             {'user_id': self.admin.id}, format='json')
        self.assertIn(r.status_code, (200, 201))

        # parent cannot DM another parent (family-to-family blocked)
        r = self.client.post('/api/conversations/start-dm/',
                             {'user_id': self.outsider_parent.id}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_cross_school_dm_blocked(self):
        self.auth('parent')
        r = self.client.post('/api/conversations/start-dm/',
                             {'user_id': self.other_admin.id}, format='json')
        self.assertIn(r.status_code, (403, 404))

    def test_class_parents_broadcast(self):
        self.auth('teacher')
        r = self.client.post('/api/conversations/message-class-parents/', {
            'class_id': self.klass.id, 'body': 'Class meeting Friday'},
            format='json')
        self.assertIn(r.status_code, (200, 201))

    def test_unassigned_teacher_blocked_from_class_parents(self):
        other_teacher = User.objects.create_user(
            email='t2@x.com', password='Pass1234!',
            role=User.Roles.TEACHER, school=self.school)
        Staff.objects.create(school=self.school, user=other_teacher,
                             employee_id='T2')
        tok, _ = Token.objects.get_or_create(user=other_teacher)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {tok.key}')
        r = self.client.post('/api/conversations/message-class-parents/', {
            'class_id': self.klass.id, 'body': 'Hi'}, format='json')
        self.assertEqual(r.status_code, 403)


class ArchiveTests(FeatureBase):
    """Soft-delete (archive), restore, and dependency reporting."""

    def test_archive_hides_record_from_list(self):
        self.auth('admin')
        r = self.client.delete(f'/api/subjects/{self.subject.id}/')
        self.assertEqual(r.status_code, 200)
        self.subject.refresh_from_db()
        self.assertTrue(self.subject.is_archived)
        ids = [s['id'] for s in self.client.get('/api/subjects/').json()['results']]
        self.assertNotIn(self.subject.id, ids)

    def test_archived_view_and_restore(self):
        self.auth('admin')
        self.client.delete(f'/api/subjects/{self.subject.id}/')
        r = self.client.get('/api/subjects/?archived=only')
        ids = [s['id'] for s in r.json()['results']]
        self.assertIn(self.subject.id, ids)
        r = self.client.post(f'/api/subjects/{self.subject.id}/restore/')
        self.assertEqual(r.status_code, 200)
        self.subject.refresh_from_db()
        self.assertFalse(self.subject.is_archived)
        ids = [s['id'] for s in self.client.get('/api/subjects/').json()['results']]
        self.assertIn(self.subject.id, ids)

    def test_dependents_reports_tied_records(self):
        self.auth('admin')
        r = self.client.get(f'/api/terms/{self.term.id}/dependents/')
        self.assertEqual(r.status_code, 200)
        deps = r.json()['dependents']
        # The fixture enrollment ties the term to a StudentEnrollment row.
        self.assertTrue(any('Enrollment' in k for k in deps))

    def test_archive_reports_dependents(self):
        self.auth('admin')
        r = self.client.delete(f'/api/terms/{self.term.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['dependents'])

    def test_permanent_delete_blocked_when_tied(self):
        self.auth('admin')
        r = self.client.delete(f'/api/terms/{self.term.id}/?permanent=1')
        self.assertEqual(r.status_code, 400)
        self.assertTrue(Term.objects.filter(pk=self.term.id).exists())

    def test_permanent_delete_allowed_when_untied(self):
        self.auth('admin')
        loose = AcademicSession.objects.create(
            school=self.school, name='Empty Session',
            start_date='2030-01-01', end_date='2030-12-31')
        r = self.client.delete(f'/api/academic-sessions/{loose.id}/?permanent=1')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(AcademicSession.objects.filter(pk=loose.id).exists())

    def test_edit_via_patch(self):
        self.auth('admin')
        r = self.client.patch(f'/api/subjects/{self.subject.id}/',
                              {'name': 'Mathematics'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.name, 'Mathematics')

    def test_is_archived_exposed_but_read_only(self):
        self.auth('admin')
        r = self.client.patch(f'/api/subjects/{self.subject.id}/',
                              {'is_archived': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.subject.refresh_from_db()
        self.assertFalse(self.subject.is_archived)

    def test_parent_cannot_archive(self):
        self.auth('parent')
        r = self.client.delete(f'/api/subjects/{self.subject.id}/')
        self.assertIn(r.status_code, (403, 405))


class AIProviderTests(TestCase):
    """Multi-provider chain: order, fallback, and no-key guidance."""

    def setUp(self):
        from api import ai_views
        self.ai_views = ai_views
        self._orig = dict(ai_views._AI_PROVIDERS)

    def tearDown(self):
        self.ai_views._AI_PROVIDERS.update(self._orig)

    def _stub(self, text=None, err=None):
        def fn(prompt, max_tokens):
            return text, err
        return fn

    def test_first_configured_provider_wins(self):
        self.ai_views._AI_PROVIDERS['gemini'] = self._stub(text='from-gemini')
        self.ai_views._AI_PROVIDERS['grok'] = self._stub(text='from-grok')
        with self.settings(AI_PROVIDERS=['gemini', 'grok']):
            text, err = self.ai_views._call_ai('hi')
        self.assertEqual(text, 'from-gemini')
        self.assertIsNone(err)

    def test_fallback_to_next_provider_on_error(self):
        self.ai_views._AI_PROVIDERS['gemini'] = self._stub(err='quota exhausted')
        self.ai_views._AI_PROVIDERS['grok'] = self._stub(text='from-grok')
        with self.settings(AI_PROVIDERS=['gemini', 'grok']):
            text, err = self.ai_views._call_ai('hi')
        self.assertEqual(text, 'from-grok')
        self.assertIsNone(err)

    def test_unconfigured_provider_is_skipped(self):
        # (None, None) means "no key configured" — silently skipped
        self.ai_views._AI_PROVIDERS['gemini'] = self._stub()
        self.ai_views._AI_PROVIDERS['grok'] = self._stub(text='ok')
        with self.settings(AI_PROVIDERS=['gemini', 'grok']):
            text, err = self.ai_views._call_ai('hi')
        self.assertEqual(text, 'ok')

    def test_all_failed_reports_each_provider(self):
        self.ai_views._AI_PROVIDERS['gemini'] = self._stub(err='bad key')
        self.ai_views._AI_PROVIDERS['grok'] = self._stub(err='timeout')
        with self.settings(AI_PROVIDERS=['gemini', 'grok']):
            text, err = self.ai_views._call_ai('hi')
        self.assertIsNone(text)
        self.assertIn('gemini: bad key', err)
        self.assertIn('grok: timeout', err)

    def test_no_keys_gives_actionable_error(self):
        self.ai_views._AI_PROVIDERS['gemini'] = self._stub()
        self.ai_views._AI_PROVIDERS['grok'] = self._stub()
        self.ai_views._AI_PROVIDERS['anthropic'] = self._stub()
        with self.settings(AI_PROVIDERS=['gemini', 'grok', 'anthropic']):
            text, err = self.ai_views._call_ai('hi')
        self.assertIsNone(text)
        self.assertIn('GEMINI_API_KEY', err)


class LifecycleTests(FeatureBase):
    """Rollover/promotion, forgot-password, submissions grading, bulk
    invoicing, audit log, and whole-school export."""

    # ---- forgot password -------------------------------------------------
    def test_password_reset_flow(self):
        r = self.client.post('/api/auth/send-otp/',
                             {'email': self.parent.email, 'purpose': 'password_reset'})
        self.assertEqual(r.status_code, 200)
        from accounts.models import OTPVerification
        otp = OTPVerification.objects.filter(
            user=self.parent, purpose='password_reset').latest('id')
        r = self.client.post('/api/auth/reset-password/', {
            'otp_id': otp.id, 'code': otp.code, 'new_password': 'NewPass999!'})
        self.assertEqual(r.status_code, 200)
        # Old password dead, new one works
        self.assertEqual(self.client.post('/api/auth/login/',
            {'email': self.parent.email, 'password': 'Pass1234!'}).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login/',
            {'email': self.parent.email, 'password': 'NewPass999!'}).status_code, 200)

    def test_reset_rejects_wrong_and_reused_code(self):
        self.client.post('/api/auth/send-otp/',
                         {'email': self.parent.email, 'purpose': 'password_reset'})
        from accounts.models import OTPVerification
        otp = OTPVerification.objects.filter(
            user=self.parent, purpose='password_reset').latest('id')
        r = self.client.post('/api/auth/reset-password/', {
            'otp_id': otp.id, 'code': 'ZZZZZZ', 'new_password': 'NewPass999!'})
        self.assertEqual(r.status_code, 400)
        otp.refresh_from_db()  # not consumed
        r = self.client.post('/api/auth/reset-password/', {
            'otp_id': otp.id, 'code': otp.code, 'new_password': 'NewPass999!'})
        self.assertEqual(r.status_code, 200)
        # Reuse is rejected
        r = self.client.post('/api/auth/reset-password/', {
            'otp_id': otp.id, 'code': otp.code, 'new_password': 'OtherPass1!'})
        self.assertEqual(r.status_code, 400)

    # ---- submissions grading ---------------------------------------------
    def _assignment_submission(self):
        from homework.models import Assignment, Submission
        a = Assignment.objects.create(
            school=self.school, school_class=self.klass, subject=self.subject,
            teacher=self.teacher, term=self.term, title='Essay',
            due_date='2027-01-01', max_points=20)
        s = Submission.objects.create(
            school=self.school, assignment=a, student=self.student,
            content='my answer')
        return a, s

    def test_staff_can_grade_and_return(self):
        a, s = self._assignment_submission()
        self.auth('teacher')
        r = self.client.post(f'/api/submissions/{s.id}/grade/',
                             {'score': 15, 'feedback': 'Good'})
        self.assertEqual(r.status_code, 200)
        s.refresh_from_db()
        self.assertEqual(s.status, 'graded')
        self.assertEqual(float(s.score), 15)
        r = self.client.post(f'/api/submissions/{s.id}/return/', {})
        self.assertEqual(r.status_code, 200)
        s.refresh_from_db()
        self.assertEqual(s.status, 'returned')

    def test_student_cannot_grade(self):
        a, s = self._assignment_submission()
        stu = User.objects.create_user(
            email='stu@x.com', password='Pass1234!',
            role=User.Roles.STUDENT, school=self.school)
        tok, _ = Token.objects.get_or_create(user=stu)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {tok.key}')
        r = self.client.post(f'/api/submissions/{s.id}/grade/', {'score': 1})
        self.assertEqual(r.status_code, 403)

    def test_score_capped_at_max(self):
        a, s = self._assignment_submission()
        self.auth('teacher')
        r = self.client.post(f'/api/submissions/{s.id}/grade/', {'score': 99})
        self.assertEqual(r.status_code, 400)

    # ---- bulk invoicing ---------------------------------------------------
    def test_bulk_invoice_creates_and_skips_dupes(self):
        from finance.models import FeeCategory, FeeStructure, Invoice
        cat = FeeCategory.objects.create(school=self.school, name='Tuition')
        FeeStructure.objects.create(
            school=self.school, category=cat, name='Tuition JSS1',
            school_class=self.klass, term=self.term, amount=50000)
        self.auth('admin')
        r = self.client.post('/api/invoices/bulk/', {
            'term': self.term.id, 'school_class': self.klass.id,
            'due_date': '2026-10-01', 'status': 'sent'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['created'], 1)
        inv = Invoice.objects.get(student=self.student, term=self.term)
        self.assertEqual(float(inv.total_amount), 50000)
        # Re-run → skip, no duplicate
        r = self.client.post('/api/invoices/bulk/', {
            'term': self.term.id, 'school_class': self.klass.id,
            'due_date': '2026-10-01'})
        self.assertEqual(r.data['created'], 0)
        self.assertEqual(len(r.data['skipped']), 1)

    def test_bulk_invoice_parent_denied(self):
        self.auth('parent')
        r = self.client.post('/api/invoices/bulk/', {
            'term': self.term.id, 'due_date': '2026-10-01'})
        self.assertEqual(r.status_code, 403)

    # ---- rollover ----------------------------------------------------------
    def test_rollover_promote_and_graduate(self):
        nxt_session = AcademicSession.objects.create(
            school=self.school, name='2027/28', start_date='2027-09-01',
            end_date='2028-08-01')
        nxt_term = Term.objects.create(
            school=self.school, session=nxt_session, name='Term 1',
            start_date='2027-09-01', end_date='2027-12-15', is_current=True)
        jss2 = Class.objects.create(school=self.school, name='JSS 2')
        Section.objects.create(school=self.school, school_class=jss2, name='A')

        self.auth('admin')
        r = self.client.get(f'/api/rollover/preview/?source_session={self.session.id}&target_session={nxt_session.id}')
        self.assertEqual(r.status_code, 200)
        jss1_row = [c for c in r.data['classes'] if c['class_id'] == self.klass.id][0]
        self.assertEqual(jss1_row['students'], 1)

        r = self.client.post('/api/rollover/', {
            'source_session': self.session.id,
            'target_session': nxt_session.id,
            'target_term': nxt_term.id,
            'mappings': {str(self.klass.id): f'promote:{jss2.id}'},
        }, format='json')
        self.assertEqual(r.status_code, 200)
        res = r.data['results'][0]
        self.assertEqual(res['promoted'], 1)
        # New enrollment in JSS2/new session; old one completed
        new = StudentEnrollment.objects.get(student=self.student, session=nxt_session)
        self.assertEqual(new.section.school_class, jss2)
        old = StudentEnrollment.objects.get(student=self.student, session=self.session)
        self.assertEqual(old.status, 'completed')

    def test_rollover_graduate_marks_completed(self):
        nxt = AcademicSession.objects.create(
            school=self.school, name='2027/28', start_date='2027-09-01',
            end_date='2028-08-01')
        nt = Term.objects.create(
            school=self.school, session=nxt, name='T1',
            start_date='2027-09-01', end_date='2027-12-15')
        self.auth('admin')
        r = self.client.post('/api/rollover/', {
            'source_session': self.session.id, 'target_session': nxt.id,
            'target_term': nt.id,
            'mappings': {str(self.klass.id): 'graduate'},
        }, format='json')
        self.assertEqual(r.status_code, 200)
        old = StudentEnrollment.objects.get(student=self.student, session=self.session)
        self.assertEqual(old.status, 'completed')
        self.assertFalse(StudentEnrollment.objects.filter(
            student=self.student, session=nxt).exists())

    def test_rollover_teacher_denied(self):
        self.auth('teacher')
        r = self.client.post('/api/rollover/', {
            'source_session': self.session.id, 'target_session': self.session.id,
            'target_term': self.term.id, 'mappings': {'1': 'skip'}}, format='json')
        self.assertEqual(r.status_code, 403)

    # ---- audit log ------------------------------------------------------
    def test_audit_records_suspend_and_scoped(self):
        from core.models import AuditLog
        self.auth('admin')
        self.client.post(f'/api/users/{self.teacher.id}/suspend/')
        self.assertTrue(AuditLog.objects.filter(
            action='user.suspend', object_id=str(self.teacher.id)).exists())
        r = self.client.get('/api/audit-logs/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(e['action'] == 'user.suspend' for e in r.data['results']))
        # Non-privileged roles get an empty log
        self.auth('parent')
        r = self.client.get('/api/audit-logs/')
        self.assertEqual(len(r.data['results']), 0)
        # Other school sees nothing of this school's events
        self.auth('oadmin')
        r = self.client.get('/api/audit-logs/')
        self.assertFalse(any(e['object_id'] == str(self.teacher.id)
                             for e in r.data['results']))

    def test_archive_is_audited(self):
        from core.models import AuditLog
        self.auth('admin')
        self.client.delete(f'/api/subjects/{self.subject.id}/')
        self.assertTrue(AuditLog.objects.filter(
            action='record.archive', object_id=str(self.subject.id)).exists())

    # ---- whole-school export --------------------------------------------
    def test_full_export_workbook(self):
        self.auth('admin')
        r = self.client.get('/api/export/all/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])
        import io, openpyxl
        content = b''.join(r.streaming_content) if hasattr(r, 'streaming_content') else r.content
        wb = openpyxl.load_workbook(io.BytesIO(content))
        for sheet in ('README', 'Students', 'Enrollments', 'Users', 'Payments'):
            self.assertIn(sheet, wb.sheetnames)


class TotpTests(FeatureBase):
    """Authenticator-app (TOTP) enrolment and password reset."""

    def _enable_totp(self, who='parent'):
        import pyotp
        self.auth(who)
        r = self.client.post('/api/auth/totp/setup/')
        self.assertEqual(r.status_code, 200)
        secret = r.data['secret']
        code = pyotp.TOTP(secret).now()
        r = self.client.post('/api/auth/totp/enable/', {'code': code})
        self.assertEqual(r.status_code, 200)
        return secret

    def test_setup_returns_secret_and_uri(self):
        self.auth('parent')
        r = self.client.post('/api/auth/totp/setup/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('otpauth://', r.data['otpauth_url'])
        self.assertTrue(len(r.data['secret']) >= 16)
        # Not active until a code verifies
        self.parent.refresh_from_db()
        self.assertFalse(self.parent.totp_enabled)

    def test_enable_rejects_bad_code(self):
        self.auth('parent')
        self.client.post('/api/auth/totp/setup/')
        r = self.client.post('/api/auth/totp/enable/', {'code': '000000'})
        self.assertEqual(r.status_code, 400)
        self.parent.refresh_from_db()
        self.assertFalse(self.parent.totp_enabled)

    def test_reset_password_with_totp(self):
        secret = self._enable_totp('parent')
        import pyotp
        code = pyotp.TOTP(secret).now()
        r = self.client.post('/api/auth/reset-password/', {
            'email': 'parent@x.com', 'totp_code': code,
            'new_password': 'NewPass999!',
        })
        self.assertEqual(r.status_code, 200)
        self.client.credentials()  # reset dropped the token � stop sending it
        # Old password dead, new password works
        self.assertEqual(self.client.post('/api/auth/login/', {
            'email': 'parent@x.com', 'password': 'Pass1234!'}).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login/', {
            'email': 'parent@x.com', 'password': 'NewPass999!'}).status_code, 200)

    def test_totp_reset_rejected_when_not_enrolled(self):
        r = self.client.post('/api/auth/reset-password/', {
            'email': 'teacher@x.com', 'totp_code': '123456',
            'new_password': 'NewPass999!',
        })
        self.assertEqual(r.status_code, 400)
        # Password unchanged
        self.assertEqual(self.client.post('/api/auth/login/', {
            'email': 'teacher@x.com', 'password': 'NewPass999!'}).status_code, 401)

    def test_totp_reset_unknown_email_generic_error(self):
        r = self.client.post('/api/auth/reset-password/', {
            'email': 'nobody@x.com', 'totp_code': '123456',
            'new_password': 'NewPass999!',
        })
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('exist', r.data['detail'].lower())

    def test_disable_requires_valid_code(self):
        secret = self._enable_totp('parent')
        import pyotp
        self.auth('parent')
        r = self.client.post('/api/auth/totp/disable/', {'code': '000000'})
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/auth/totp/disable/',
                             {'code': pyotp.TOTP(secret).now()})
        self.assertEqual(r.status_code, 200)
        self.parent.refresh_from_db()
        self.assertFalse(self.parent.totp_enabled)
        # TOTP reset no longer works
        r = self.client.post('/api/auth/reset-password/', {
            'email': 'parent@x.com', 'totp_code': '123456',
            'new_password': 'AnotherPass9!',
        })
        self.assertEqual(r.status_code, 400)

    def test_totp_endpoints_require_auth(self):
        for url in ('/api/auth/totp/setup/', '/api/auth/totp/enable/',
                    '/api/auth/totp/disable/'):
            r = self.client.post(url, {})
            self.assertIn(r.status_code, (401, 403))


class ApprovalWorkflowTests(FeatureBase):
    """Super-admin onboarding review: detail, edit, approve, flag, reject."""

    def _make_request(self, name='Pending School', subdomain='pending-sch'):
        school = School.objects.create(
            name=name, subdomain=subdomain, tier='Roots',
            status=School.Status.ONBOARDING,
            contact_info={'email': 'info@pend.ng', 'phone': '0801'},
        )
        admin = User.objects.create_user(
            email=f'admin@{subdomain}.ng', password='Pass1234!',
            role=User.Roles.SCHOOL_ADMIN, school=school,
            first_name='Pending', last_name='Admin')
        return school, admin

    def test_list_shows_admin_and_subscription(self):
        school, admin = self._make_request()
        self.auth('super')
        r = self.client.get('/api/onboarding/approvals/')
        self.assertEqual(r.status_code, 200)
        row = next(x for x in r.data if x['id'] == school.id)
        self.assertEqual(row['admin']['email'], admin.email)
        self.assertIn('admin_notes', row)

    def test_detail_and_edit(self):
        school, admin = self._make_request()
        self.auth('super')
        r = self.client.get(f'/api/onboarding/approvals/{school.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['name'], 'Pending School')
        r = self.client.patch(f'/api/onboarding/approvals/{school.id}/', {
            'name': 'Fixed Name School', 'tier': 'Bloom',
            'contact_phone': '0909999', 'admin_notes': 'called them',
            'admin_email': 'real@pend.ng',
        }, format='json')
        self.assertEqual(r.status_code, 200)
        school.refresh_from_db(); admin.refresh_from_db()
        self.assertEqual(school.name, 'Fixed Name School')
        self.assertEqual(school.tier, 'Bloom')
        self.assertEqual(school.contact_info['phone'], '0909999')
        self.assertEqual(school.admin_notes, 'called them')
        self.assertEqual(admin.email, 'real@pend.ng')

    def test_edit_rejects_taken_subdomain_and_email(self):
        school, _ = self._make_request()
        self.auth('super')
        r = self.client.patch(f'/api/onboarding/approvals/{school.id}/',
                              {'subdomain': self.school.subdomain}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(f'/api/onboarding/approvals/{school.id}/',
                              {'admin_email': 'admin@x.com'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_approve_activates(self):
        school, _ = self._make_request()
        self.auth('super')
        r = self.client.post(f'/api/onboarding/approvals/{school.id}/approve/')
        self.assertEqual(r.status_code, 200)
        school.refresh_from_db()
        self.assertEqual(school.status, 'active')
        from core.models import AuditLog
        self.assertTrue(AuditLog.objects.filter(
            action='school.approve', object_id=str(school.id)).exists())

    def test_flag_suspends(self):
        school, _ = self._make_request()
        self.auth('super')
        r = self.client.post(f'/api/onboarding/approvals/{school.id}/flag/',
                             {'reason': 'unverified'}, format='json')
        self.assertEqual(r.status_code, 200)
        school.refresh_from_db()
        self.assertEqual(school.status, 'suspended')

    def test_reject_deletes_pending_only(self):
        school, admin = self._make_request()
        self.auth('super')
        # Cannot reject an already-active school
        self.school.refresh_from_db()
        r = self.client.post(f'/api/onboarding/approvals/{self.school.id}/reject/')
        self.assertEqual(r.status_code, 400)
        # Pending request is removed with its admin account
        r = self.client.post(f'/api/onboarding/approvals/{school.id}/reject/',
                             {'reason': 'duplicate'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(School.objects.filter(pk=school.id).exists())
        self.assertFalse(User.objects.filter(pk=admin.id).exists())

    def test_non_super_admin_denied(self):
        school, _ = self._make_request()
        self.auth('oadmin')
        self.assertEqual(self.client.get('/api/onboarding/approvals/').status_code, 403)
        self.assertEqual(self.client.get(
            f'/api/onboarding/approvals/{school.id}/').status_code, 403)
        self.assertEqual(self.client.patch(
            f'/api/onboarding/approvals/{school.id}/',
            {'name': 'x'}, format='json').status_code, 403)
        self.assertEqual(self.client.post(
            f'/api/onboarding/approvals/{school.id}/reject/').status_code, 403)


class TierCatalogAndModuleRequestTests(FeatureBase):
    def test_tiers_endpoint_public_catalog(self):
        r = self.client.get('/api/onboarding/tiers/')
        self.assertEqual(r.status_code, 200)
        tiers = r.data['tiers']
        self.assertEqual(len(tiers), 4)
        sprout = tiers[0]
        self.assertIn('billing', sprout)
        self.assertTrue(sprout['modules'])
        self.assertTrue(sprout['suitable'])
        # Higher-tier modules appear as requestable extras
        keys = [m['key'] for m in sprout['extra_modules']]
        self.assertIn('library', keys)
        self.assertIn('transport', keys)

    def test_onboarding_stores_requested_modules(self):
        r = self.client.post('/api/onboarding/', {
            'school_name': 'Req Mod School', 'address': 'x',
            'subdomain': 'reqmod', 'tier': 'Sprout',
            'admin_email': 'ra@reqmod.ng', 'admin_name': 'Req Admin',
            'admin_password': 'Str0ng!Pass', 'billing_cycle': 'termly',
            'requested_modules': ['library', 'bogus-key', 'transport'],
        }, format='json')
        self.assertEqual(r.status_code, 201)
        school = School.objects.get(subdomain='reqmod')
        # Invalid keys stripped; valid kept
        self.assertEqual(sorted(school.requested_modules), ['library', 'transport'])

    def test_approval_payload_includes_request_and_tier_modules(self):
        school, _ = ApprovalWorkflowTests._make_request(self)
        school.requested_modules = ['library']
        school.save()
        self.auth('super')
        r = self.client.get(f'/api/onboarding/approvals/{school.id}/')
        self.assertEqual(r.data['requested_modules'], ['library'])
        self.assertIn('students', r.data['tier_modules'])
        self.assertNotIn('transport', r.data['tier_modules'])

    def test_grant_extra_modules_via_patch(self):
        school, _ = ApprovalWorkflowTests._make_request(self)
        self.auth('super')
        detail = self.client.get(f'/api/onboarding/approvals/{school.id}/').data
        mods = detail['tier_modules'] + ['transport']
        r = self.client.patch(f'/api/onboarding/approvals/{school.id}/',
                              {'enabled_modules': mods}, format='json')
        self.assertEqual(r.status_code, 200)
        school.refresh_from_db()
        self.assertIn('transport', school.enabled_modules)


class UserSetPasswordTests(FeatureBase):
    def test_admin_resets_user_password(self):
        self.auth('super')
        r = self.client.post(f'/api/users/{self.parent.id}/set-password/',
                             {'password': 'TempPass99!'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/auth/login/', {
            'email': 'parent@x.com', 'password': 'TempPass99!'}).status_code, 200)
        from core.models import AuditLog
        self.assertTrue(AuditLog.objects.filter(
            action='user.reset_password', object_id=str(self.parent.id)).exists())

    def test_short_password_rejected_and_self_blocked(self):
        self.auth('super')
        r = self.client.post(f'/api/users/{self.parent.id}/set-password/',
                             {'password': 'short'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.post(f'/api/users/{self.super.id}/set-password/',
                             {'password': 'LongEnough9!'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_school_admin_can_reset_same_school_only(self):
        self.auth('admin')
        r = self.client.post(f'/api/users/{self.parent.id}/set-password/',
                             {'password': 'TempPass99!'}, format='json')
        self.assertEqual(r.status_code, 200)
        # Other school's users are invisible to this admin
        other_parent = User.objects.create_user(
            email='ox@other.ng', password='Pass1234!',
            role=User.Roles.PARENT, school=self.other)
        r = self.client.post(f'/api/users/{other_parent.id}/set-password/',
                             {'password': 'TempPass99!'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_parent_cannot_reset_passwords(self):
        self.auth('parent')
        r = self.client.post(f'/api/users/{self.teacher.id}/set-password/',
                             {'password': 'TempPass99!'}, format='json')
        self.assertIn(r.status_code, (403, 404))


class DemoLeadActionTests(FeatureBase):
    def _lead(self):
        from schools.models import DemoLead
        return DemoLead.objects.create(
            school_name='Lead Sch', contact_name='Ada',
            email='ada@lead.ng', phone='0801')

    def test_toggle_contacted_and_delete(self):
        lead = self._lead()
        self.auth('super')
        r = self.client.post(f'/api/marketing/demo-leads/{lead.id}/contact/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['contacted'])
        r = self.client.post(f'/api/marketing/demo-leads/{lead.id}/contact/')
        self.assertFalse(r.data['contacted'])
        r = self.client.delete(f'/api/marketing/demo-leads/{lead.id}/')
        self.assertEqual(r.status_code, 200)
        from schools.models import DemoLead
        self.assertFalse(DemoLead.objects.filter(pk=lead.id).exists())

    def test_non_admin_denied(self):
        lead = self._lead()
        self.auth('oadmin')
        self.assertEqual(self.client.post(
            f'/api/marketing/demo-leads/{lead.id}/contact/').status_code, 403)
        self.assertEqual(self.client.delete(
            f'/api/marketing/demo-leads/{lead.id}/').status_code, 403)
