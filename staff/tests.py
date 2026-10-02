from django.test import TestCase

from accounts.models import User
from schools.models import School
from staff.models import Staff


class StaffModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='S', subdomain='s-staff', tier='Sprout')
        self.user = User.objects.create_user(
            email='staff@s.example', password='x', role=User.Roles.STAFF,
            first_name='Jane', last_name='Doe', school=self.school,
        )

    def test_staff_unique_employee_id(self):
        Staff.objects.create(school=self.school, user=self.user, employee_id='E001')
        user2 = User.objects.create_user(
            email='staff2@s.example', password='x', role=User.Roles.STAFF,
            first_name='John', last_name='Doe', school=self.school,
        )
        with self.assertRaises(Exception):
            Staff.objects.create(school=self.school, user=user2, employee_id='E001')
