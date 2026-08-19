"""Kural paketi imza/onay akışı ve süre (deadline) motoru.

İlkeler (prompt §6):

* İnsan onayı, imza ve içerik checksum'u olmadan paket yürürlüğe girmez.
* Onaydan sonra kural içeriği değişirse imza tutmaz → paket **kullanılmaz**
  (fail-closed); motor süre uydurmak yerine ``REVIEW_REQUIRED`` döndürür.
* Süre hesapları kural paketinden gelir; koda gömülü gün/saat yoktur.

İmza, ``SECRET_KEY`` türevli HMAC **prototipidir** (asimetrik imza yol
haritasında); hukuki kesinlik iddiası taşımaz.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils import timezone

from apps.compliance.models import DeadlineUnit, LegalRule, LegalRulePack
from apps.core.audit import record
from apps.core.models import AuditAction, AuditSeverity


def _signing_key() -> bytes:
    return hashlib.sha256(f"rulepack:{settings.SECRET_KEY}".encode()).digest()


def _rule_payload(rule: LegalRule) -> dict[str, Any]:
    return {
        "rule_code": rule.rule_code,
        "title_tr": rule.title_tr,
        "title_en": rule.title_en,
        "description": rule.description,
        "source_url": rule.source.url,
        "article": rule.article,
        "severity": rule.severity,
        "deadline_value": rule.deadline_value,
        "deadline_unit": rule.deadline_unit,
        "requires_human_review": rule.requires_human_review,
        "evidence_requirements": rule.evidence_requirements,
    }


def pack_checksum(pack: LegalRulePack) -> str:
    """Paketin kural içeriği üzerinden deterministik checksum üretir."""
    rules = [_rule_payload(rule) for rule in pack.rules.order_by("rule_code")]
    payload = json.dumps(
        {
            "jurisdiction": pack.jurisdiction,
            "regulation_code": pack.regulation_code,
            "version": pack.version,
            "rules": rules,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sign(checksum: str) -> str:
    return hmac.new(_signing_key(), checksum.encode("ascii"), hashlib.sha256).hexdigest()


def verify_pack(pack: LegalRulePack) -> bool:
    """Paketin checksum ve imzasının güncel içerikle tuttuğunu doğrular."""
    if not pack.checksum or not pack.signature:
        return False
    if not hmac.compare_digest(pack_checksum(pack), pack.checksum):
        return False
    return hmac.compare_digest(_sign(pack.checksum), pack.signature)


def approve_pack(pack: LegalRulePack, *, approved_by) -> LegalRulePack:
    """Paketi insan onayıyla yürürlüğe alır.

    Checksum + imza üretir, aynı mevzuatın önceki ``ACTIVE`` sürümlerini
    emekliye ayırır ve denetim kaydı düşer.
    """
    if not pack.rules.exists():
        raise ValueError("Boş paket yürürlüğe alınamaz.")

    LegalRulePack.objects.filter(
        jurisdiction=pack.jurisdiction,
        regulation_code=pack.regulation_code,
        status=LegalRulePack.Status.ACTIVE,
    ).exclude(pk=pack.pk).update(status=LegalRulePack.Status.RETIRED)

    pack.checksum = pack_checksum(pack)
    pack.signature = _sign(pack.checksum)
    pack.status = LegalRulePack.Status.ACTIVE
    pack.approved_by = approved_by
    pack.approved_at = timezone.now()
    pack.save(
        update_fields=[
            "checksum",
            "signature",
            "status",
            "approved_by",
            "approved_at",
            "updated_at",
        ]
    )
    record(
        action=AuditAction.SETTINGS,
        obj=pack,
        message=(
            f"Kural paketi yürürlüğe alındı: {pack.regulation_code} v{pack.version} "
            f"({pack.rules.count()} kural)"
        ),
        severity=AuditSeverity.NOTICE,
        actor=approved_by,
    )
    return pack


def active_rule(jurisdiction: str, regulation_code: str, rule_code: str) -> LegalRule | None:
    """Yürürlükteki ve imzası geçerli paketten kural döndürür.

    Aktif paket yoksa veya imza tutmuyorsa ``None`` döner — çağıran taraf
    süre/sonuç uyduramaz.
    """
    packs = LegalRulePack.objects.filter(
        jurisdiction=jurisdiction,
        regulation_code=regulation_code,
        status=LegalRulePack.Status.ACTIVE,
    ).order_by("-version")
    for pack in packs:
        if not verify_pack(pack):
            continue  # içerik onaydan sonra değişmiş: paket kullanılamaz
        rule = pack.rules.filter(rule_code=rule_code).first()
        if rule is not None:
            return rule
    return None


# ---------------------------------------------------------------------------
# Süre motoru
# ---------------------------------------------------------------------------
def _add_business_days(start: datetime, days: int) -> datetime:
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Pzt-Cum
            remaining -= 1
    return current


def compute_deadline(rule: LegalRule, start: datetime) -> datetime | None:
    """Kuralın süre tanımını başlangıç anına uygular.

    İş günü hesabı yalnızca hafta sonlarını atlar; resmî tatil takvimi henüz
    yönetilmiyor (bilinen sınır — çıktı bu nedenle *en erken* son tarihtir).
    """
    if not rule.deadline_value or not rule.deadline_unit:
        return None
    if timezone.is_naive(start):
        start = timezone.make_aware(start)
    if rule.deadline_unit == DeadlineUnit.HOURS:
        return start + timedelta(hours=rule.deadline_value)
    if rule.deadline_unit == DeadlineUnit.DAYS:
        return start + timedelta(days=rule.deadline_value)
    if rule.deadline_unit == DeadlineUnit.BUSINESS_DAYS:
        return _add_business_days(start, rule.deadline_value)
    if rule.deadline_unit == DeadlineUnit.MONTHS:
        return start + relativedelta(months=rule.deadline_value)
    return None


@dataclass(frozen=True)
class DeadlineResult:
    """Süre sorgusunun sonucu."""

    status: str  # OK | REVIEW_REQUIRED
    deadline: datetime | None = None
    rule: LegalRule | None = None
    reason: str = ""


def deadline_for(
    jurisdiction: str, regulation_code: str, rule_code: str, start: datetime
) -> DeadlineResult:
    """Yürürlükteki kural paketinden süre hesaplar.

    Aktif/geçerli paket yoksa süre **uydurulmaz**: ``REVIEW_REQUIRED`` döner
    ve insan incelemesi gerekir.
    """
    rule = active_rule(jurisdiction, regulation_code, rule_code)
    if rule is None:
        return DeadlineResult(
            status="REVIEW_REQUIRED",
            reason=(
                f"{regulation_code}/{rule_code} için yürürlükte ve imzası geçerli "
                "kural paketi yok; süre insan incelemesiyle belirlenmelidir."
            ),
        )
    deadline = compute_deadline(rule, start)
    if deadline is None:
        return DeadlineResult(
            status="REVIEW_REQUIRED",
            rule=rule,
            reason=f"{rule.rule_code} bir süre tanımlamıyor.",
        )
    return DeadlineResult(status="OK", deadline=deadline, rule=rule)
