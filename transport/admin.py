from django.contrib import admin

from .models import Route, Vehicle, VehicleAssignment


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'start_location', 'end_location']


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['registration_number', 'make', 'model', 'capacity', 'status', 'school']


@admin.register(VehicleAssignment)
class VehicleAssignmentAdmin(admin.ModelAdmin):
    list_display = ['vehicle', 'route', 'driver_name', 'effective_date']
