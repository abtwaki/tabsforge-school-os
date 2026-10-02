from django.test import TestCase

from notifications.models import EmailMessage
from schools.models import School


class NotificationModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='S', subdomain='s-notif', tier='Sprout')

    def test_email_str(self):
        email = EmailMessage.objects.create(
            school=self.school, recipient='a@example.com',
            subject='Welcome', body='Hello'
        )
        self.assertIn('Welcome', str(email))
