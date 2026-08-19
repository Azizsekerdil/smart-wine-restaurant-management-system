"""CAIO ajanı uygulama yapılandırması."""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CaioConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.caio"
    label = "caio"
    verbose_name = _("CAIO Ajanı")
