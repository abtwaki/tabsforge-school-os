from django.test import TestCase
from django.utils import timezone

from academics.models import Class, Subject
from gradebook.models import Assessment
from schools.models import AcademicSession, School, Term


class GradebookModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='S', subdomain='s-grade', tier='Sprout')
        self.session = AcademicSession.objects.create(
            school=self.school, name='2025/2026',
            start_date=timezone.now().date(), end_date=timezone.now().date()
        )
        self.term = Term.objects.create(
            school=self.school, session=self.session, name='First Term',
            start_date=timezone.now().date(), end_date=timezone.now().date()
        )
        self.cls = Class.objects.create(school=self.school, name='Class 1')
        self.subject = Subject.objects.create(school=self.school, name='Math', code='MATH')

    def test_assessment_str(self):
        assessment = Assessment.objects.create(
            school=self.school, term=self.term, subject=self.subject,
            school_class=self.cls, name='Mid Term', type='mid_term',
            date=timezone.now().date()
        )
        self.assertIn('Mid Term', str(assessment))
