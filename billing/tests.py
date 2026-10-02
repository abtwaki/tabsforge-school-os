from django.test import SimpleTestCase

from .providers import size_tier_for, termly_price


class PricingTests(SimpleTestCase):
    def test_size_tier_boundaries(self):
        self.assertEqual(size_tier_for(50)['key'], 'tier_1')
        self.assertEqual(size_tier_for(499)['rate'], 2700)
        self.assertEqual(size_tier_for(500)['rate'], 2250)
        self.assertEqual(size_tier_for(999)['setup_fee'], 100000)
        self.assertEqual(size_tier_for(1000)['rate'], 1750)

    def test_first_fifty_students_are_free_in_first_term(self):
        self.assertEqual(termly_price(50, first_term=True)['subscription_amount'], 0)
        pricing = termly_price(51, first_term=True)
        self.assertEqual(pricing['free_students'], 50)
        self.assertEqual(pricing['billable_students'], 1)
        self.assertEqual(pricing['subscription_amount'], 2700)

    def test_later_terms_charge_every_active_student(self):
        pricing = termly_price(500)
        self.assertEqual(pricing['billable_students'], 500)
        self.assertEqual(pricing['subscription_amount'], 1125000)
