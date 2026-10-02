"""Seed deterministic demo data for TabsForge School OS."""
from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from academics.models import Class, Section, Subject, Timetable
from billing.models import Subscription
from billing.providers import tier_price
from finance.models import FeeCategory
from gradebook.models import Assessment
from schools.models import AcademicSession, School, Term
from staff.models import Staff
from students.models import Guardian, GuardianStudent, Student, StudentEnrollment


class Command(BaseCommand):
    help = 'Create a demo school with sample data and admin credentials.'

    def handle(self, *args, **options):
        school, created = School.objects.get_or_create(
            subdomain='demo-school',
            defaults={
                'name': 'Demo School of Excellence',
                'address': '1 Demo Avenue, Demo City',
                'contact_info': {'phone': '+1-555-DEMO', 'email': 'info@demo-school.example'},
                'tier': 'Bloom',
                'status': 'active',
                'primary_color': '#3B82F6',
                'secondary_color': '#10B981',
            },
        )
        if not created:
            self.stdout.write(self.style.WARNING('Demo school already exists, skipping creation.'))

        # Ensure the demo school has a subscription record.
        Subscription.objects.get_or_create(
            school=school,
            defaults={
                'tier': school.tier,
                'billing_cycle': 'termly',
                'amount': tier_price(school.tier, 'termly'),
                'currency': 'NGN',
                'status': Subscription.Status.ACTIVE,
                'provider': 'manual',
            },
        )

        today = timezone.now().date()
        session, _ = AcademicSession.objects.get_or_create(
            school=school,
            name='2025/2026 Academic Session',
            defaults={
                'start_date': today,
                'end_date': today + timedelta(days=365),
                'is_current': True,
            },
        )
        term, _ = Term.objects.get_or_create(
            school=school,
            session=session,
            name='First Term',
            defaults={
                'start_date': today,
                'end_date': today + timedelta(days=120),
                'is_current': True,
            },
        )

        # Admin user
        admin_email = 'admin@demo-school.example'
        admin_password = 'DemoPass123!'
        admin_user, admin_created = User.objects.get_or_create(
            email=admin_email,
            defaults={
                'first_name': 'Demo',
                'last_name': 'Administrator',
                'role': User.Roles.SCHOOL_ADMIN,
                'school': school,
                'is_staff': True,
                'is_active': True,
            },
        )
        if admin_created:
            admin_user.set_password(admin_password)
            admin_user.save()

        # Sample classes
        classes = []
        for name, code in [('Primary 1', 'P1'), ('Primary 2', 'P2'), ('Primary 3', 'P3')]:
            cls, _ = Class.objects.get_or_create(school=school, name=name, defaults={'code': code})
            classes.append(cls)

        # Sample sections
        for cls in classes:
            Section.objects.get_or_create(
                school=school, school_class=cls, name='A',
                defaults={'room': f'{cls.code}-A', 'capacity': 30},
            )

        # Sample subjects
        subjects = []
        for name, code in [('Mathematics', 'MATH'), ('English', 'ENG'), ('Science', 'SCI')]:
            subject, _ = Subject.objects.get_or_create(
                school=school, code=code, defaults={'name': name}
            )
            subjects.append(subject)

        # Sample staff user + profile
        staff_email = 'teacher@demo-school.example'
        staff_password = 'TeacherPass123!'
        staff_user, staff_created = User.objects.get_or_create(
            email=staff_email,
            defaults={
                'first_name': 'Jane',
                'last_name': 'Doe',
                'role': User.Roles.STAFF,
                'school': school,
                'is_active': True,
            },
        )
        if staff_created:
            staff_user.set_password(staff_password)
            staff_user.save()
        staff, _ = Staff.objects.get_or_create(
            school=school,
            user=staff_user,
            defaults={
                'employee_id': 'DEMO001',
                'designation': 'Class Teacher',
                'department': 'Primary',
            },
        )
        staff.assigned_classes.set(classes[:2])
        staff.assigned_subjects.set(subjects[:2])

        # Sample guardian + students
        guardian_email = 'guardian@demo-school.example'
        guardian_password = 'GuardianPass123!'
        guardian_user, guardian_created = User.objects.get_or_create(
            email=guardian_email,
            defaults={
                'first_name': 'John',
                'last_name': 'Guardian',
                'role': User.Roles.PARENT,
                'school': school,
                'is_active': True,
            },
        )
        if guardian_created:
            guardian_user.set_password(guardian_password)
            guardian_user.save()

        guardian, _ = Guardian.objects.get_or_create(
            school=school,
            user=guardian_user,
            defaults={
                'first_name': 'John',
                'last_name': 'Guardian',
                'relationship': 'father',
            },
        )

        students = []
        for idx, (first, last, adm) in enumerate([
            ('Alice', 'Mwangi', 'DEMO/2025/001'),
            ('Bob', 'Ochieng', 'DEMO/2025/002'),
        ], start=1):
            student, _ = Student.objects.get_or_create(
                school=school,
                admission_number=adm,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'gender': 'female' if idx == 1 else 'male',
                },
            )
            students.append(student)
            GuardianStudent.objects.get_or_create(
                school=school, guardian=guardian, student=student,
                defaults={'relationship': 'father', 'is_primary': True},
            )
            StudentEnrollment.objects.get_or_create(
                school=school,
                student=student,
                session=session,
                term=term,
                defaults={'section': classes[0].sections.first(), 'status': 'active'},
            )

        # Sample timetable entry
        if classes and subjects:
            Timetable.objects.get_or_create(
                school=school,
                section=classes[0].sections.first(),
                subject=subjects[0],
                day='monday',
                start_time=time(8, 0),
                end_time=time(9, 0),
                defaults={'teacher': staff_user, 'room': 'P1-A'},
            )

        # Sample assessment
        Assessment.objects.get_or_create(
            school=school,
            term=term,
            subject=subjects[0],
            school_class=classes[0],
            name='Mid-Term Exam',
            type='exam',
            defaults={'max_score': 100, 'date': today},
        )

        # Sample fee category
        FeeCategory.objects.get_or_create(
            school=school, name='Tuition', defaults={'description': 'Term tuition fee', 'is_mandatory': True}
        )

        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully.'))
        self.stdout.write('School: Demo School of Excellence (subdomain: demo-school)')
        self.stdout.write(f'Admin login: {admin_email} / {admin_password}')
        self.stdout.write(f'Teacher login: {staff_email} / {staff_password}')
        self.stdout.write(f'Guardian login: {guardian_email} / {guardian_password}')
