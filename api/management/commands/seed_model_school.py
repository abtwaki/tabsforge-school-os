"""
Comprehensive seed command for TabsForge Model School.

Creates a fully populated demo school with:
- 250 students across 14 class levels (Nursery 1-3, Primary 1-5, JSS 1-3, SS 1-3)
- SS streams: Science, Arts, Commercial
- 2 complete academic sessions (2023/2024, 2024/2025) with 3 terms each
- Realistic Nigerian curriculum subjects per level
- ~15 teacher accounts with correct subject assignments
- Guardian/parent accounts linked to students
- Grading scheme (CA1:20, CA2:20, Exam:60) with WAEC-style boundaries
- Full assessment grades and computed result summaries
- ReportCards with class and subject positions
- Fee structures, invoices, and payments
- Attendance history
- Admission number configuration
- Demo application (pending review)
- Task reminders data

Demo credentials:
  Super Admin:  abtwaki@tabsforge.com / Twax@030885
  School Admin: admin@modelschool.tf / Model@2024!
  Teacher:      teacher1@modelschool.tf / Teacher@2024!
  Accountant:   bursar@modelschool.tf / Bursar@2024!
  Parent:       parent1@modelschool.tf / Parent@2024!
  Student:      student1@modelschool.tf / Student@2024!
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from academics.models import Class, ClassSubject, Section, Subject
from admissions.models import AdmissionConfig, Application
from attendance.models import Attendance
from billing.models import Subscription
from finance.models import Expense, FeeCategory, FeeStructure, Invoice, Payment
from gradebook.models import (
    Assessment, Grade, GradeBoundary, GradingScheme, ReportCard, ResultSummary,
)
from homework.models import Assignment, LiveLesson
from messaging.models import Conversation, ConversationParticipant, Message
from schools.models import AcademicSession, School, Term
from staff.models import Staff
from students.models import Guardian, GuardianStudent, Student, StudentEnrollment


# ---------------------------------------------------------------------------
# Seed data constants
# ---------------------------------------------------------------------------

SCHOOL_NAME = 'TabsForge Model School'
SCHOOL_SUBDOMAIN = 'model-school'

# Nigerian first names (common)
MALE_NAMES = [
    'Emeka', 'Chidi', 'Tunde', 'Seun', 'Bola', 'Yemi', 'Kunle', 'Dayo',
    'Femi', 'Gbenga', 'Ayo', 'Niyi', 'Wale', 'Sola', 'Kola', 'Tobi',
    'Uche', 'Nnamdi', 'Obinna', 'Chisom', 'Ikenna', 'Amaka', 'Hassan',
    'Ibrahim', 'Musa', 'Abubakar', 'Suleiman', 'Garba', 'Yakubu', 'Usman',
    'Ahmed', 'Kabiru', 'Lawal', 'Abiola', 'Adebayo', 'Olumide', 'Rotimi',
    'Taiwo', 'Kehinde', 'Babatunde', 'Oluwaseun', 'Oluwafemi', 'Adewale',
]
FEMALE_NAMES = [
    'Ngozi', 'Chioma', 'Adaeze', 'Blessing', 'Favour', 'Grace', 'Joy',
    'Mercy', 'Peace', 'Patience', 'Amara', 'Kemi', 'Bisi', 'Toyin',
    'Funmi', 'Shade', 'Titi', 'Lara', 'Nike', 'Folake', 'Ronke',
    'Halima', 'Fatima', 'Maryam', 'Aisha', 'Zainab', 'Hauwa', 'Rakiya',
    'Bilkisu', 'Ramatu', 'Ruqayyah', 'Sadiya', 'Nafisa', 'Hadiza',
    'Amina', 'Hadijat', 'Mariam', 'Aminat', 'Oluwatobi', 'Adeola',
    'Olabisi', 'Yetunde', 'Titilayo', 'Adunola', 'Oluwakemi',
]
SURNAMES = [
    'Okonkwo', 'Adeyemi', 'Bello', 'Musa', 'Ibrahim', 'Johnson', 'Abubakar',
    'Williams', 'Okafor', 'Nwachukwu', 'Eze', 'Ogbonna', 'Chukwu', 'Nwosu',
    'Obi', 'Obiora', 'Uzodinma', 'Afolabi', 'Ogunleye', 'Adeniran', 'Adebayo',
    'Olawale', 'Fasanya', 'Ajayi', 'Adeleke', 'Akande', 'Adetunji', 'Lawal',
    'Suleiman', 'Yakubu', 'Garba', 'Aliyu', 'Danladi', 'Tanko', 'Sani',
    'Mohammed', 'Abdullahi', 'Usman', 'Idris', 'Ismail', 'Shehu', 'Aminu',
    'Auwal', 'Salisu', 'Liman', 'Haliru', 'Danmusa', 'Nagari',
]

# 14 class levels
CLASS_LEVELS = [
    ('Nursery 1', 'NUR1', 'nursery', 3, 4),
    ('Nursery 2', 'NUR2', 'nursery', 4, 5),
    ('Nursery 3', 'NUR3', 'nursery', 5, 6),
    ('Primary 1', 'PRI1', 'primary', 6, 7),
    ('Primary 2', 'PRI2', 'primary', 7, 8),
    ('Primary 3', 'PRI3', 'primary', 8, 9),
    ('Primary 4', 'PRI4', 'primary', 9, 10),
    ('Primary 5', 'PRI5', 'primary', 10, 11),
    ('JSS 1', 'JSS1', 'jss', 11, 12),
    ('JSS 2', 'JSS2', 'jss', 12, 13),
    ('JSS 3', 'JSS3', 'jss', 13, 14),
    ('SS 1', 'SS1', 'ss', 14, 15),
    ('SS 2', 'SS2', 'ss', 15, 16),
    ('SS 3', 'SS3', 'ss', 16, 17),
]

# SS streams (sections)
SS_STREAMS = ['Science', 'Arts', 'Commercial']

# Subjects per school level
NURSERY_SUBJECTS = ['Numeracy', 'Literacy', 'Creative Play', 'Social Development', 'Physical Development']
PRIMARY_SUBJECTS = [
    'English Studies', 'Mathematics', 'Basic Science', 'Social Studies',
    'Civic Education', 'CRS/IRS', 'Yoruba Language', 'Computer Studies',
    'Cultural & Creative Arts', 'Agricultural Science', 'Physical & Health Education',
]
JSS_SUBJECTS = [
    'English Language', 'Mathematics', 'Basic Science', 'Basic Technology',
    'Business Studies', 'Social Studies', 'Civic Education', 'CRS/IRS',
    'French', 'Computer/ICT', 'Hausa Language', 'Agricultural Science',
]
SS_CORE_SUBJECTS = ['English Language', 'Mathematics', 'Civic Education']
SS_SCIENCE_SUBJECTS = ['Biology', 'Chemistry', 'Physics', 'Further Mathematics', 'Agricultural Science']
SS_ARTS_SUBJECTS = ['Literature-in-English', 'Government', 'CRS/IRS', 'History']
SS_COMMERCE_SUBJECTS = ['Economics', 'Accounting', 'Commerce']

# Fee amounts per class level (NGN)
FEE_BY_LEVEL = {
    'nursery': 45000,
    'primary': 55000,
    'jss': 65000,
    'ss': 75000,
}


class Command(BaseCommand):
    help = 'Seed TabsForge Model School with 250 students and full academic data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='Delete existing model school data before seeding.',
        )

    def handle(self, *args, **options):
        rng = random.Random(42)  # deterministic

        if options['flush']:
            School.objects.filter(subdomain=SCHOOL_SUBDOMAIN).delete()
            self.stdout.write(self.style.WARNING('Existing model school deleted.'))

        self.stdout.write('Creating TabsForge Model School...')

        with transaction.atomic():
            school = self._create_school()
            scheme = self._create_grading_scheme(school)
            self._setup_admission_config(school)
            sessions_and_terms = self._create_sessions(school)
            classes_map, sections_map = self._create_classes(school)
            subjects_map = self._create_subjects(school)
            self._assign_subjects_to_classes(school, classes_map, subjects_map)
            teacher_map = self._create_teachers(school, rng)
            self._assign_teachers_to_subjects(school, classes_map, subjects_map, teacher_map)
            guardian_map, parent_users = self._create_parents(school, rng)
            students = self._create_students(school, classes_map, sections_map, rng)
            self._link_parents_to_students(school, students, guardian_map, rng)
            self._create_enrollments(school, students, sections_map, sessions_and_terms, rng)
            self._create_fee_structures(school, classes_map, sessions_and_terms)
            self._create_grades_and_results(school, students, classes_map, sections_map,
                                            subjects_map, sessions_and_terms, scheme, rng)
            self._create_attendance(school, students, sections_map, sessions_and_terms, rng)
            self._create_invoices_and_payments(school, students, sessions_and_terms, rng)
            self._create_expenses(school, sessions_and_terms, rng)
            self._create_demo_application(school, classes_map)
            self._create_homework(school, classes_map, subjects_map, teacher_map, sessions_and_terms, rng)
            self._create_demo_conversations(school, teacher_map, parent_users, rng)

        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('TabsForge Model School seeded successfully!'))
        self.stdout.write('='*60)
        self.stdout.write('\nDEMO CREDENTIALS:')
        self.stdout.write(f'  Super Admin:   abtwaki@tabsforge.com       / Twax@030885')
        self.stdout.write(f'  School Admin:  admin@modelschool.tf         / Model@2024!')
        self.stdout.write(f'  Teacher:       teacher1@modelschool.tf      / Teacher@2024!')
        self.stdout.write(f'  Accountant:    bursar@modelschool.tf         / Bursar@2024!')
        self.stdout.write(f'  Parent:        parent1@modelschool.tf        / Parent@2024!')
        self.stdout.write(f'  Student:       student1@modelschool.tf       / Student@2024!')
        self.stdout.write('='*60)

    # -------------------------------------------------------------------------
    # School creation
    # -------------------------------------------------------------------------
    def _create_school(self):
        school, created = School.objects.get_or_create(
            subdomain=SCHOOL_SUBDOMAIN,
            defaults={
                'name': SCHOOL_NAME,
                'address': '1 Education Avenue, Minna, Niger State, Nigeria',
                'contact_info': {
                    'phone': '+234 803 000 0001',
                    'email': 'info@modelschool.tf',
                    'website': 'https://modelschool.tf',
                },
                'tier': School.Tiers.SUMMIT,
                'status': School.Status.ACTIVE,
                'primary_color': '#125A0F',
                'secondary_color': '#0B367B',
            },
        )
        if not created:
            self.stdout.write(self.style.WARNING(f'School already exists (pk={school.pk}), continuing with existing.'))

        Subscription.objects.get_or_create(
            school=school,
            defaults={
                'tier': School.Tiers.SUMMIT,
                'billing_cycle': 'termly',
                'amount': Decimal('150000'),
                'currency': 'NGN',
                'status': Subscription.Status.ACTIVE,
                'provider': 'manual',
            },
        )

        # Create admin user
        admin_email = 'admin@modelschool.tf'
        admin, ac = User.objects.get_or_create(
            email=admin_email,
            defaults={
                'first_name': 'Musa',
                'last_name': 'Abdullahi',
                'role': User.Roles.SCHOOL_ADMIN,
                'school': school,
                'is_staff': True,
                'is_active': True,
            },
        )
        if ac:
            admin.set_password('Model@2024!')
            admin.save()

        # Accountant
        bursar_email = 'bursar@modelschool.tf'
        bursar, bc = User.objects.get_or_create(
            email=bursar_email,
            defaults={
                'first_name': 'Ngozi',
                'last_name': 'Adeyemi',
                'role': User.Roles.ACCOUNTANT,
                'school': school,
                'is_active': True,
            },
        )
        if bc:
            bursar.set_password('Bursar@2024!')
            bursar.save()

        self.stdout.write(f'  School: {school.name} (pk={school.pk})')
        return school

    # -------------------------------------------------------------------------
    # Grading scheme
    # -------------------------------------------------------------------------
    def _create_grading_scheme(self, school):
        scheme, _ = GradingScheme.objects.get_or_create(
            school=school, name='WAEC-Style Standard',
            defaults={'is_default': True, 'ca1_weight': 20, 'ca2_weight': 20, 'exam_weight': 60},
        )
        boundaries = [
            ('A1', 'Excellent', 75, 100, 5),
            ('B2', 'Very Good', 70, 74, 4),
            ('B3', 'Good', 65, 69, 3),
            ('C4', 'Credit', 60, 64, 2),
            ('C5', 'Credit', 55, 59, 2),
            ('C6', 'Credit', 50, 54, 2),
            ('D7', 'Pass', 45, 49, 1),
            ('E8', 'Pass', 40, 44, 1),
            ('F9', 'Fail', 0, 39, 0),
        ]
        for label, remark, lo, hi, pts in boundaries:
            GradeBoundary.objects.get_or_create(
                school=school, scheme=scheme, label=label,
                defaults={'remark': remark, 'min_score': lo, 'max_score': hi, 'points': pts},
            )
        self.stdout.write('  Grading scheme: WAEC-Style Standard (CA1:20, CA2:20, Exam:60)')
        return scheme

    # -------------------------------------------------------------------------
    # Admission config
    # -------------------------------------------------------------------------
    def _setup_admission_config(self, school):
        AdmissionConfig.objects.get_or_create(
            school=school,
            defaults={
                'prefix': 'TMS',
                'include_year': True,
                'year_format': '%Y',
                'separator': '/',
                'sequence_digits': 4,
                'current_sequence': 250,  # pre-seeded with 250 students
                'custom_format': '',
            },
        )
        self.stdout.write('  Admission config: TMS/{YEAR}/{SEQUENCE:04d}')

    # -------------------------------------------------------------------------
    # Sessions and terms
    # -------------------------------------------------------------------------
    def _create_sessions(self, school):
        sessions_data = [
            ('2023/2024 Academic Session', date(2023, 9, 11), date(2024, 7, 26), False, [
                ('First Term', date(2023, 9, 11), date(2023, 12, 15), False),
                ('Second Term', date(2024, 1, 8), date(2024, 4, 5), False),
                ('Third Term', date(2024, 4, 22), date(2024, 7, 26), False),
            ]),
            ('2024/2025 Academic Session', date(2024, 9, 9), date(2025, 7, 25), True, [
                ('First Term', date(2024, 9, 9), date(2024, 12, 13), False),
                ('Second Term', date(2025, 1, 6), date(2025, 4, 4), True),
                ('Third Term', date(2025, 4, 28), date(2025, 7, 25), False),
            ]),
        ]
        result = []
        for sname, sstart, send, scurrent, terms_data in sessions_data:
            session, _ = AcademicSession.objects.get_or_create(
                school=school, name=sname,
                defaults={'start_date': sstart, 'end_date': send, 'is_current': scurrent},
            )
            terms = []
            for tname, tstart, tend, tcurrent in terms_data:
                term, _ = Term.objects.get_or_create(
                    school=school, session=session, name=tname,
                    defaults={'start_date': tstart, 'end_date': tend, 'is_current': tcurrent},
                )
                terms.append(term)
            result.append((session, terms))
        self.stdout.write('  Sessions: 2023/2024, 2024/2025 (3 terms each)')
        return result

    # -------------------------------------------------------------------------
    # Classes and sections
    # -------------------------------------------------------------------------
    def _create_classes(self, school):
        classes_map = {}   # code -> Class instance
        sections_map = {}  # (code, stream or 'A') -> Section instance

        for name, code, level_type, min_age, max_age in CLASS_LEVELS:
            cls, _ = Class.objects.get_or_create(
                school=school, name=name,
                defaults={'code': code},
            )
            classes_map[code] = (cls, level_type, min_age, max_age)

            if level_type == 'ss':
                for stream in SS_STREAMS:
                    sec, _ = Section.objects.get_or_create(
                        school=school, school_class=cls, name=stream,
                        defaults={'room': f'{code}-{stream[:3]}', 'capacity': 20},
                    )
                    sections_map[(code, stream)] = sec
            else:
                sec, _ = Section.objects.get_or_create(
                    school=school, school_class=cls, name='A',
                    defaults={'room': f'{code}-A', 'capacity': 30},
                )
                sections_map[(code, 'A')] = sec

        self.stdout.write(f'  Classes: {len(classes_map)} class levels, {len(sections_map)} sections')
        return classes_map, sections_map

    # -------------------------------------------------------------------------
    # Subjects
    # -------------------------------------------------------------------------
    def _create_subjects(self, school):
        all_subjects = sorted(set(
            NURSERY_SUBJECTS + PRIMARY_SUBJECTS + JSS_SUBJECTS +
            SS_CORE_SUBJECTS + SS_SCIENCE_SUBJECTS + SS_ARTS_SUBJECTS + SS_COMMERCE_SUBJECTS
        ))
        subjects_map = {}
        used_codes = set()
        for sname in all_subjects:
            # Generate a unique code
            base = ''.join(w[0] for w in sname.split() if w)[:6].upper()
            base = base.replace('/', '').replace('&', '')
            code = base
            counter = 1
            while code in used_codes:
                code = base[:5] + str(counter)
                counter += 1
            used_codes.add(code)

            subj, _ = Subject.objects.get_or_create(
                school=school, name=sname,
                defaults={'code': code},
            )
            subjects_map[sname] = subj
        self.stdout.write(f'  Subjects: {len(subjects_map)} unique subjects')
        return subjects_map

    # -------------------------------------------------------------------------
    # Assign subjects to classes
    # -------------------------------------------------------------------------
    def _assign_subjects_to_classes(self, school, classes_map, subjects_map):
        assignments = []
        for code, (cls, level_type, _, __) in classes_map.items():
            if level_type == 'nursery':
                subj_list = NURSERY_SUBJECTS
            elif level_type == 'primary':
                subj_list = PRIMARY_SUBJECTS
            elif level_type == 'jss':
                subj_list = JSS_SUBJECTS
            else:  # ss
                subj_list = SS_CORE_SUBJECTS + SS_SCIENCE_SUBJECTS + SS_ARTS_SUBJECTS + SS_COMMERCE_SUBJECTS

            for sname in subj_list:
                if sname in subjects_map:
                    ClassSubject.objects.get_or_create(
                        school=school, school_class=cls, subject=subjects_map[sname],
                    )

    # -------------------------------------------------------------------------
    # Teachers
    # -------------------------------------------------------------------------
    def _create_teachers(self, school, rng):
        teacher_defs = [
            ('teacher1@modelschool.tf', 'Teacher@2024!', 'Ayo', 'Okonkwo', 'T001', 'Mathematics Teacher'),
            ('teacher2@modelschool.tf', 'Teacher@2024!', 'Ngozi', 'Eze', 'T002', 'English Language Teacher'),
            ('teacher3@modelschool.tf', 'Teacher@2024!', 'Emeka', 'Adeyemi', 'T003', 'Basic Science Teacher'),
            ('teacher4@modelschool.tf', 'Teacher@2024!', 'Fatima', 'Bello', 'T004', 'Social Studies Teacher'),
            ('teacher5@modelschool.tf', 'Teacher@2024!', 'Chidi', 'Nwachukwu', 'T005', 'Basic Technology Teacher'),
            ('teacher6@modelschool.tf', 'Teacher@2024!', 'Kemi', 'Adeleke', 'T006', 'Biology/Chemistry Teacher'),
            ('teacher7@modelschool.tf', 'Teacher@2024!', 'Uche', 'Okafor', 'T007', 'Physics Teacher'),
            ('teacher8@modelschool.tf', 'Teacher@2024!', 'Aisha', 'Ibrahim', 'T008', 'Accounting/Commerce Teacher'),
            ('teacher9@modelschool.tf', 'Teacher@2024!', 'Tunde', 'Afolabi', 'T009', 'Literature/CRS Teacher'),
            ('teacher10@modelschool.tf', 'Teacher@2024!', 'Grace', 'Lawal', 'T010', 'Nursery/Primary Class Teacher'),
            ('teacher11@modelschool.tf', 'Teacher@2024!', 'Musa', 'Danladi', 'T011', 'Government/History Teacher'),
            ('teacher12@modelschool.tf', 'Teacher@2024!', 'Amara', 'Obi', 'T012', 'Economics Teacher'),
            ('teacher13@modelschool.tf', 'Teacher@2024!', 'Seun', 'Fasanya', 'T013', 'Computer/ICT Teacher'),
            ('teacher14@modelschool.tf', 'Teacher@2024!', 'Halima', 'Suleiman', 'T014', 'Agricultural Science Teacher'),
            ('teacher15@modelschool.tf', 'Teacher@2024!', 'Wale', 'Adebayo', 'T015', 'French/Languages Teacher'),
        ]

        teacher_map = {}
        for email, pwd, first, last, emp_id, designation in teacher_defs:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first, 'last_name': last,
                    'role': User.Roles.STAFF, 'school': school, 'is_active': True,
                },
            )
            if created:
                user.set_password(pwd)
                user.save()

            staff, _ = Staff.objects.get_or_create(
                school=school, user=user,
                defaults={
                    'employee_id': emp_id, 'designation': designation,
                    'department': 'Teaching Staff', 'date_joined': date(2020, 9, 1),
                },
            )
            teacher_map[emp_id] = (user, staff)

        self.stdout.write(f'  Teachers: {len(teacher_map)} staff accounts')
        return teacher_map

    # -------------------------------------------------------------------------
    # Assign teachers to subjects/classes
    # -------------------------------------------------------------------------
    def _assign_teachers_to_subjects(self, school, classes_map, subjects_map, teacher_map):
        # T001 = Maths, T002 = English, T003 = Science, T004 = Social, T005 = Basic Tech
        # T006 = Bio/Chem, T007 = Physics, T008 = Accts/Commerce, T009 = Lit/CRS
        # T010 = Nursery/Primary class teacher, T011 = Govt/History, T012 = Economics
        # T013 = Computer/ICT, T014 = Agricultural Sci, T015 = French/Languages
        teacher_subject_map = {
            'Mathematics': 'T001', 'Further Mathematics': 'T001',
            'English Language': 'T002', 'English Studies': 'T002', 'Literacy': 'T002',
            'Basic Science': 'T003', 'Biology': 'T006', 'Chemistry': 'T006',
            'Physics': 'T007',
            'Social Studies': 'T004', 'Civic Education': 'T004',
            'Basic Technology': 'T005',
            'Accounting': 'T008', 'Commerce': 'T008', 'Business Studies': 'T008',
            'Literature-in-English': 'T009', 'CRS/IRS': 'T009',
            'Numeracy': 'T010', 'Creative Play': 'T010', 'Social Development': 'T010',
            'Physical Development': 'T010', 'Cultural & Creative Arts': 'T010',
            'Physical & Health Education': 'T010',
            'Government': 'T011', 'History': 'T011',
            'Economics': 'T012',
            'Computer Studies': 'T013', 'Computer/ICT': 'T013',
            'Agricultural Science': 'T014',
            'French': 'T015', 'Hausa Language': 'T015', 'Yoruba Language': 'T015',
        }

        for code, (cls, level_type, _, __) in classes_map.items():
            for sname, tid in teacher_subject_map.items():
                if sname in subjects_map:
                    cs = ClassSubject.objects.filter(
                        school=school, school_class=cls, subject=subjects_map[sname],
                    ).first()
                    if cs:
                        user, staff = teacher_map.get(tid, (None, None))
                        if user:
                            cs.teacher = user
                            cs.save(update_fields=['teacher'])
                            staff.assigned_classes.add(cls)
                            staff.assigned_subjects.add(subjects_map[sname])

    # -------------------------------------------------------------------------
    # Parents / guardians
    # -------------------------------------------------------------------------
    def _create_parents(self, school, rng):
        # Create 30 parent accounts; each parent will have ~8-9 children
        guardian_map = {}
        parent_users = []

        # Named demo parent
        demo_parent, dc = User.objects.get_or_create(
            email='parent1@modelschool.tf',
            defaults={
                'first_name': 'Abdullahi', 'last_name': 'Bello',
                'role': User.Roles.PARENT, 'school': school, 'is_active': True,
            },
        )
        if dc:
            demo_parent.set_password('Parent@2024!')
            demo_parent.save()
        demo_guardian, _ = Guardian.objects.get_or_create(
            school=school, user=demo_parent,
            defaults={
                'first_name': 'Abdullahi', 'last_name': 'Bello',
                'phone': '+2348012345678', 'email': 'parent1@modelschool.tf',
                'relationship': 'father',
            },
        )
        guardian_map['parent1@modelschool.tf'] = demo_guardian
        parent_users.append(demo_parent)

        for i in range(2, 31):
            first = rng.choice(MALE_NAMES if rng.random() > 0.4 else FEMALE_NAMES)
            last = rng.choice(SURNAMES)
            email = f'parent{i}@modelschool.tf'
            user, uc = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first, 'last_name': last,
                    'role': User.Roles.PARENT, 'school': school, 'is_active': True,
                },
            )
            if uc:
                user.set_password('Parent@2024!')
                user.save()
            guardian, _ = Guardian.objects.get_or_create(
                school=school, user=user,
                defaults={
                    'first_name': first, 'last_name': last,
                    'phone': f'+234801{rng.randint(1000000, 9999999)}',
                    'email': email,
                    'relationship': rng.choice(['father', 'mother', 'guardian']),
                },
            )
            guardian_map[email] = guardian
            parent_users.append(user)

        self.stdout.write(f'  Parents: 30 guardian accounts')
        return guardian_map, parent_users

    # -------------------------------------------------------------------------
    # Students (250)
    # -------------------------------------------------------------------------
    def _create_students(self, school, classes_map, sections_map, rng):
        # Distribution: 14 levels, ~17-18 each, total 250
        # Nursery 1-3: 18 each = 54; Primary 1-5: 17 each = 85; JSS 1-3: 18 each = 54; SS 1-3: 19 each = 57
        # Total: 54+85+54+57 = 250 ✓
        distribution = {
            'NUR1': 18, 'NUR2': 18, 'NUR3': 18,
            'PRI1': 17, 'PRI2': 17, 'PRI3': 17, 'PRI4': 17, 'PRI5': 17,
            'JSS1': 18, 'JSS2': 18, 'JSS3': 18,
            'SS1': 19, 'SS2': 19, 'SS3': 19,
        }

        # Demo student user
        demo_student_user, dsu = User.objects.get_or_create(
            email='student1@modelschool.tf',
            defaults={
                'first_name': 'Aminu', 'last_name': 'Bello',
                'role': User.Roles.STUDENT, 'school': school, 'is_active': True,
            },
        )
        if dsu:
            demo_student_user.set_password('Student@2024!')
            demo_student_user.save()

        all_students = []
        seq = 1

        for code, (cls, level_type, min_age, max_age) in classes_map.items():
            count = distribution.get(code, 18)

            for idx in range(count):
                gender = 'male' if rng.random() > 0.48 else 'female'
                first = rng.choice(MALE_NAMES if gender == 'male' else FEMALE_NAMES)
                last = rng.choice(SURNAMES)
                adm_num = f'TMS/2024/{seq:04d}'

                # Approximate age based on class level
                age_years = rng.randint(min_age, max_age)
                birth_year = date.today().year - age_years
                birth_month = rng.randint(1, 12)
                birth_day = rng.randint(1, 28)
                dob = date(birth_year, birth_month, birth_day)

                student, created = Student.objects.get_or_create(
                    school=school, admission_number=adm_num,
                    defaults={
                        'first_name': first, 'last_name': last,
                        'date_of_birth': dob, 'gender': gender,
                        'address': f'{rng.randint(1, 100)} {rng.choice(SURNAMES)} Street, Minna',
                    },
                )

                # Link demo student user to first student
                if seq == 1 and created:
                    student.user = demo_student_user
                    student.save(update_fields=['user'])

                all_students.append((student, code, level_type))
                seq += 1

        self.stdout.write(f'  Students: {len(all_students)} created (seq 1–{seq-1})')
        return all_students

    # -------------------------------------------------------------------------
    # Link parents to students
    # -------------------------------------------------------------------------
    def _link_parents_to_students(self, school, students, guardian_map, rng):
        guardians = list(guardian_map.values())
        total = len(guardians)
        for i, (student, code, level_type) in enumerate(students):
            # Each guardian gets ~8-9 children
            guardian = guardians[i % total]
            GuardianStudent.objects.get_or_create(
                school=school, guardian=guardian, student=student,
                defaults={'relationship': guardian.relationship, 'is_primary': True},
            )

    # -------------------------------------------------------------------------
    # Student enrollments (across all sessions & terms)
    # -------------------------------------------------------------------------
    def _create_enrollments(self, school, students, sections_map, sessions_and_terms, rng):
        for session, terms in sessions_and_terms:
            for term in terms:
                for student, code, level_type in students:
                    if level_type == 'ss':
                        # Split into streams based on student index
                        stream = SS_STREAMS[list(dict.fromkeys(
                            c for s, c, lt in students if c == code
                        ).keys()).index(code) % 3] if False else None
                        # Simpler: distribute by student pk mod 3
                        stream = SS_STREAMS[student.pk % 3]
                        section = sections_map.get((code, stream))
                    else:
                        section = sections_map.get((code, 'A'))

                    if section:
                        StudentEnrollment.objects.get_or_create(
                            school=school, student=student,
                            session=session, term=term,
                            defaults={
                                'section': section,
                                'status': StudentEnrollment.Status.ACTIVE,
                            },
                        )

    # -------------------------------------------------------------------------
    # Fee structures
    # -------------------------------------------------------------------------
    def _create_fee_structures(self, school, classes_map, sessions_and_terms):
        tuition_cat, _ = FeeCategory.objects.get_or_create(
            school=school, name='Tuition',
            defaults={'description': 'Term tuition fee', 'is_mandatory': True},
        )
        pta_cat, _ = FeeCategory.objects.get_or_create(
            school=school, name='PTA Levy',
            defaults={'description': 'Parent-Teacher Association levy', 'is_mandatory': True},
        )
        dev_cat, _ = FeeCategory.objects.get_or_create(
            school=school, name='Development Levy',
            defaults={'description': 'School development fund', 'is_mandatory': False},
        )

        for session, terms in sessions_and_terms:
            for term in terms:
                for code, (cls, level_type, _, __) in classes_map.items():
                    base_fee = FEE_BY_LEVEL[level_type]
                    FeeStructure.objects.get_or_create(
                        school=school, category=tuition_cat, school_class=cls, term=term,
                        name=f'Tuition - {cls.name}',
                        defaults={'amount': base_fee, 'due_date': term.start_date + timedelta(days=14)},
                    )
                    FeeStructure.objects.get_or_create(
                        school=school, category=pta_cat, school_class=cls, term=term,
                        name=f'PTA - {cls.name}',
                        defaults={'amount': 2000, 'due_date': term.start_date + timedelta(days=14)},
                    )

    # -------------------------------------------------------------------------
    # Assessment grades and result computation
    # -------------------------------------------------------------------------
    def _create_grades_and_results(self, school, students, classes_map, sections_map,
                                   subjects_map, sessions_and_terms, scheme, rng):
        from api.result_engine import compute_results_for_term

        # Only do grades for completed terms (not future terms)
        today = date.today()
        done_count = 0

        for session, terms in sessions_and_terms:
            for term in terms:
                if term.end_date > today:
                    continue  # skip future terms

                self.stdout.write(f'    Computing results for {term.name} {session.name}...')

                for student, code, level_type in students:
                    cls, _, _, __ = classes_map[code]

                    if level_type == 'nursery':
                        subj_list = NURSERY_SUBJECTS
                    elif level_type == 'primary':
                        subj_list = PRIMARY_SUBJECTS
                    elif level_type == 'jss':
                        subj_list = JSS_SUBJECTS
                    else:
                        # SS: core + stream-specific
                        stream_idx = student.pk % 3
                        if stream_idx == 0:
                            subj_list = SS_CORE_SUBJECTS + SS_SCIENCE_SUBJECTS
                        elif stream_idx == 1:
                            subj_list = SS_CORE_SUBJECTS + SS_ARTS_SUBJECTS
                        else:
                            subj_list = SS_CORE_SUBJECTS + SS_COMMERCE_SUBJECTS

                    for sname in subj_list:
                        if sname not in subjects_map:
                            continue
                        subject = subjects_map[sname]

                        # Generate realistic scores with some variation
                        base = rng.gauss(65, 15)
                        ca1_raw = max(0, min(20, rng.gauss(base * 0.2, 3)))
                        ca2_raw = max(0, min(20, rng.gauss(base * 0.2, 3)))
                        exam_raw = max(0, min(60, rng.gauss(base * 0.6, 8)))

                        # CA1 assessment
                        ca1_assess, _ = Assessment.objects.get_or_create(
                            school=school, term=term, subject=subject, school_class=cls,
                            name='CA1', type='ca1',
                            defaults={'max_score': 20, 'date': term.start_date + timedelta(days=30)},
                        )
                        Grade.objects.get_or_create(
                            school=school, assessment=ca1_assess, student=student,
                            defaults={'score': round(ca1_raw, 1)},
                        )

                        # CA2 assessment
                        ca2_assess, _ = Assessment.objects.get_or_create(
                            school=school, term=term, subject=subject, school_class=cls,
                            name='CA2', type='ca2',
                            defaults={'max_score': 20, 'date': term.start_date + timedelta(days=60)},
                        )
                        Grade.objects.get_or_create(
                            school=school, assessment=ca2_assess, student=student,
                            defaults={'score': round(ca2_raw, 1)},
                        )

                        # Exam assessment
                        exam_assess, _ = Assessment.objects.get_or_create(
                            school=school, term=term, subject=subject, school_class=cls,
                            name='Examination', type='exam',
                            defaults={'max_score': 60, 'date': term.end_date - timedelta(days=7)},
                        )
                        Grade.objects.get_or_create(
                            school=school, assessment=exam_assess, student=student,
                            defaults={'score': round(exam_raw, 1)},
                        )

                    done_count += 1

                # Run the result engine for this term
                try:
                    count = compute_results_for_term(school, term)
                    self.stdout.write(f'      Computed {count} result summaries.')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'      Result engine error: {e}'))

        self.stdout.write(f'  Grades: created for all completed terms')

    # -------------------------------------------------------------------------
    # Attendance history (last 60 school days)
    # -------------------------------------------------------------------------
    def _create_attendance(self, school, students, sections_map, sessions_and_terms, rng):
        today = date.today()
        school_days = []
        check = today - timedelta(days=90)
        while check <= today:
            if check.weekday() < 5:  # Mon-Fri
                school_days.append(check)
            check += timedelta(days=1)
        school_days = school_days[-60:]  # last 60 school days

        count = 0
        for adate in school_days[-30:]:  # only create for last 30 days (faster)
            for student, code, level_type in students:
                if level_type == 'ss':
                    stream = SS_STREAMS[student.pk % 3]
                    section = sections_map.get((code, stream))
                else:
                    section = sections_map.get((code, 'A'))

                if not section:
                    continue

                cls = section.school_class

                # 90% attendance rate with some variation
                rand = rng.random()
                if rand < 0.88:
                    att_status = Attendance.Status.PRESENT
                elif rand < 0.93:
                    att_status = Attendance.Status.LATE
                elif rand < 0.97:
                    att_status = Attendance.Status.EXCUSED
                else:
                    att_status = Attendance.Status.ABSENT

                Attendance.objects.get_or_create(
                    school=school, student=student, school_class=cls, date=adate,
                    defaults={'status': att_status},
                )
                count += 1

        self.stdout.write(f'  Attendance: {count} records created (last 30 school days)')

    # -------------------------------------------------------------------------
    # Invoices and payments
    # -------------------------------------------------------------------------
    def _create_invoices_and_payments(self, school, students, sessions_and_terms, rng):
        today = date.today()
        inv_seq = 1

        for session, terms in sessions_and_terms:
            for term in terms:
                if term.start_date > today:
                    continue  # skip future terms

                for student, code, level_type in students:
                    base_fee = FEE_BY_LEVEL.get(level_type, 55000)
                    total = Decimal(str(base_fee + 2000))  # tuition + PTA

                    inv_num = f'INV/{term.start_date.year}{term.name[:1]}/{student.pk:04d}'
                    inv, created = Invoice.objects.get_or_create(
                        school=school, student=student, term=term,
                        defaults={
                            'invoice_number': inv_num,
                            'due_date': term.start_date + timedelta(days=14),
                            'total_amount': total,
                            'amount_paid': Decimal('0'),
                            'status': Invoice.Status.SENT,
                        },
                    )

                    if created:
                        inv_seq += 1
                        # Simulate payment (80% fully paid, 10% partial, 10% unpaid)
                        rand = rng.random()
                        if rand < 0.80:
                            Payment.objects.create(
                                school=school, invoice=inv,
                                amount=total, method='bank_transfer',
                                reference=f'REF{rng.randint(100000, 999999)}',
                            )
                            inv.amount_paid = total
                            inv.status = Invoice.Status.PAID
                            inv.save(update_fields=['amount_paid', 'status'])
                        elif rand < 0.90:
                            partial = total * Decimal('0.5')
                            Payment.objects.create(
                                school=school, invoice=inv,
                                amount=partial, method='cash',
                            )
                            inv.amount_paid = partial
                            inv.status = Invoice.Status.PARTIAL
                            inv.save(update_fields=['amount_paid', 'status'])
                        else:
                            if term.end_date < today:
                                inv.status = Invoice.Status.OVERDUE
                                inv.save(update_fields=['status'])

        self.stdout.write('  Invoices and payments: created for all terms')

    # -------------------------------------------------------------------------
    # School expenses
    # -------------------------------------------------------------------------
    def _create_expenses(self, school, sessions_and_terms, rng):
        today = date.today()
        for session, terms in sessions_and_terms:
            for term in terms:
                if term.start_date > today:
                    continue
                expense_list = [
                    ('Staff Salaries', 'salaries', 850000),
                    ('Electricity Bills', 'utilities', 45000),
                    ('Water Supply', 'utilities', 12000),
                    ('Classroom Maintenance', 'maintenance', 80000),
                    ('Cleaning Supplies', 'supplies', 18000),
                    ('Sports Equipment', 'supplies', 35000),
                    ('Generator Fuel', 'utilities', 60000),
                    ('Internet Subscription', 'utilities', 25000),
                    ('Staff Transport Allowance', 'transport', 40000),
                    ('School Bus Maintenance', 'maintenance', 95000),
                ]
                for title, cat, amount in expense_list:
                    Expense.objects.get_or_create(
                        school=school, title=title, term=term,
                        expense_date=term.start_date + timedelta(days=rng.randint(5, 30)),
                        defaults={'category': cat, 'amount': Decimal(str(amount))},
                    )
        self.stdout.write('  Expenses: created for all completed terms')

    # -------------------------------------------------------------------------
    # Demo pending application
    # -------------------------------------------------------------------------
    def _create_demo_application(self, school, classes_map):
        from schools.models import AcademicSession
        session = AcademicSession.objects.filter(school=school, is_current=True).first()
        cls_tuple = classes_map.get('PRI1')
        if not session or not cls_tuple:
            return
        cls = cls_tuple[0]
        Application.objects.get_or_create(
            school=school,
            first_name='Zara',
            last_name='Mohammed',
            date_of_birth=date(2018, 3, 15),
            session=session,
            defaults={
                'gender': 'female',
                'applying_for_class': cls,
                'guardian_name': 'Ibrahim Mohammed',
                'guardian_relationship': 'father',
                'guardian_phone': '+2348034567890',
                'guardian_email': 'ibrahim.m@example.com',
                'status': Application.Status.PENDING,
                'previous_school': 'Little Stars Nursery School',
                'previous_class': 'Nursery 3',
                'additional_info': 'Child is well-behaved and loves reading.',
            },
        )
        self.stdout.write('  Demo application: 1 pending application created')

    # -------------------------------------------------------------------------
    # Homework assignments
    # -------------------------------------------------------------------------
    def _create_homework(self, school, classes_map, subjects_map, teacher_map, sessions_and_terms, rng):
        _, latest = sessions_and_terms[-1]
        current_term = next((t for t in latest if t.is_current), latest[0])

        hw_data = [
            ('JSS1', 'Mathematics', 'Algebra Basics - Practice Sheet', 'Solve all questions on page 45', 30),
            ('JSS2', 'English Language', 'Comprehension Exercise', 'Read the passage and answer all questions', 30),
            ('SS1', 'Physics', 'Newton\'s Laws - Problem Set', 'Complete the 10 problems on motion', 40),
            ('SS2', 'Economics', 'Demand & Supply Essay', 'Write a 500-word essay on market equilibrium', 50),
            ('PRI3', 'Mathematics', 'Multiplication Tables', 'Practise tables from 6 to 12', 20),
        ]

        t1_user, t1_staff = teacher_map.get('T001', (None, None))
        for code, sname, title, desc, pts in hw_data:
            cls_tuple = classes_map.get(code)
            if not cls_tuple or sname not in subjects_map:
                continue
            cls = cls_tuple[0]
            Assignment.objects.get_or_create(
                school=school, school_class=cls, subject=subjects_map[sname],
                term=current_term, title=title,
                defaults={
                    'description': desc,
                    'type': 'homework',
                    'due_date': date.today() + timedelta(days=rng.randint(-3, 7)),
                    'max_points': pts,
                    'teacher': t1_user,
                    'is_published': True,
                },
            )

        # A live lesson
        t2_user, _ = teacher_map.get('T002', (None, None))
        jss2 = classes_map.get('JSS2')
        eng_subj = subjects_map.get('English Language')
        if jss2 and eng_subj and t2_user:
            import datetime
            LiveLesson.objects.get_or_create(
                school=school, school_class=jss2[0], subject=eng_subj,
                title='Essay Writing Masterclass',
                defaults={
                    'description': 'Live lesson on how to write a compelling essay.',
                    'teacher': t2_user,
                    'scheduled_at': timezone.now() + timedelta(days=2),
                    'duration_minutes': 45,
                    'status': LiveLesson.Status.SCHEDULED,
                },
            )
        self.stdout.write('  Homework: 5 assignments + 1 live lesson created')

    # -------------------------------------------------------------------------
    # Demo conversations
    # -------------------------------------------------------------------------
    def _create_demo_conversations(self, school, teacher_map, parent_users, rng):
        from accounts.models import User
        admin = User.objects.filter(school=school, role=User.Roles.SCHOOL_ADMIN).first()
        t1_user, _ = teacher_map.get('T001', (None, None))
        parent1 = parent_users[0] if parent_users else None

        if not all([admin, t1_user, parent1]):
            return

        # 1:1 parent ↔ teacher
        conv1, _ = Conversation.objects.get_or_create(
            school=school, name='', is_group=False,
            created_by=parent1,
        )
        for u in [parent1, t1_user]:
            ConversationParticipant.objects.get_or_create(
                school=school, conversation=conv1, user=u,
                defaults={'is_admin': (u == parent1)},
            )

        # Add some messages
        msgs = [
            (parent1, 'Good morning. I would like to know about my child\'s progress in Mathematics.'),
            (t1_user, 'Good morning. Aminu is making steady progress. His CA scores are quite good.'),
            (parent1, 'Thank you so much. We are glad to hear that. Is there anything we can do at home?'),
            (t1_user, 'Please encourage him to practise past questions. I will share some materials.'),
        ]
        for sender, content in msgs:
            Message.objects.get_or_create(
                school=school, conversation=conv1, sender=sender,
                content=content,
                defaults={},
            )

        # Group conversation: Admin + 3 teachers
        grp, _ = Conversation.objects.get_or_create(
            school=school, name='Staff Meeting Room', is_group=True,
            created_by=admin,
        )
        for u in [admin, t1_user]:
            ConversationParticipant.objects.get_or_create(
                school=school, conversation=grp, user=u,
                defaults={'is_admin': (u == admin)},
            )
        t2_user, _ = teacher_map.get('T002', (None, None))
        if t2_user:
            ConversationParticipant.objects.get_or_create(
                school=school, conversation=grp, user=t2_user,
                defaults={'is_admin': False},
            )
        Message.objects.get_or_create(
            school=school, conversation=grp, sender=admin,
            content='Reminder: Staff meeting this Friday at 2pm. Please be present.',
            defaults={},
        )
        Message.objects.get_or_create(
            school=school, conversation=grp, sender=t1_user,
            content='Noted, thank you.',
            defaults={},
        )

        self.stdout.write('  Messaging: 1:1 parent<->teacher + staff group conversation created')
