from django.contrib import admin

from .models import Assessment, Grade, ReportCard


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'subject', 'school_class', 'term', 'school']
    list_filter = ['school', 'type', 'term']


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ['student', 'assessment', 'score', 'school']
    list_filter = ['school', 'assessment__term']


@admin.register(ReportCard)
class ReportCardAdmin(admin.ModelAdmin):
    list_display = ['student', 'term', 'average_score', 'position', 'status']
    list_filter = ['school', 'status']
