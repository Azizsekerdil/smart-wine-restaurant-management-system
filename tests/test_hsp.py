"""Human Sovereignty Protocol testleri.

Prompt §30 zorunlu invariant'larının bu dilime düşen kısmı:

* ``UNKNOWN`` sınıfı bulut yolunda fail-open olamaz.
* DENY sessizce ALLOW olamaz; onaysız/pasif kural karar üretemez.
* Kurallar varsayılanı gevşetemez (yalnızca sıkılaştırma).
* Makbuz zincirinde oynama tespit edilir.
* ``RESTRICTED`` veri hiçbir sağlayıcı hatasında buluta düşmez.
* Makbuz ham istem metni içermez.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from apps.hsp.gateway import HSPDeniedError, evaluate_ai_request
from apps.hsp.models import DataClass, HSPDecision, HSPPolicyRule, RightsReceipt
from apps.hsp.policy import evaluate
from apps.hsp.receipts import issue_receipt, verify_chain, verify_receipt

pytestmark = [pytest.mark.ai, pytest.mark.django_db]


# ---------------------------------------------------------------------------
# Politika motoru
# ---------------------------------------------------------------------------
def test_bilinmeyen_islev_fail_closed() -> None:
    """Sınıfı bilinmeyen işlev buluta çıkamaz (UNKNOWN ≠ ALLOW)."""
    result = evaluate("boyle_bir_islev_yok")
    assert result.data_class == DataClass.UNKNOWN
    assert result.decision == HSPDecision.LOCAL_ONLY
    assert not result.cloud_allowed
    assert not result.blocked  # yerel çalışma sürer


def test_restricted_sinif_yalnizca_yerel() -> None:
    """Müşteri tercih analizi (kişisel veri) bulut yoluna kapalıdır."""
    result = evaluate("customer")
    assert result.data_class == DataClass.RESTRICTED
    assert not result.cloud_allowed


def test_confidential_sinif_sinirli_izin() -> None:
    result = evaluate("day_summary")
    assert result.data_class == DataClass.CONFIDENTIAL
    assert result.decision == HSPDecision.ALLOW_WITH_LIMITS
    assert result.masking_required


def test_public_sinif_izinli() -> None:
    assert evaluate("menu_text").decision == HSPDecision.ALLOW


def test_onaysiz_kural_karar_uretemez(admin_user) -> None:
    """Aktif ama onaysız kural değerlendirmeye katılamaz."""
    HSPPolicyRule.objects.create(feature="menu_text", decision=HSPDecision.DENY)
    result = evaluate("menu_text")
    assert result.decision == HSPDecision.ALLOW
    assert result.applied_rule_ids == []


def test_pasif_kural_karar_uretemez(admin_user) -> None:
    """Devre dışı bırakılan (revoked) kural yetki/yasak üretemez."""
    HSPPolicyRule.objects.create(
        feature="menu_text",
        decision=HSPDecision.DENY,
        is_active=False,
        approved_by=admin_user,
        approved_at=timezone.now(),
    )
    assert evaluate("menu_text").decision == HSPDecision.ALLOW


def test_onayli_kural_sikilastirir(admin_user) -> None:
    HSPPolicyRule.objects.create(
        feature="day_summary",
        decision=HSPDecision.LOCAL_ONLY,
        approved_by=admin_user,
        approved_at=timezone.now(),
    )
    result = evaluate("day_summary")
    assert result.decision == HSPDecision.LOCAL_ONLY
    assert not result.cloud_allowed
    assert len(result.applied_rule_ids) == 1


def test_kural_varsayilani_gevsetemez(admin_user) -> None:
    """RESTRICTED işlev, ALLOW kuralı onaylı olsa bile buluta açılamaz."""
    HSPPolicyRule.objects.create(
        feature="customer",
        decision=HSPDecision.ALLOW,
        approved_by=admin_user,
        approved_at=timezone.now(),
    )
    result = evaluate("customer")
    assert result.decision == HSPDecision.LOCAL_ONLY  # en katı karar kazanır
    assert not result.cloud_allowed


def test_deny_sessizce_allow_olamaz(admin_user) -> None:
    """DENY kuralı dururken sonradan eklenen gevşek kural onu ezemez."""
    HSPPolicyRule.objects.create(
        feature="waste",
        decision=HSPDecision.DENY,
        approved_by=admin_user,
        approved_at=timezone.now(),
    )
    HSPPolicyRule.objects.create(
        feature="waste",
        decision=HSPDecision.ALLOW,
        version=2,
        approved_by=admin_user,
        approved_at=timezone.now(),
    )
    assert evaluate("waste").decision == HSPDecision.DENY


def test_yildiz_kurali_tum_islevlere_uygulanir(admin_user) -> None:
    HSPPolicyRule.objects.create(
        feature="*",
        decision=HSPDecision.LOCAL_ONLY,
        approved_by=admin_user,
        approved_at=timezone.now(),
    )
    assert not evaluate("menu_text").cloud_allowed
    assert not evaluate("day_summary").cloud_allowed


# ---------------------------------------------------------------------------
# Gateway köprüsü
# ---------------------------------------------------------------------------
def test_deny_karari_istegi_engeller_ve_makbuz_keser(admin_user) -> None:
    HSPPolicyRule.objects.create(
        feature="anomaly",
        decision=HSPDecision.DENY,
        approved_by=admin_user,
        approved_at=timezone.now(),
    )
    with pytest.raises(HSPDeniedError):
        evaluate_ai_request(feature="anomaly", actor_label="test")

    receipt = RightsReceipt.objects.get()
    assert receipt.decision == HSPDecision.DENY
    assert receipt.outcome == "blocked"


# ---------------------------------------------------------------------------
# ask() entegrasyonu — RESTRICTED veri buluta düşmez
# ---------------------------------------------------------------------------
def test_restricted_islev_bulut_zincirine_giremez(admin_user, monkeypatch) -> None:
    """`customer` işlevi, bulut sağlayıcı yapılandırılmış olsa bile yalnızca
    yerel sağlayıcılarla çalışır ve makbuz düzenlenir."""
    from apps.aiservices import services

    used: list[str] = []
    real_get = services.get_provider

    def spy_get_provider(code: str):
        used.append(code)
        return real_get("mock")

    monkeypatch.setattr(services, "get_provider", spy_get_provider)
    monkeypatch.setattr(
        services, "build_fallback_chain", lambda preferred="": ["anthropic", "nvidia", "mock"]
    )

    result = services.ask(user=admin_user, feature="customer", prompt="VIP müşteri analizi")

    assert used, "hiç sağlayıcı denenmedi"
    assert all(code == "mock" for code in used), f"bulut sağlayıcı denendi: {used}"
    assert result.is_mock

    receipt = RightsReceipt.objects.latest("id")
    assert receipt.feature == "customer"
    assert receipt.data_class == DataClass.RESTRICTED
    assert receipt.enforced_limits["local_only"] is True


def test_izinli_islev_akisi_bozulmaz(admin_user, monkeypatch) -> None:
    """HSP kancası, izinli işlevde mevcut davranışı değiştirmez."""
    from apps.aiservices import services

    monkeypatch.setattr(services, "build_fallback_chain", lambda preferred="": ["mock"])
    result = services.ask(user=admin_user, feature="pairing", prompt="Kuzu tandır")
    assert result.text
    assert RightsReceipt.objects.filter(feature="pairing", outcome="success").exists()


# ---------------------------------------------------------------------------
# Makbuz zinciri
# ---------------------------------------------------------------------------
def _issue(feature: str = "menu_text") -> RightsReceipt:
    receipt = issue_receipt(evaluate(feature), actor_label="test", outcome="success")
    assert receipt is not None
    return receipt


def test_makbuz_zinciri_dogrulanir() -> None:
    first = _issue()
    second = _issue("day_summary")
    assert first.prev_hash == "0" * 64
    assert second.prev_hash == first.integrity_hash
    ok, broken = verify_chain()
    assert ok and broken is None


def test_makbuz_oynamasi_tespit_edilir() -> None:
    receipt = _issue()
    _issue("day_summary")

    RightsReceipt.objects.filter(pk=receipt.pk).update(decision=HSPDecision.ALLOW_WITH_LIMITS)
    tampered = RightsReceipt.objects.get(pk=receipt.pk)
    assert not verify_receipt(tampered)
    ok, broken = verify_chain()
    assert not ok
    assert broken == receipt.pk


def test_makbuz_silme_tespit_edilir() -> None:
    first = _issue()
    _issue("day_summary")
    third = _issue("pairing")

    RightsReceipt.objects.filter(pk__in=[first.pk, third.pk]).exclude(pk=first.pk).first()
    RightsReceipt.objects.get(pk=third.pk)  # zincir: 1 → 2 → 3
    RightsReceipt.objects.filter(pk=first.pk + 1).delete()  # ortadaki makbuz silinir

    ok, _broken = verify_chain()
    assert not ok


def test_makbuz_ham_istem_icermez(admin_user, monkeypatch) -> None:
    """Makbuzda istem metni veya kişisel veri alanı bulunmaz."""
    from apps.aiservices import services

    monkeypatch.setattr(services, "build_fallback_chain", lambda preferred="": ["mock"])
    secret_prompt = "Ahmet Yılmaz adlı müşteri için analiz"
    services.ask(user=admin_user, feature="customer", prompt=secret_prompt)

    receipt = RightsReceipt.objects.latest("id")
    dumped = str(receipt.__dict__)
    assert "Ahmet" not in dumped
    assert secret_prompt not in dumped
