from django.contrib import admin

from .models import AcademicSession, School, Term


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'subdomain', 'custom_domain', 'tier', 'status', 'created_at']
    list_filter = ['tier', 'status']
    search_fields = ['name', 'subdomain', 'custom_domain']


@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'start_date', 'end_date', 'is_current']
    list_filter = ['school', 'is_current']


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ['name', 'session', 'school', 'start_date', 'end_date', 'is_current']
    list_filter = ['school', 'is_current']
