from django.test import TestCase
from django.utils import timezone

from academics.models import Class
from attendance.models import Attendance
from schools.models import School
from students.models import Student


class AttendanceModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='S', subdomain='s-att', tier='Sprout')
        self.student = Student.objects.create(
            school=self.school, admission_number='A1',
            first_name='Alice', last_name='Mwangi'
        )
        self.cls = Class.objects.create(school=self.school, name='Class 1')

    def test_attendance_unique(self):
        today = timezone.now().date()
        Attendance.objects.create(
            school=self.school, student=self.student,
            school_class=self.cls, date=today, status='present'
        )
        with self.assertRaises(Exception):
            Attendance.objects.create(
                school=self.school, student=self.student,
                school_class=self.cls, date=today, status='absent'
            )
