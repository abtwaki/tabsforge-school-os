from django.test import TestCase

from finance.models import FeeCategory
from schools.models import School


class FinanceModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='S', subdomain='s-fin', tier='Sprout')

    def test_fee_category_unique_per_school(self):
        FeeCategory.objects.create(school=self.school, name='Tuition')
        with self.assertRaises(Exception):
            FeeCategory.objects.create(school=self.school, name='Tuition')
