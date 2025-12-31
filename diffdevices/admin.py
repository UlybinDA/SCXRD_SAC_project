from django.contrib import admin
from django.urls import path
from django.http import HttpResponseRedirect
from .models import DiffDevice


@admin.register(DiffDevice)
class DiffDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_name', 'is_available', 'time_cons_mult')
    search_fields = ('device_name','is_available')
    list_filter = ('is_available',)
