from django.contrib import admin

from .models import EmailMessage, SMSMessage


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'subject', 'status', 'school', 'created_at']
    list_filter = ['school', 'status']


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'status', 'school', 'created_at']
    list_filter = ['school', 'status']
