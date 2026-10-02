from django.test import TestCase

from academics.models import Class, Section
from schools.models import AcademicSession, School, Term
from students.models import Guardian, Student, StudentEnrollment


class StudentModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='S', subdomain='s', tier='Sprout')
        self.student = Student.objects.create(
            school=self.school, admission_number='S001',
            first_name='Ada', last_name='Lovelace'
        )

    def test_student_unique_admission_number(self):
        with self.assertRaises(Exception):
            Student.objects.create(
                school=self.school, admission_number='S001',
                first_name='Charles', last_name='Babbage'
            )
