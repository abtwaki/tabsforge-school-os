from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone')}),
        ('TabsForge', {'fields': ('role', 'school', 'is_support')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'school', 'first_name', 'last_name'),
        }),
    )
    list_display = ['email', 'full_name', 'role', 'school', 'is_staff', 'is_active']
    list_filter = ['role', 'is_staff', 'is_superuser', 'school']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    ordering = ['email']
