from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from apps.common.admin import NoDeleteAdminMixin
from .models import User


class TaraUserCreationForm(BaseUserCreationForm):
    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("email", "full_name", "phone", "is_active", "is_staff")


class TaraUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(NoDeleteAdminMixin, DjangoUserAdmin):
    model = User
    form = TaraUserChangeForm
    add_form = TaraUserCreationForm
    list_display = (
        "email",
        "full_name",
        "phone",
        "is_active",
        "is_staff",
        "is_superuser",
        "last_login",
        "created_at",
    )
    list_filter = ("is_active", "is_staff", "is_superuser", "created_at")
    search_fields = ("email", "full_name", "phone")
    ordering = ("email",)
    date_hierarchy = "created_at"
    readonly_fields = ("id", "last_login", "created_at", "updated_at")
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        ("Kişisel Bilgiler", {"fields": ("full_name", "phone")}),
        (
            "Yetkiler",
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
        ("Kayıt Bilgileri", {"fields": ("last_login", "created_at", "updated_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "phone",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            ro.extend(["is_superuser", "user_permissions", "groups"])
        return tuple(dict.fromkeys(ro))
