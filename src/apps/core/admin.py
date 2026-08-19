"""Çekirdek yönetim paneli kayıtları."""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.core.models import AppSetting, AuditLog, FeatureFlag


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Denetim kaydı yalnızca okunabilir."""

    list_display = ("timestamp", "actor_label", "action", "severity", "object_repr", "success")
    list_filter = ("action", "severity", "success")
    search_fields = ("actor_label", "object_repr", "message", "object_id")
    date_hierarchy = "timestamp"
    readonly_fields = [field.name for field in AuditLog._meta.fields]

    def has_add_permission(self, request: Any) -> bool:
        return False

    def has_change_permission(self, request: Any, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: Any, obj: Any = None) -> bool:
        return False


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "category", "label", "display_value", "is_secret", "is_experimental")
    list_filter = ("category", "is_secret", "is_experimental")
    search_fields = ("key", "label")
    exclude = ("secret_value",)

    @admin.display(description=_("Değer"))
    def display_value(self, obj: AppSetting) -> str:
        return obj.display_value


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "module", "status")
    list_filter = ("status", "module")
    search_fields = ("code", "name", "description")
