"""Denetim kaydı bütünlük zinciri yardımcıları.

Denetim kayıtları eklenirken hash zincirine bağlanır:

    integrity_hash = SHA-256(prev_hash + kanonik_yük)
    signature      = HMAC-SHA256(SECRET_KEY türevi anahtar, integrity_hash)

Bu, kayıt değiştirme/silmeyi *tespit edilebilir* kılar (tamper-evident);
tek anahtarlı HMAC bir **prototip** mekanizmadır ve production kriptografi
iddiası taşımaz (asimetrik imza + harici zaman damgası yol haritasında).

Geriye uyumluluk: zincir alanları eklenmeden önce yazılmış (veya yazım
sırasında zincirlenemeyen) kayıtların ``integrity_hash`` değeri boştur.
Doğrulama bu kayıtları "zincirsiz" sayar ve raporlar; zincirli kayıtlar
arasında süreklilik arar. ``purge_audit_log`` en eski kayıtları
arşivleyebildiği için zincirin başı bir güven çapası olarak kabul edilir
(baş budaması tespit edilemez — bilinen sınır).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import TYPE_CHECKING, Any

from django.conf import settings

if TYPE_CHECKING:
    from apps.core.models import AuditLog

GENESIS = "0" * 64


def _signing_key() -> bytes:
    return hashlib.sha256(f"audit-chain:{settings.SECRET_KEY}".encode()).digest()


def canonical_json(data: dict[str, Any]) -> str:
    """Deterministik JSON temsili üretir."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def audit_payload(entry: AuditLog) -> str:
    """Denetim kaydının imzalanan kanonik yükünü üretir."""
    return canonical_json(
        {
            "timestamp": entry.timestamp.isoformat() if entry.timestamp else "",
            "actor": entry.actor_label,
            "action": entry.action,
            "severity": entry.severity,
            "object_type": entry.object_type,
            "object_id": entry.object_id,
            "object_repr": entry.object_repr,
            "changes": entry.changes,
            "message": entry.message,
            "ip": entry.ip_address,
            "agent": entry.user_agent,
            "success": entry.success,
        }
    )


def compute_hash(prev_hash: str, payload: str) -> str:
    return hashlib.sha256((prev_hash + payload).encode("utf-8")).hexdigest()


def sign(integrity_hash: str) -> str:
    return hmac.new(_signing_key(), integrity_hash.encode("ascii"), hashlib.sha256).hexdigest()


def verify_entry(entry: AuditLog) -> bool:
    """Tek zincirli kaydın hash ve imzasını doğrular."""
    expected = compute_hash(entry.prev_hash, audit_payload(entry))
    if not hmac.compare_digest(expected, entry.integrity_hash):
        return False
    return hmac.compare_digest(sign(entry.integrity_hash), entry.signature)


def verify_audit_chain() -> tuple[bool, int | None, int]:
    """Denetim zincirini doğrular.

    Returns:
        ``(gecerli_mi, ilk_bozuk_kayit_id, zincirsiz_kayit_sayisi)``.
        Zincirin ilk kaydı güven çapasıdır (``prev_hash`` değeri sorgulanmaz);
        sonrasında süreklilik ve her kaydın bütünlüğü aranır.
    """
    from apps.core.models import AuditLog

    unchained = AuditLog.objects.filter(integrity_hash="").count()
    prev_hash: str | None = None
    for entry in AuditLog.objects.exclude(integrity_hash="").order_by("id").iterator():
        if not verify_entry(entry):
            return False, entry.pk, unchained
        if prev_hash is not None and entry.prev_hash != prev_hash:
            return False, entry.pk, unchained
        prev_hash = entry.integrity_hash
    return True, None, unchained
