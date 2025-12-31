from django.contrib import admin
from .models import Laboratory
from quotagroup.models import QuotaGroup


@admin.register(Laboratory)
class LaboratoryAdmin(admin.ModelAdmin):
    """
    Django Admin configuration for Laboratory model management.

    Provides interface for managing research laboratories with custom display,
    search, filtering, and autocomplete functionality for quota group assignment.
    """

    list_display = ("short_name", "organization", "city", "country", "quota_group_display")
    search_fields = ("short_name", "organization", "city", "country", "quota_group__name")
    list_filter = ("country", "city", "quota_group")
    readonly_fields = ("users_list",)


    autocomplete_fields = ['quota_group']

    def users_list(self, obj):
        """
        Generate comma-separated list of usernames for this laboratory.

        Args:
            obj (Laboratory): The Laboratory instance being displayed.

        Returns:
            str: Comma-separated list of usernames belonging to this laboratory.
        """
        return ", ".join([user.username for user in obj.users.all()])

    users_list.short_description = "Пользователи"


    def quota_group_display(self, obj):
        """
        Display the quota group name or dash if none is assigned.

        Args:
            obj (Laboratory): The Laboratory instance being displayed.

        Returns:
            str: Quota group name or "-" if no quota group is assigned.
        """
        return obj.quota_group.name if obj.quota_group else "-"

    quota_group_display.short_description = "Группа квот"
    quota_group_display.admin_order_field = "quota_group__name"

    fieldsets = (
        (None, {"fields": ("name", "lab_code", "organization", "country", "city", 'short_name')}),
        ("Квоты", {"fields": ("quota_group",)}),
        ("Дополнительно", {"fields": ("users_list",)}),
    )