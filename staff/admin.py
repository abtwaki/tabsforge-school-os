from django.contrib import admin

from .models import Staff


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'user', 'designation', 'department', 'school', 'is_active']
    list_filter = ['school', 'department', 'is_active']
    filter_horizontal = ['assigned_classes', 'assigned_subjects']
