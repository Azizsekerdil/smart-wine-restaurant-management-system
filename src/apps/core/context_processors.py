"""Şablonlara ortak bağlam sağlayan işlemciler."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest

from winehouse import __version__


def app_context(request: HttpRequest) -> dict[str, Any]:
    """Her şablonda kullanılabilen uygulama bağlamı."""
    user = getattr(request, "user", None)
    ai = getattr(settings, "AI_SETTINGS", {})
    devstudio = getattr(settings, "DEVSTUDIO", {})

    return {
        "APP_NAME": "Wine House",
        "APP_VERSION": __version__,
        "APP_SUBTITLE_TR": "Akıllı Şarap Restoranı Yönetim Sistemi",
        "APP_SUBTITLE_EN": "Smart Wine Restaurant Management System",
        "CURRENCY_SYMBOL": getattr(settings, "WINEHOUSE_CURRENCY_SYMBOL", "₺"),
        "CURRENCY_CODE": getattr(settings, "WINEHOUSE_CURRENCY", "TRY"),
        # Ortam rozetleri — kullanıcı hangi modda olduğunu her zaman görür
        "IS_DEBUG": settings.DEBUG,
        "PAYMENT_MODE": getattr(settings, "PAYMENT_MODE", "sandbox"),
        "EINVOICE_MODE": getattr(settings, "EINVOICE_MODE", "sandbox"),
        "AI_DEFAULT_PROVIDER": ai.get("DEFAULT_PROVIDER", "mock"),
        "AI_PRIVACY_MODE": ai.get("PRIVACY_MODE", True),
        "AI_LOCAL_ONLY": ai.get("LOCAL_ONLY", False),
        "DEVSTUDIO_ENABLED": devstudio.get("ENABLED", False),
        # Menü görünürlüğü için rol yetenekleri
        "nav": _navigation_flags(user),
    }


def _navigation_flags(user: Any) -> dict[str, bool]:
    """Kullanıcının hangi menü başlıklarını görebileceğini belirler."""
    if user is None or not getattr(user, "is_authenticated", False):
        return {}

    def can(codename: str) -> bool:
        return bool(user.has_perm(codename))

    return {
        "operations": can("operations.view_diningtable") or can("operations.view_order"),
        "reservations": can("operations.view_reservation"),
        "kds": can("operations.view_prepticket"),
        "catalog": can("catalog.view_menuitem"),
        "cellar": can("cellar.view_wine"),
        "inventory": can("inventory.view_stockitem") or can("inventory.view_purchaseorder"),
        "crm": can("crm.view_customer"),
        "hr": can("hr.view_employee"),
        "reporting": can("reporting.view_reportdefinition"),
        "ai": can("aiservices.view_aiconversation"),
        "backups": can("backups.view_backuprecord"),
        "training": True,
        "settings": bool(getattr(user, "is_superuser", False)) or can("core.change_appsetting"),
        "audit": can("core.view_auditlog"),
    }
