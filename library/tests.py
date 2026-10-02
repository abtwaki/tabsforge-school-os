from django.test import TestCase

from library.models import Book
from schools.models import School


class LibraryModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='S', subdomain='s-lib', tier='Bloom')

    def test_book_str(self):
        book = Book.objects.create(
            school=self.school, title='Python 101', author='Guido',
            isbn='123', copies_total=3, copies_available=3
        )
        self.assertEqual(str(book), 'Python 101')
