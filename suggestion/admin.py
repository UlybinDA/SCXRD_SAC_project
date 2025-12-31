from django.contrib import admin
from .models import Suggestion
from django.utils.translation import gettext_lazy as _

@admin.register(Suggestion)
class ProbeAdmin(admin.ModelAdmin):
    list_display = ('subject','status','date')
    search_fields = ('author','status','date')
    fieldsets = ((_('Информация по предложению'), {
            'fields': (
                'author',
                'subject',
                'text',
                'status',
            )
        }),)

