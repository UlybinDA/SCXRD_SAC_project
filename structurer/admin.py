from django.contrib import admin
from .models import Structurer


@admin.register(Structurer)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)

    def name(self, obj):
        return obj.user.get_full_name()
