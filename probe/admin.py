from django.contrib import admin
from  .models import Probe



@admin.register(Probe)
class ProbeAdmin(admin.ModelAdmin):
    list_display = ('application', 'color1', 'volume','smpl_type','dmin')


