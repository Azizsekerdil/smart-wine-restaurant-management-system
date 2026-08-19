"""Rights Receipt üretimi ve zincir doğrulaması.

Her HSP değerlendirmesi için hash zincirine bağlı bir makbuz düzenlenir:

    integrity_hash = SHA-256(prev_hash + kanonik_yük)
    signature      = HMAC-SHA256(anahtar, integrity_hash)

Anahtar Django ``SECRET_KEY``'inden türetilir. Bu **prototip** bir bütünlük
mekanizmasıdır (tek anahtar, sunucu tarafı); asimetrik imza ve harici zaman
damgası P2 kapsamındadır. Production kriptografi iddiası taşımaz.

Makbuzlar ham istem, yanıt veya kişisel veri içermez; yalnızca karar ve
sınıf üstverisi tutar.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from django.conf import settings
from django.db import transaction

from apps.hsp.models import RightsReceipt
from apps.hsp.policy import HSPEvaluation

logger = logging.getLogger("winehouse.hsp")

_GENESIS = "0" * 64


def _signing_key() -> bytes:
    return hashlib.sha256(f"hsp-receipt:{settings.SECRET_KEY}".encode()).digest()


def _canonical_payload(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compute_hash(prev_hash: str, payload: str) -> str:
    return hashlib.sha256((prev_hash + payload).encode("utf-8")).hexdigest()


def _sign(integrity_hash: str) -> str:
    return hmac.new(_signing_key(), integrity_hash.encode("ascii"), hashlib.sha256).hexdigest()


def receipt_payload(receipt: RightsReceipt) -> str:
    """Makbuzun imzalanan kanonik yükünü üretir."""
    return _canonical_payload(
        {
            "actor": receipt.actor_label,
            "feature": receipt.feature,
            "action": receipt.action,
            "data_class": receipt.data_class,
            "personal_class": receipt.personal_class,
            "decision": receipt.decision,
            "rules": receipt.applied_rule_ids,
            "limits": receipt.enforced_limits,
            "provider": receipt.provider,
            "model": receipt.model,
            "outcome": receipt.outcome,
        }
    )


def issue_receipt(
    evaluation: HSPEvaluation,
    *,
    actor_label: str = "",
    provider: str = "",
    model: str = "",
    outcome: str = "",
    masking_applied: bool | None = None,
    action: str = "TRANSFER",
) -> RightsReceipt | None:
    """Değerlendirme için zincire bağlı makbuz düzenler.

    Makbuz yazımı iş akışını asla bozmaz: hata durumunda ``None`` döner ve
    günlüğe düşülür (denetim kaydı davranışıyla tutarlı).
    """
    limits = dict(evaluation.enforced_limits)
    if masking_applied is not None:
        limits["masking_applied"] = bool(masking_applied)

    try:
        with transaction.atomic():
            last = RightsReceipt.objects.order_by("-id").first()
            prev_hash = last.integrity_hash if last is not None else _GENESIS
            receipt = RightsReceipt(
                actor_label=actor_label[:150],
                feature=evaluation.feature,
                action=action[:30],
                data_class=evaluation.data_class,
                personal_class=evaluation.personal_class,
                decision=evaluation.decision,
                applied_rule_ids=evaluation.applied_rule_ids,
                enforced_limits=limits,
                provider=provider[:40],
                model=model[:120],
                outcome=outcome[:20],
                prev_hash=prev_hash,
            )
            receipt.integrity_hash = _compute_hash(prev_hash, receipt_payload(receipt))
            receipt.signature = _sign(receipt.integrity_hash)
            receipt.save()
            return receipt
    except Exception:  # pragma: no cover - makbuz iş akışını bozmamalı
        logger.exception("Rights receipt yazılamadı: feature=%s", evaluation.feature)
        return None


def verify_receipt(receipt: RightsReceipt) -> bool:
    """Tek makbuzun hash ve imzasını doğrular."""
    expected_hash = _compute_hash(receipt.prev_hash, receipt_payload(receipt))
    if not hmac.compare_digest(expected_hash, receipt.integrity_hash):
        return False
    return hmac.compare_digest(_sign(receipt.integrity_hash), receipt.signature)


def verify_chain() -> tuple[bool, int | None]:
    """Tüm zinciri doğrular.

    Returns:
        ``(gecerli_mi, ilk_bozuk_makbuz_id)``. Zincir boşsa ``(True, None)``.
    """
    prev_hash = _GENESIS
    for receipt in RightsReceipt.objects.order_by("id").iterator():
        if receipt.prev_hash != prev_hash or not verify_receipt(receipt):
            return False, receipt.pk
        prev_hash = receipt.integrity_hash
    return True, None
