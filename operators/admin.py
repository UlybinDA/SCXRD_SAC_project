from django.contrib import admin
from .models import Operator


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    """
    Django Admin configuration for Operator model management.

    Provides interface for managing crystallography equipment operators with
    custom display methods for user names and laboratory associations.
    Includes filtering by active status and laboratory, search functionality,
    and read-only timestamp fields.
    """

    list_display = ('code', 'name', 'laboratory', 'is_active')
    list_filter = ('is_active', 'user__laboratory')
    search_fields = ('code', 'user__first_name', 'user__last_name', 'user__patronymic')
    readonly_fields = ('created_at', 'updated_at')

    def name(self, obj):
        """
        Display the full name of the operator's associated user.

        Args:
            obj (Operator): The Operator instance being displayed.

        Returns:
            str: Full name of the associated user.
        """
        return obj.user.get_full_name()

    name.short_description = 'Имя'

    def laboratory(self, obj):
        """
        Display the name of the operator's laboratory.

        Args:
            obj (Operator): The Operator instance being displayed.

        Returns:
            str: Name of the laboratory the operator belongs to.
        """
        return obj.user.laboratory.name

    laboratory.short_description = 'Лаборатория'