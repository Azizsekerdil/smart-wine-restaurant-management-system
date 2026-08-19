"""Çekirdek uygulama yapılandırması."""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = _("Çekirdek")

    def ready(self) -> None:  # pragma: no cover - Django yaşam döngüsü
        from apps.core import checks  # noqa: F401
