"""HSP P2 testleri: insan onay kuyruğu, denetim zinciri, hsp_verify komutu.

Doğrulanan değişmezler:

* Reddedilen istek sessizce izinliye dönüşemez.
* Makbuz ve denetim kaydı üzerindeki oynama tespit edilebilir.
* İnsan onayı sürelidir — kalıcı yetki oluşturmaz.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.core.audit import record
from apps.core.integrity import verify_audit_chain, verify_entry
from apps.core.models import AuditAction, AuditLog
from apps.hsp.gateway import evaluate_ai_request
from apps.hsp.models import (
    HSPDecision,
    HSPPolicyRule,
    HSPReviewRequest,
    RightsReceipt,
)
from apps.hsp.policy import evaluate
from apps.hsp.receipts import issue_receipt

pytestmark = [pytest.mark.ai, pytest.mark.django_db]


# ---------------------------------------------------------------------------
# İnsan onay kuyruğu
# ---------------------------------------------------------------------------
def _review_rule(admin_user, feature: str = "day_summary") -> HSPPolicyRule:
    return HSPPolicyRule.objects.create(
        feature=feature,
        decision=HSPDecision.REQUIRE_HUMAN_REVIEW,
        approved_by=admin_user,
        approved_at=timezone.now(),
    )


def test_onaysiz_inceleme_bulutu_kapatir_ve_kuyruk_acar(admin_user) -> None:
    _review_rule(admin_user)
    evaluation = evaluate_ai_request(feature="day_summary", actor_label="test")
    assert not evaluation.cloud_allowed
    assert not evaluation.blocked  # yerel çalışma sürer
    assert HSPReviewRequest.objects.filter(
        feature="day_summary", status=HSPReviewRequest.Status.PENDING
    ).exists()


def test_tekrarlanan_istek_kuyrugu_sisirmez(admin_user) -> None:
    _review_rule(admin_user)
    evaluate_ai_request(feature="day_summary")
    evaluate_ai_request(feature="day_summary")
    assert HSPReviewRequest.objects.filter(feature="day_summary").count() == 1


def test_gecerli_onay_bulutu_sinirli_acar(admin_user) -> None:
    _review_rule(admin_user)
    now = timezone.now()
    HSPReviewRequest.objects.create(
        feature="day_summary",
        status=HSPReviewRequest.Status.APPROVED,
        decided_by=admin_user,
        decided_at=now,
        expires_at=now + timedelta(days=7),
    )
    result = evaluate("day_summary")
    assert result.decision == HSPDecision.ALLOW_WITH_LIMITS
    assert result.cloud_allowed
    assert result.masking_required


def test_suresi_dolan_onay_yetki_uretmez(admin_user) -> None:
    """Onay kalıcı yetki oluşturmaz: süre dolunca bulut yeniden kapanır."""
    _review_rule(admin_user)
    now = timezone.now()
    HSPReviewRequest.objects.create(
        feature="day_summary",
        status=HSPReviewRequest.Status.APPROVED,
        decided_by=admin_user,
        decided_at=now - timedelta(days=8),
        expires_at=now - timedelta(days=1),
    )
    result = evaluate("day_summary")
    assert result.decision == HSPDecision.REQUIRE_HUMAN_REVIEW
    assert not result.cloud_allowed


def test_reddedilen_talep_bulutu_acmaz(admin_user) -> None:
    _review_rule(admin_user)
    HSPReviewRequest.objects.create(
        feature="day_summary",
        status=HSPReviewRequest.Status.REJECTED,
        decided_by=admin_user,
        decided_at=timezone.now(),
    )
    assert not evaluate("day_summary").cloud_allowed


# ---------------------------------------------------------------------------
# Denetim kaydı zinciri
# ---------------------------------------------------------------------------
def test_denetim_kayitlari_zincirlenir(db) -> None:
    first = record(action=AuditAction.SETTINGS, message="ilk kayıt")
    second = record(action=AuditAction.SETTINGS, message="ikinci kayıt")
    assert first.integrity_hash and first.signature
    assert second.prev_hash == first.integrity_hash
    ok, broken, _unchained = verify_audit_chain()
    assert ok and broken is None


def test_denetim_kaydi_oynamasi_tespit_edilir(db) -> None:
    entry = record(action=AuditAction.SETTINGS, message="orijinal mesaj")
    record(action=AuditAction.SETTINGS, message="sonraki kayıt")

    AuditLog.objects.filter(pk=entry.pk).update(message="değiştirilmiş mesaj")
    tampered = AuditLog.objects.get(pk=entry.pk)
    assert not verify_entry(tampered)
    ok, broken, _unchained = verify_audit_chain()
    assert not ok
    assert broken == entry.pk


def test_denetim_kaydi_silme_tespit_edilir(db) -> None:
    record(action=AuditAction.SETTINGS, message="a")
    middle = record(action=AuditAction.SETTINGS, message="b")
    record(action=AuditAction.SETTINGS, message="c")

    AuditLog.objects.filter(pk=middle.pk)._raw_delete(using="default")  # modeli baypas eder
    ok, _broken, _unchained = verify_audit_chain()
    assert not ok


def test_zincirsiz_eski_kayit_dogrulamayi_bozmaz(db) -> None:
    """Zincir alanları boş (eski) kayıtlar raporlanır ama zinciri bozmaz."""
    legacy = AuditLog(action=AuditAction.SETTINGS, message="eski kayıt")
    legacy.integrity_hash = ""  # zincirleme öncesi davranışı taklit eder
    AuditLog.objects.bulk_create([legacy])  # save() zincirlemesini baypas eder
    record(action=AuditAction.SETTINGS, message="yeni kayıt")

    ok, broken, unchained = verify_audit_chain()
    assert ok and broken is None
    assert unchained == 1


# ---------------------------------------------------------------------------
# hsp_verify komutu
# ---------------------------------------------------------------------------
def _make_receipt() -> RightsReceipt:
    """Politika değerlendirmesinden bir makbuz keser (zincir testleri için)."""
    issue_receipt(evaluate("menu_text"), actor_label="test", outcome="ok")
    return RightsReceipt.objects.latest("id")


def test_hsp_verify_komutu_saglam_zincirde_gecer(db, capsys) -> None:
    record(action=AuditAction.SETTINGS, message="kayıt")
    _make_receipt()
    call_command("hsp_verify")
    out = capsys.readouterr().out
    assert "Makbuz zinciri geçerli" in out
    assert "Denetim zinciri geçerli" in out


def test_hsp_verify_komutu_bozuk_zincirde_kirilir(db) -> None:
    _make_receipt()
    RightsReceipt.objects.filter(pk=RightsReceipt.objects.latest("id").pk).update(
        decision=HSPDecision.DENY
    )
    with pytest.raises(SystemExit):
        call_command("hsp_verify")
