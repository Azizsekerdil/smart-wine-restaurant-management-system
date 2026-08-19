"""Şarap kavı uygulaması yapılandırması."""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CellarConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cellar"
    label = "cellar"
    verbose_name = _("Şarap Kavı")
