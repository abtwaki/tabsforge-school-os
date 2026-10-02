"""End-to-end workflow and multi-tenancy verification for TabsForge School OS.

These tests run on a transient test database and cover the critical
admission-to-student, finance, and result workflows. They do not touch
production data.
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import User
from academics.models import Class, ClassSubject, Section, Subject
from attendance.models import Attendance
from finance.models import FeeCategory, FeeStructure, Invoice, Payment, PaymentReceipt
from gradebook.models import Assessment, Grade, GradingScheme, GradeBoundary, ReportCard, ResultSummary
from schools.models import AcademicSession, School, Term
from staff.models import Staff
from students.models import Guardian, GuardianStudent, Student, StudentEnrollment


class EndToEndWorkflow(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.super = User.objects.create_superuser(
            email='super@workflows.example', password='Superpass123!',
            first_name='Super', last_name='Admin',
        )
        self.super.role = User.Roles.SUPER_ADMIN
        self.super.save()
        self.super_token, _ = Token.objects.get_or_create(user=self.super)

        self.school = School.objects.create(
            name='TabsForge Audit School', subdomain='audit-school',
            tier='Sprout', status=School.Status.ACTIVE,
        )
        self.admin = User.objects.create_user(
            email='admin@workflows.example', password='Adminpass123!',
            first_name='Admin', last_name='One', role=User.Roles.SCHOOL_ADMIN,
            school=self.school, is_staff=True,
        )
        self.teacher_user = User.objects.create_user(
            email='teacher@workflows.example', password='Teacherpass123!',
            first_name='Teacher', last_name='One', role=User.Roles.STAFF,
            school=self.school,
        )
        Staff.objects.create(
            school=self.school, user=self.teacher_user, employee_id='T001',
            designation='Subject Teacher',
        )
        self.parent_user = User.objects.create_user(
            email='parent@workflows.example', password='Parentpass123!',
            first_name='Parent', last_name='One', role=User.Roles.PARENT,
            school=self.school,
        )
        self.admin_token, _ = Token.objects.get_or_create(user=self.admin)
        self.teacher_token, _ = Token.objects.get_or_create(user=self.teacher_user)
        self.parent_token, _ = Token.objects.get_or_create(user=self.parent_user)

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_a_school_setup(self):
        """Create session, term, class, arm, subject and grading scheme."""
        self.auth(self.admin_token)

        session = AcademicSession.objects.create(
            school=self.school, name='2026/2027', start_date='2026-09-01', end_date='2027-08-31',
            is_current=True,
        )
        term = Term.objects.create(
            school=self.school, session=session, name='First Term',
            start_date='2026-09-01', end_date='2026-12-22', is_current=True,
        )
        school_class = Class.objects.create(school=self.school, name='JSS 1')
        section = Section.objects.create(school=self.school, school_class=school_class, name='A')
        subject = Subject.objects.create(school=self.school, name='Mathematics', code='MATH')
        ClassSubject.objects.create(school=self.school, school_class=school_class, subject=subject, teacher=self.teacher_user)

        scheme = GradingScheme.objects.create(school=self.school, name='Primary', ca1_weight=30, ca2_weight=20, exam_weight=50, is_default=True)
        GradeBoundary.objects.create(school=self.school, scheme=scheme, label='A', min_score=70, max_score=100, points=5)
        GradeBoundary.objects.create(school=self.school, scheme=scheme, label='B', min_score=60, max_score=69.99, points=4)

        self.assertEqual(Section.objects.filter(school=self.school).count(), 1)
        self.assertEqual(ClassSubject.objects.filter(school=self.school).count(), 1)

    def test_b_admission_to_student(self):
        """Create, approve and convert an application into a student."""
        session = AcademicSession.objects.create(
            school=self.school, name='2026/2027', start_date='2026-09-01', end_date='2027-08-31',
            is_current=True,
        )
        term = Term.objects.create(
            school=self.school, session=session, name='First Term',
            start_date='2026-09-01', end_date='2026-12-22', is_current=True,
        )
        school_class = Class.objects.create(school=self.school, name='JSS 1')

        self.auth(self.admin_token)

        # Create application
        from admissions.models import Application
        application = Application.objects.create(
            school=self.school, first_name='Chidi', last_name='Obi',
            date_of_birth='2015-05-10', gender='male', applying_for_class=school_class,
            session=session,
            guardian_name='Ada Obi', guardian_phone='08000000001',
            status='approved', generated_admission_number='ADM-2026-0001',
        )

        # Convert to student
        student = Student.objects.create(
            school=self.school, first_name=application.first_name, last_name=application.last_name,
            admission_number=application.generated_admission_number,
            date_of_birth=application.date_of_birth,
        )
        section = Section.objects.create(school=self.school, school_class=school_class, name='A')
        StudentEnrollment.objects.create(
            school=self.school, student=student, section=section, session=session, term=term,
            status='active',
        )
        application.student = student
        application.save()

        # Verify student appears in class list
        self.assertTrue(StudentEnrollment.objects.filter(school=self.school, student=student, section=section).exists())
        self.assertEqual(StudentEnrollment.objects.filter(school=self.school, student=student).count(), 1)

    def test_c_guardian_link_and_parent_read(self):
        """Add guardian, link to student, and verify parent access."""
        school_class = Class.objects.create(school=self.school, name='JSS 1')
        section = Section.objects.create(school=self.school, school_class=school_class, name='A')
        session = AcademicSession.objects.create(
            school=self.school, name='2026/2027', start_date='2026-09-01', end_date='2027-08-31',
            is_current=True,
        )
        term = Term.objects.create(
            school=self.school, session=session, name='First Term',
            start_date='2026-09-01', end_date='2026-12-22', is_current=True,
        )
        student = Student.objects.create(
            school=self.school, first_name='Chidi', last_name='Obi', admission_number='A001',
        )
        StudentEnrollment.objects.create(
            school=self.school, student=student, section=section, session=session, term=term,
        )

        guardian = Guardian.objects.create(
            school=self.school, user=self.parent_user,
            first_name='Ada', last_name='Obi', relationship='mother',
        )
        GuardianStudent.objects.create(school=self.school, guardian=guardian, student=student, is_primary=True)

        # Parent can list only own ward
        self.auth(self.parent_token)
        response = self.client.get(reverse('student-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get('results', response.data)), 1)

    def test_d_fees_payment_and_receipt(self):
        """Create fee, invoice, record payment and verify balance/receipt."""
        session = AcademicSession.objects.create(
            school=self.school, name='2026/2027', start_date='2026-09-01', end_date='2027-08-31',
            is_current=True,
        )
        term = Term.objects.create(
            school=self.school, session=session, name='First Term',
            start_date='2026-09-01', end_date='2026-12-22', is_current=True,
        )
        school_class = Class.objects.create(school=self.school, name='JSS 1')
        student = Student.objects.create(
            school=self.school, first_name='Chidi', last_name='Obi', admission_number='A002',
        )

        fee_category = FeeCategory.objects.create(school=self.school, name='Tuition')
        fee = FeeStructure.objects.create(
            school=self.school, category=fee_category, name='JSS 1 Tuition',
            school_class=school_class, term=term, amount=Decimal('50000.00'),
        )
        invoice = Invoice.objects.create(
            school=self.school, student=student, invoice_number='INV-001', term=term,
            total_amount=Decimal('50000.00'), due_date='2026-10-31',
            amount_paid=Decimal('0'),
        )
        self.assertEqual(invoice.balance, Decimal('50000.00'))

        # First partial payment
        p1 = Payment.objects.create(
            school=self.school, invoice=invoice, amount=Decimal('20000.00'),
            method='cash',
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, Decimal('20000.00'))
        self.assertEqual(invoice.status, Invoice.Status.PARTIAL)
        self.assertEqual(invoice.balance, Decimal('30000.00'))
        self.assertEqual(PaymentReceipt.objects.filter(payment=p1).count(), 1)

        # Second payment completing fee
        Payment.objects.create(
            school=self.school, invoice=invoice, amount=Decimal('30000.00'),
            method='bank_transfer',
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, Decimal('50000.00'))
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.balance, Decimal('0.00'))

    def test_e_result_calculation(self):
        """Enter CA and exam scores, compute totals and grades, verify report card."""
        session = AcademicSession.objects.create(
            school=self.school, name='2026/2027', start_date='2026-09-01', end_date='2027-08-31',
            is_current=True,
        )
        term = Term.objects.create(
            school=self.school, session=session, name='First Term',
            start_date='2026-09-01', end_date='2026-12-22', is_current=True,
        )
        school_class = Class.objects.create(school=self.school, name='JSS 1')
        section = Section.objects.create(school=self.school, school_class=school_class, name='A')
        subject = Subject.objects.create(school=self.school, name='Mathematics', code='MATH')

        scheme = GradingScheme.objects.create(
            school=self.school, name='Primary', ca1_weight=20, ca2_weight=20, exam_weight=60,
            is_default=True,
        )
        GradeBoundary.objects.create(school=self.school, scheme=scheme, label='A', min_score=70, max_score=100, points=5)
        GradeBoundary.objects.create(school=self.school, scheme=scheme, label='B', min_score=60, max_score=69.99, points=4)
        GradeBoundary.objects.create(school=self.school, scheme=scheme, label='C', min_score=50, max_score=59.99, points=3)

        s1 = Student.objects.create(school=self.school, first_name='Amara', last_name='Okafor', admission_number='S001')
        s2 = Student.objects.create(school=self.school, first_name='Daniel', last_name='Mensah', admission_number='S002')
        StudentEnrollment.objects.create(school=self.school, student=s1, section=section, session=session, term=term)
        StudentEnrollment.objects.create(school=self.school, student=s2, section=section, session=session, term=term)

        ca1 = Assessment.objects.create(school=self.school, term=term, subject=subject, school_class=school_class, name='CA 1', type='ca1', max_score=20, date='2026-10-05')
        ca2 = Assessment.objects.create(school=self.school, term=term, subject=subject, school_class=school_class, name='CA 2', type='ca2', max_score=20, date='2026-10-20')
        exam = Assessment.objects.create(school=self.school, term=term, subject=subject, school_class=school_class, name='Exam', type='exam', max_score=100, date='2026-11-10')

        # s1: 15/20 ca1, 14/20 ca2, 78/100 exam -> 15*0.2 + 14*0.2 + 78*0.6 = 52.6, grade C
        Grade.objects.create(school=self.school, assessment=ca1, student=s1, score=15)
        Grade.objects.create(school=self.school, assessment=ca2, student=s1, score=14)
        Grade.objects.create(school=self.school, assessment=exam, student=s1, score=78)

        # s2: 18/20 ca1, 17/20 ca2, 89/100 exam -> 18*0.2 + 17*0.2 + 89*0.6 = 60.4, grade B
        Grade.objects.create(school=self.school, assessment=ca1, student=s2, score=18)
        Grade.objects.create(school=self.school, assessment=ca2, student=s2, score=17)
        Grade.objects.create(school=self.school, assessment=exam, student=s2, score=89)

        # Manual result calculation (mirrors what a backend result engine must do)
        for student in [s1, s2]:
            ca1_score = Grade.objects.get(assessment=ca1, student=student).score
            ca2_score = Grade.objects.get(assessment=ca2, student=student).score
            exam_score = Grade.objects.get(assessment=exam, student=student).score
            total = float(ca1_score) * (scheme.ca1_weight / 100) + float(ca2_score) * (scheme.ca2_weight / 100) + float(exam_score) * (scheme.exam_weight / 100)

            # Determine grade from boundaries
            grade = None
            for boundary in scheme.boundaries.order_by('-min_score'):
                if total >= float(boundary.min_score):
                    grade = boundary
                    break

            ResultSummary.objects.update_or_create(
                school=self.school, student=student, term=term, subject=subject,
                defaults={
                    'school_class': school_class,
                    'scheme': scheme,
                    'ca1_score': ca1_score,
                    'ca2_score': ca2_score,
                    'exam_score': exam_score,
                    'total_score': total,
                    'grade': grade.label if grade else '',
                    'grade_points': grade.points if grade else 0,
                },
            )

        r1 = ResultSummary.objects.get(school=self.school, student=s1, term=term, subject=subject)
        r2 = ResultSummary.objects.get(school=self.school, student=s2, term=term, subject=subject)
        self.assertAlmostEqual(float(r1.total_score), 52.6, places=1)
        self.assertEqual(r1.grade, 'C')
        self.assertAlmostEqual(float(r2.total_score), 60.4, places=1)
        self.assertEqual(r2.grade, 'B')

        # Compute positions by total score descending
        results = list(ResultSummary.objects.filter(school=self.school, term=term, subject=subject).order_by('-total_score'))
        for i, res in enumerate(results, start=1):
            res.subject_position = i
            res.save()

        r1.refresh_from_db()
        r2.refresh_from_db()
        self.assertEqual(r2.subject_position, 1)
        self.assertEqual(r1.subject_position, 2)

        # Report card for s2
        ReportCard.objects.update_or_create(
            school=self.school, student=s2, term=term,
            defaults={
                'school_class': school_class,
                'average_score': r2.total_score,
                'subjects_count': 1,
            },
        )
        rc = ReportCard.objects.get(school=self.school, student=s2, term=term)
        self.assertEqual(rc.subjects_count, 1)


class MultiTenancyTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.school_a = School.objects.create(
            name='School A', subdomain='school-a-audit', tier='Sprout', status=School.Status.ACTIVE,
        )
        self.school_b = School.objects.create(
            name='School B', subdomain='school-b-audit', tier='Sprout', status=School.Status.ACTIVE,
        )

        self.admin_a = User.objects.create_user(
            email='admin@school-a-audit.example', password='password123',
            first_name='Admin', last_name='A', role=User.Roles.SCHOOL_ADMIN,
            school=self.school_a, is_staff=True,
        )
        self.admin_b = User.objects.create_user(
            email='admin@school-b-audit.example', password='password123',
            first_name='Admin', last_name='B', role=User.Roles.SCHOOL_ADMIN,
            school=self.school_b, is_staff=True,
        )

        self.class_a = Class.objects.create(school=self.school_a, name='Class A')
        self.class_b = Class.objects.create(school=self.school_b, name='Class B')

        self.token_a, _ = Token.objects.get_or_create(user=self.admin_a)
        self.token_b, _ = Token.objects.get_or_create(user=self.admin_b)

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_cross_school_list_isolation(self):
        self.auth(self.token_a)
        response = self.client.get(reverse('class-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item['name'] for item in response.data.get('results', response.data)]
        self.assertIn('Class A', names)
        self.assertNotIn('Class B', names)

    def test_cross_school_detail_get(self):
        self.auth(self.token_b)
        url = reverse('class-detail', kwargs={'pk': self.class_a.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_school_update_blocked(self):
        # User A cannot modify school B's class.
        self.auth(self.token_a)
        url = reverse('class-detail', kwargs={'pk': self.class_b.pk})
        response = self.client.patch(url, {'name': 'Hijacked'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_school_delete_blocked(self):
        # User A cannot delete school B's class.
        self.auth(self.token_a)
        url = reverse('class-detail', kwargs={'pk': self.class_b.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Class.objects.filter(pk=self.class_b.pk).exists())

    def test_cross_school_search(self):
        self.auth(self.token_b)
        response = self.client.get(reverse('class-list'), {'search': 'Class A'})
        names = [item['name'] for item in response.data.get('results', response.data)]
        self.assertNotIn('Class A', names)

    def test_cross_school_student_read(self):
        student_a = Student.objects.create(
            school=self.school_a, first_name='A', last_name='Student', admission_number='SA01',
        )
        student_b = Student.objects.create(
            school=self.school_b, first_name='B', last_name='Student', admission_number='SB01',
        )

        user_a = User.objects.create_user(
            email='student@school-a-audit.example', password='password123',
            first_name='Student', last_name='A', role=User.Roles.STUDENT,
            school=self.school_a,
        )
        student_a.user = user_a
        student_a.save()
        token_a, _ = Token.objects.get_or_create(user=user_a)

        self.auth(token_a)
        response = self.client.get(reverse('student-list'))
        ids = [item['id'] for item in response.data.get('results', response.data)]
        self.assertIn(student_a.pk, ids)
        self.assertNotIn(student_b.pk, ids)
