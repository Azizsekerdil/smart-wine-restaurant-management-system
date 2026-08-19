"""Hesap uygulaması yapılandırması."""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = _("Kullanıcılar ve Roller")

    def ready(self) -> None:  # pragma: no cover - Django yaşam döngüsü
        from apps.accounts import signals  # noqa: F401
