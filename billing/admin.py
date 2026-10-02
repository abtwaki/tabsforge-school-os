from django.contrib import admin

from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['school', 'tier', 'billing_cycle', 'amount', 'status', 'provider']
    list_filter = ['tier', 'status', 'provider']
    search_fields = ['school__name']
