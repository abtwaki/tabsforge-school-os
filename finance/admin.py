from django.contrib import admin

from .models import FeeCategory, FeeStructure, Invoice, Payment


@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'is_mandatory']


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['name', 'school_class', 'term', 'amount', 'school']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'student', 'term', 'total_amount', 'status', 'school']
    list_filter = ['school', 'status']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'amount', 'method', 'paid_at']
