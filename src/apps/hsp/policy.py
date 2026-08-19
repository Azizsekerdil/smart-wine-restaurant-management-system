"""HSP pre-action politika motoru.

Ana soru: *bu makine (AI katmanı) bu insan/işletme verisiyle ne yapmaya
yetkili?* Bu modül AI gateway'in bulut aktarım (TRANSFER) eylemini eylemden
**önce** değerlendirir.

Tasarım kuralları (prompt §12, §17.1):

* ``UNKNOWN`` sınıfı yüksek riskli yolda (bulut aktarımı) **fail-closed**'dur:
  sınıfı bilinmeyen işlev buluta çıkamaz, yerel çalışmaya devam eder.
* Veritabanı kuralları varsayılanı yalnızca **sıkılaştırabilir**; gevşetme bu
  haritanın gözden geçirilen bir kod değişikliğiyle güncellenmesini gerektirir
  (sürümlü + onaylı değişiklik ilkesi).
* Onaysız veya pasif kural karar üretemez; DENY sessizce ALLOW olamaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.hsp.models import (
    DECISION_STRICTNESS,
    DataClass,
    HSPDecision,
    HSPPolicyRule,
    HSPReviewRequest,
    PersonalDataClass,
)

# ---------------------------------------------------------------------------
# İşlev → sınıflandırma haritası
# ---------------------------------------------------------------------------
# Haritada olmayan her işlev UNKNOWN'dır ve bulut yolunda fail-closed davranır.
# Gevşetme (ör. RESTRICTED → CONFIDENTIAL) yalnızca bu dosyada, gözden
# geçirilen bir değişiklikle yapılabilir.
FEATURE_CLASSIFICATION: dict[str, tuple[str, str]] = {
    # feature: (data_class, personal_class)
    "menu_text": (DataClass.PUBLIC, PersonalDataClass.NON_PERSONAL),
    "sommelier": (DataClass.INTERNAL, PersonalDataClass.UNKNOWN),
    "pairing": (DataClass.INTERNAL, PersonalDataClass.UNKNOWN),
    "vision": (DataClass.INTERNAL, PersonalDataClass.UNKNOWN),
    "translation": (DataClass.INTERNAL, PersonalDataClass.UNKNOWN),
    "training": (DataClass.INTERNAL, PersonalDataClass.NON_PERSONAL),
    "report_query": (DataClass.CONFIDENTIAL, PersonalDataClass.NON_PERSONAL),
    "forecast": (DataClass.CONFIDENTIAL, PersonalDataClass.NON_PERSONAL),
    "inventory": (DataClass.CONFIDENTIAL, PersonalDataClass.NON_PERSONAL),
    "waste": (DataClass.CONFIDENTIAL, PersonalDataClass.NON_PERSONAL),
    "anomaly": (DataClass.CONFIDENTIAL, PersonalDataClass.NON_PERSONAL),
    "decision": (DataClass.CONFIDENTIAL, PersonalDataClass.NON_PERSONAL),
    "day_summary": (DataClass.CONFIDENTIAL, PersonalDataClass.NON_PERSONAL),
    "devstudio": (DataClass.CONFIDENTIAL, PersonalDataClass.NON_PERSONAL),
    "caio": (DataClass.CONFIDENTIAL, PersonalDataClass.NON_PERSONAL),
    # Müşteri tercih analizi kişisel veri işler: bulut aktarımı kapalıdır.
    "customer": (DataClass.RESTRICTED, PersonalDataClass.PERSONAL),
}

#: Veri sınıfı → bulut aktarımı için varsayılan karar.
DEFAULT_DECISIONS: dict[str, str] = {
    DataClass.PUBLIC: HSPDecision.ALLOW,
    DataClass.INTERNAL: HSPDecision.ALLOW_WITH_LIMITS,
    DataClass.CONFIDENTIAL: HSPDecision.ALLOW_WITH_LIMITS,
    DataClass.RESTRICTED: HSPDecision.LOCAL_ONLY,
    DataClass.UNKNOWN: HSPDecision.LOCAL_ONLY,  # fail-closed
}


@dataclass(frozen=True)
class HSPEvaluation:
    """Bir AI isteği için HSP değerlendirme sonucu."""

    feature: str
    data_class: str
    personal_class: str
    decision: str
    applied_rule_ids: list[int] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def cloud_allowed(self) -> bool:
        """Bulut sağlayıcıya aktarım izinli mi?"""
        return self.decision in (HSPDecision.ALLOW, HSPDecision.ALLOW_WITH_LIMITS)

    @property
    def blocked(self) -> bool:
        """İstek tamamen engelli mi (yerel dahil)?"""
        return self.decision == HSPDecision.DENY

    @property
    def masking_required(self) -> bool:
        """Bulut yolunda maskeleme kanıt olarak zorunlu mu?"""
        return self.decision == HSPDecision.ALLOW_WITH_LIMITS

    @property
    def enforced_limits(self) -> dict[str, bool]:
        return {
            "cloud_allowed": self.cloud_allowed,
            "masking_required": self.masking_required,
            "local_only": not self.cloud_allowed and not self.blocked,
        }


def classify_feature(feature: str) -> tuple[str, str]:
    """İşlevin veri sınıfını döndürür; tanımsız işlev ``UNKNOWN``'dır."""
    return FEATURE_CLASSIFICATION.get(feature, (DataClass.UNKNOWN, PersonalDataClass.UNKNOWN))


