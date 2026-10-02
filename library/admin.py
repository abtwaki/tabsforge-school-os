from django.contrib import admin

from .models import Book, BorrowRecord


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'isbn', 'copies_available', 'status', 'school']
    search_fields = ['title', 'author', 'isbn']


@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ['book', 'student', 'due_date', 'status', 'school']
    list_filter = ['school', 'status']
