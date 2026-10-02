from django.contrib import admin

from .models import Guardian, GuardianStudent, Student, StudentEnrollment


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['admission_number', 'first_name', 'last_name', 'school']
    search_fields = ['admission_number', 'first_name', 'last_name']
    list_filter = ['school', 'gender']


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'phone', 'school']
    search_fields = ['first_name', 'last_name', 'phone']


@admin.register(GuardianStudent)
class GuardianStudentAdmin(admin.ModelAdmin):
    list_display = ['guardian', 'student', 'relationship', 'is_primary']


@admin.register(StudentEnrollment)
class StudentEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'section', 'term', 'status']
    list_filter = ['school', 'status']
