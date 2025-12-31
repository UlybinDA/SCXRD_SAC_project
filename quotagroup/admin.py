from django.contrib import admin
from django.urls import path
from django.http import HttpResponseRedirect
from .models import QuotaGroup, QuotaTimeTransaction
from django.core.exceptions import ValidationError


@admin.register(QuotaGroup)
class QuotaGroupAdmin(admin.ModelAdmin):
    """
    Django Admin configuration for QuotaGroup model management.

    Provides interface for managing quota groups with custom actions,
    display methods, and custom admin views for quota reset functionality.
    """

    list_display = ('name', 'get_quota_status', 'last_reset')
    search_fields = ('name',)
    list_filter = ('period_time',)
    actions = ['reset_quota_action']

    fieldsets = (
        (None, {
            'fields': ('name', 'main', 'update_time_on_period', 'period_time', 'max_time', 'current_time')
        }),
        ('Даты сброса', {
            'fields': ('last_reset', 'next_reset'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('last_reset',)

    def get_quota_status(self, obj):
        """
        Display quota status description in admin list view.

        Args:
            obj (QuotaGroup): The QuotaGroup instance being displayed.

        Returns:
            str: Human-readable quota status from get_quota_status() method.
        """
        return obj.get_quota_status()

    get_quota_status.short_description = 'Текущий статус'

    def reset_quota_action(self, request, queryset):
        """
        Admin action to reset selected quota groups.

        Applies reset_quota() method to all selected QuotaGroup instances
        in the admin changelist.

        Args:
            request (HttpRequest): The current admin request.
            queryset (QuerySet): Selected QuotaGroup objects.

        Returns:
            None: Displays success message to user.
        """
        for group in queryset:
            group.reset_quota()
        self.message_user(request, "Квоты успешно сброшены")

    reset_quota_action.short_description = "Сбросить выбранные квоты"

    def get_urls(self):
        """
        Define custom admin URLs for quota management.

        Adds custom view endpoint for individual quota reset functionality.

        Returns:
            list: Combined list of custom and default admin URLs.
        """
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/reset/',
                 self.admin_site.admin_view(self.reset_quota_view),
                 name='reset_quota')
        ]
        return custom_urls + urls

    def reset_quota_view(self, request, object_id):
        """
        Custom admin view to reset an individual quota group.

        Provides direct reset functionality from the object's change view.

        Args:
            request (HttpRequest): The current admin request.
            object_id (str): Primary key of the QuotaGroup to reset.

        Returns:
            HttpResponseRedirect: Redirect back to the object's change view.
        """
        group = self.get_object(request, object_id)
        group.reset_quota()
        self.message_user(request, f"Квота {group.name} успешно сброшена")
        return HttpResponseRedirect("../../")


@admin.register(QuotaTimeTransaction)
class QuotaTransferTimeAdmin(admin.ModelAdmin):
    """
    Django Admin configuration for QuotaTimeTransaction model management.

    Provides read-only interface for viewing time transfer transactions
    with filtering and search capabilities.
    """

    list_display = ('user', 'quota_group_donor', 'quota_group_acceptor', 'time_transfer', 'datetime_stamp')
    search_fields = ('user', 'quota_group_donor', 'quota_group_acceptor', 'time_transfer', 'datetime_stamp')
    list_filter = ('user', 'quota_group_donor', 'quota_group_acceptor', 'time_transfer', 'datetime_stamp')
    readonly_fields = ('user', 'quota_group_donor', 'quota_group_acceptor', 'time_transfer', 'datetime_stamp')