from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import User


class UserCreationAdminForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "display_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Admin-created users are full accounts; guests come from share links.
        self.fields["email"].required = True


class UserChangeAdminForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeAdminForm
    add_form = UserCreationAdminForm

    list_display = ("email", "display_name", "account_type", "is_staff", "created_at")
    list_filter = ("account_type", "is_staff", "is_superuser", "is_active")
    search_fields = ("email", "display_name", "phone")
    ordering = ("-created_at",)
    readonly_fields = ("last_login", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Profile",
            {
                "fields": (
                    "display_name",
                    "phone",
                    "account_type",
                    "gender",
                    "skill_tier",
                    "main_positions",
                    "sub_positions",
                    "tier_flex_down",
                    "tier_flex_up",
                    "travel_radius_km",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "display_name",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
