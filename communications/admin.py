from django.contrib import admin

from .models import Announcement, Notice


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'status', 'school', 'created_at']
    list_filter = ['school', 'status']


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'priority', 'school', 'is_read', 'created_at']
    list_filter = ['school', 'priority', 'is_read']
