from django.contrib import admin

from .models import Hostel, HostelAllocation, Room


@admin.register(Hostel)
class HostelAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'warden_name']


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['room_number', 'hostel', 'capacity', 'occupied', 'school']


@admin.register(HostelAllocation)
class HostelAllocationAdmin(admin.ModelAdmin):
    list_display = ['student', 'room', 'check_in', 'status', 'school']
