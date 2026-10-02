"""Library catalog and borrowing."""
from django.db import models

from core.models import TenantModel


class Book(TenantModel):
    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        BORROWED = 'borrowed', 'Borrowed'
        LOST = 'lost', 'Lost'
        DAMAGED = 'damaged', 'Damaged'

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    isbn = models.CharField(max_length=50, blank=True, db_index=True)
    publisher = models.CharField(max_length=255, blank=True)
    published_year = models.PositiveSmallIntegerField(null=True, blank=True)
    copies_total = models.PositiveIntegerField(default=1)
    copies_available = models.PositiveIntegerField(default=1)
    category = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title


class BorrowRecord(TenantModel):
    class Status(models.TextChoices):
        BORROWED = 'borrowed', 'Borrowed'
        RETURNED = 'returned', 'Returned'
        OVERDUE = 'overdue', 'Overdue'

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='borrows')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='borrows')
    borrowed_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField()
    returned_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BORROWED)

    class Meta:
        ordering = ['-borrowed_at']

    def __str__(self):
        return f"{self.student} borrowed {self.book}"
