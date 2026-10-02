from django.test import TestCase

from academics.models import Class, Subject
from schools.models import School


class AcademicsModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='S1', subdomain='s1', tier='Sprout')

    def test_class_str(self):
        cls = Class.objects.create(school=self.school, name='Primary 1')
        self.assertEqual(str(cls), 'Primary 1')

    def test_subject_unique_code_per_school(self):
        Subject.objects.create(school=self.school, name='Math', code='MATH')
        with self.assertRaises(Exception):
            Subject.objects.create(school=self.school, name='Maths', code='MATH')