def _strictest(*decisions: str) -> str:
    """Verilen kararlardan en katısını seçer."""
    return max(decisions, key=lambda d: DECISION_STRICTNESS.get(d, 0))


def evaluate(feature: str) -> HSPEvaluation:
    """Bulut aktarım eylemi için HSP kararını üretir.

    Etkin karar = varsayılan karar ile **etkili** (aktif + onaylı) kuralların
    en katısı. Kurallar hiçbir durumda varsayılandan gevşek sonuç veremez.
    """
    data_class, personal_class = classify_feature(feature)
    decision = DEFAULT_DECISIONS[data_class]
    reasons = [f"varsayılan[{data_class}]={decision}"]
    applied: list[int] = []

    rules = HSPPolicyRule.objects.filter(is_active=True, feature__in=[feature, "*"])
    for rule in rules:
        if not rule.is_effective:
            continue  # onaysız kural karar üretemez
        stricter = _strictest(decision, rule.decision)
        if stricter != decision:
            decision = stricter
            reasons.append(f"kural#{rule.pk}(v{rule.version})={rule.decision}")
        applied.append(rule.pk)

    if data_class == DataClass.UNKNOWN:
        reasons.append("sınıf bilinmiyor: bulut yolu fail-closed")

    # REQUIRE_HUMAN_REVIEW: geçerli (onaylı + süresi dolmamış) inceleme varsa
    # bulut yolu SINIRLI izinle açılır; yoksa istek fail-safe yerel kalır.
    if decision == HSPDecision.REQUIRE_HUMAN_REVIEW:
        approval = (
            HSPReviewRequest.objects.filter(
                feature=feature, status=HSPReviewRequest.Status.APPROVED
            )
            .order_by("-decided_at")
            .first()
        )
        if approval is not None and approval.grants_cloud:
            decision = HSPDecision.ALLOW_WITH_LIMITS
            reasons.append(
                f"insan onayı#{approval.pk} (geçerlilik {approval.expires_at:%Y-%m-%d %H:%M})"
            )
        else:
            reasons.append("insan incelemesi bekleniyor: bulut yolu kapalı")

    return HSPEvaluation(
        feature=feature,
        data_class=data_class,
        personal_class=personal_class,
        decision=decision,
        applied_rule_ids=applied,
        reasons=reasons,
    )
