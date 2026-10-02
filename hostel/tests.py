from django.test import TestCase

from hostel.models import Hostel
from schools.models import School


class HostelModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='S', subdomain='s-hostel', tier='Summit')

    def test_hostel_str(self):
        hostel = Hostel.objects.create(school=self.school, name='Boys Hostel')
        self.assertEqual(str(hostel), 'Boys Hostel')
