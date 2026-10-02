from django.contrib import admin

from .models import Class, ClassSubject, Section, Subject, Timetable


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'school']
    list_filter = ['school']


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'school_class', 'school']
    list_filter = ['school', 'school_class']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'school']
    list_filter = ['school']


@admin.register(ClassSubject)
class ClassSubjectAdmin(admin.ModelAdmin):
    list_display = ['school_class', 'subject', 'teacher', 'school']
    list_filter = ['school', 'school_class']


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ['section', 'subject', 'day', 'start_time', 'end_time']
    list_filter = ['school', 'day']
