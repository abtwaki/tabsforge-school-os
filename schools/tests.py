from django.test import TestCase

from schools.models import School


class SchoolModelTests(TestCase):
    def test_subdomain_unique(self):
        School.objects.create(name='Demo School', subdomain='demo', tier='Sprout')
        with self.assertRaises(Exception):
            School.objects.create(name='Demo Two', subdomain='demo', tier='Sprout')
