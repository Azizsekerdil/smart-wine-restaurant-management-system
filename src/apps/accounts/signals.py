"""Kimlik doğrulama olaylarını denetim kaydına yazan sinyaller."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from apps.core.audit import _client_ip, record
from apps.core.models import AuditAction, AuditSeverity


@receiver(user_logged_in)
def on_login(sender: Any, request: Any, user: Any, **kwargs: Any) -> None:
    """Başarılı girişi kaydeder ve kilit sayaçlarını sıfırlar."""
    from apps.accounts.models import LoginAttempt

    LoginAttempt.objects.create(
        username=user.get_username(),
        successful=True,
        ip_address=_client_ip(request) if request else None,
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""),
        method=getattr(request, "_winehouse_login_method", "password") if request else "password",
    )
    if hasattr(user, "register_successful_login"):
        user.register_successful_login()

    record(
        action=AuditAction.LOGIN,
        message=f"{user.get_username()} sisteme giriş yaptı.",
        request=request,
        actor=user,
    )


@receiver(user_logged_out)
def on_logout(sender: Any, request: Any, user: Any, **kwargs: Any) -> None:
    """Çıkışı kaydeder."""
    if user is None:
        return
    record(
        action=AuditAction.LOGOUT,
        message=f"{user.get_username()} çıkış yaptı.",
        request=request,
        actor=user,
    )


@receiver(user_login_failed)
def on_login_failed(
    sender: Any, credentials: dict[str, Any], request: Any = None, **kwargs: Any
) -> None:
    """Başarısız girişi kaydeder ve kullanıcı sayacını artırır."""
    from apps.accounts.models import LoginAttempt, User

    username = (credentials or {}).get("username", "") or ""

    LoginAttempt.objects.create(
        username=username[:150],
        successful=False,
        ip_address=_client_ip(request) if request else None,
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""),
    )

    user = User.objects.filter(username=username).first()
    if user is not None:
        user.register_failed_login()

    record(
        action=AuditAction.LOGIN_FAILED,
        message=f"Başarısız giriş denemesi: {username or '(boş kullanıcı adı)'}",
        severity=AuditSeverity.WARNING,
        success=False,
        request=request,
    )
