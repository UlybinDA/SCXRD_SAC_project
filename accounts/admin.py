from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm


class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser

    list_display = [
        "email",
        "username",
        "last_name",
        "first_name",
        "patronymic",
        "get_laboratory",
        "position",
        "supervisor",
        "is_staff",
    ]

    list_filter = ("position", "laboratory", "is_staff", "is_superuser", "is_active")

    search_fields = ("email", "username", "last_name", "first_name", "patronymic", "laboratory__name")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Персональная информация", {"fields": (
            "last_name",
            "first_name",
            "patronymic",
            "email",
            "laboratory",
            "position",
            "supervisor",
            'lab_permissions'
        )}),
        ("Права", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
        ("Важные даты", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username",
                "password",
                "email",
                "last_name",
                "first_name",
                "patronymic",
                "laboratory",
                "position",
                "supervisor"
            ),
        }),
    )

    def get_laboratory(self, obj):
        """
        Retrieve the name of the laboratory associated with this user for display in the admin interface.
        Args:
            obj: Instance of CustomUser for which the laboratory is being displayed.
        Returns:
            str: Name of the related laboratory, or an empty string if unavailable.
        """
        return obj.laboratory.name

    get_laboratory.short_description = "Лаборатория"
    get_laboratory.admin_order_field = "laboratory__name"


admin.site.register(CustomUser, CustomUserAdmin)
