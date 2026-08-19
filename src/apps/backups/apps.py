"""Yedekleme uygulaması yapılandırması."""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BackupsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.backups"
    label = "backups"
    verbose_name = _("Yedekleme")
