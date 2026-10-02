from django.test import TestCase

from accounts.models import User
from communications.models import Announcement
from schools.models import School


class CommunicationsModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='S', subdomain='s-comms', tier='Sprout')
        self.user = User.objects.create_user(
            email='admin@s.example', password='x', role=User.Roles.SCHOOL_ADMIN,
            first_name='Admin', last_name='User', school=self.school,
        )

    def test_announcement_str(self):
        ann = Announcement.objects.create(
            school=self.school, title='Holiday', content='School closed.',
            author=self.user
        )
        self.assertEqual(str(ann), 'Holiday')
