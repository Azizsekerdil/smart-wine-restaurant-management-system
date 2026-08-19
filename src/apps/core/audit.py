"""Denetim kaydı yardımcıları.

Kullanım::

    from apps.core.audit import record

    record(
        action=AuditAction.PAYMENT,
        obj=order,
        message="Hesap kart ile kapatıldı",
        changes={"tutar": "1250.00"},
        request=request,
    )

İstek nesnesi verilmezse ``AuditContextMiddleware`` tarafından iş parçacığına
yazılan bağlam (kullanıcı, IP, istemci) otomatik kullanılır.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from django.db import models

from apps.core.models import AuditAction, AuditLog, AuditSeverity
from apps.core.security import mask_secrets

logger = logging.getLogger("winehouse.security")

_context = threading.local()


def set_audit_context(*, user: Any = None, ip: str | None = None, agent: str = "") -> None:
    """Geçerli iş parçacığı için denetim bağlamını ayarlar."""
    _context.user = user
    _context.ip = ip
    _context.agent = agent[:255] if agent else ""


def clear_audit_context() -> None:
    """İstek bitiminde bağlamı temizler (iş parçacığı yeniden kullanılabilir)."""
    for attribute in ("user", "ip", "agent"):
        if hasattr(_context, attribute):
            delattr(_context, attribute)


def get_audit_context() -> dict[str, Any]:
    """Geçerli denetim bağlamını döndürür."""
    return {
        "user": getattr(_context, "user", None),
        "ip": getattr(_context, "ip", None),
        "agent": getattr(_context, "agent", ""),
    }


def _serialize(value: Any) -> Any:
    """JSON alanına yazılabilir hale getirir."""
    if isinstance(value, models.Model):
        return f"{value._meta.label}:{value.pk}"
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return mask_secrets(value) if isinstance(value, str) else value
    return mask_secrets(str(value))


def record(
    *,
    action: str,
    obj: models.Model | None = None,
    message: str = "",
    changes: dict[str, Any] | None = None,
    severity: str = AuditSeverity.INFO,
    success: bool = True,
    request: Any = None,
    actor: Any = None,
) -> AuditLog:
    """Denetim kaydı oluşturur.

    Hiçbir koşulda çağıran işlemi bozmaz: kayıt yazılamazsa yalnızca
    günlüğe hata düşer ve boş bir nesne döner.
    """
    context = get_audit_context()

    resolved_actor = actor
    if resolved_actor is None and request is not None:
        resolved_actor = getattr(request, "user", None)
    if resolved_actor is None:
        resolved_actor = context["user"]
    if resolved_actor is not None and not getattr(resolved_actor, "is_authenticated", False):
        resolved_actor = None

    ip = context["ip"]
    agent = context["agent"]
    if request is not None:
        ip = ip or _client_ip(request)
        agent = agent or request.META.get("HTTP_USER_AGENT", "")[:255]

    entry = AuditLog(
        actor=resolved_actor,
        actor_label=(getattr(resolved_actor, "username", "") or "sistem")[:150],
        action=action,
        severity=severity,
        object_type=obj._meta.label if obj is not None else "",
        object_id=str(obj.pk) if obj is not None and obj.pk else "",
        object_repr=mask_secrets(str(obj))[:255] if obj is not None else "",
        changes=_serialize(changes or {}),
        message=mask_secrets(message),
        ip_address=ip,
        user_agent=(agent or "")[:255],
        success=success,
    )
    try:
        entry.save()
    except Exception:  # pragma: no cover - denetim kaydı iş akışını bozmamalı
        logger.exception("Denetim kaydı yazılamadı: action=%s", action)
    return entry


def record_permission_denied(request: Any, message: str) -> AuditLog:
    """Yetkisiz erişim denemesini kritik önemde kaydeder."""
    return record(
        action=AuditAction.PERMISSION_DENIED,
        message=message,
        severity=AuditSeverity.WARNING,
        success=False,
        request=request,
    )


def diff_fields(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """İki sözlük arasındaki farkı ``{alan: [eski, yeni]}`` biçiminde döndürür."""
    changed: dict[str, Any] = {}
    for key in set(before) | set(after):
        old, new = before.get(key), after.get(key)
        if old != new:
            changed[key] = [_serialize(old), _serialize(new)]
    return changed


def _client_ip(request: Any) -> str | None:
    """İstemci IP adresini güvenli biçimde çıkarır."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        if candidate:
            return candidate
    return request.META.get("REMOTE_ADDR") or None
