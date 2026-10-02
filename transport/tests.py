from django.test import TestCase

from schools.models import School
from transport.models import Vehicle


class TransportModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='S', subdomain='s-trans', tier='Summit')

    def test_vehicle_str(self):
        vehicle = Vehicle.objects.create(
            school=self.school, registration_number='KAB 123X',
            make='Toyota', model='Coaster', capacity=30
        )
        self.assertIn('KAB 123X', str(vehicle))
