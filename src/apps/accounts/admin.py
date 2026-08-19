"""Hesap yönetim paneli kayıtları."""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import ApprovalRequest, LoginAttempt, RoleProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "display_name",
        "primary_role",
        "employee_code",
        "is_active",
        "pin_enabled",
        "last_login",
    )
    list_filter = ("primary_role", "is_active", "is_staff", "is_superuser", "groups")
    search_fields = ("username", "display_name", "first_name", "last_name", "employee_code")
    ordering = ("username",)
    readonly_fields = ("pin_hash", "password_changed_at", "failed_login_count", "locked_until")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            _("Kişisel bilgiler"),
            {"fields": ("display_name", "first_name", "last_name", "email", "phone")},
        ),
        (
            _("Görev"),
            {
                "fields": (
                    "primary_role",
                    "employee_code",
                    "discount_limit_percent",
                    "preferred_language",
                )
            },
        ),
        (
            _("Yetkiler"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (
            _("Güvenlik"),
            {
                "fields": (
                    "pin_enabled",
                    "pin_hash",
                    "must_change_password",
                    "password_changed_at",
                    "failed_login_count",
                    "locked_until",
                )
            },
        ),
        (_("Tarihler"), {"fields": ("last_login", "date_joined")}),
        (_("Notlar"), {"fields": ("notes",)}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "display_name", "primary_role", "password1", "password2"),
            },
        ),
    )


@admin.register(RoleProfile)
class RoleProfileAdmin(admin.ModelAdmin):
    list_display = ("code", "name_tr", "name_en", "level", "is_system", "permission_count")
    list_filter = ("level", "is_system")
    search_fields = ("code", "name_tr", "name_en")
    readonly_fields = ("code", "is_system")

    @admin.display(description=_("İzin sayısı"))
    def permission_count(self, obj: RoleProfile) -> int:
        return obj.group.permissions.count()


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("action", "status", "requested_by", "reviewed_by", "created_at", "reviewed_at")
    list_filter = ("status", "action")
    search_fields = ("reason", "review_note", "object_id")
    readonly_fields = ("created_at", "updated_at", "reviewed_at")
    date_hierarchy = "created_at"


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("username", "successful", "method", "ip_address", "timestamp")
    list_filter = ("successful", "method")
    search_fields = ("username", "ip_address")
    date_hierarchy = "timestamp"

    def has_add_permission(self, request: Any) -> bool:
        return False

    def has_change_permission(self, request: Any, obj: Any = None) -> bool:
        return False
