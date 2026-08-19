"""Kural paketi ve süre motoru testleri (prompt §6).

İlkeler: onaysız paket süre üretemez, onaydan sonra içerik değişirse imza
tutmaz (fail-closed), süreler koda değil pakete aittir, ay hesabı takvim
doğru yapılır.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command

from apps.compliance.models import DeadlineUnit, LegalRule, LegalRulePack
from apps.compliance.rulepacks import (
    active_rule,
    approve_pack,
    compute_deadline,
    deadline_for,
    verify_pack,
)

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

IST = ZoneInfo("Europe/Istanbul")


@pytest.fixture
def seeded(db):
    call_command("seed_rulepacks")


def _kvkk_pack() -> LegalRulePack:
    return LegalRulePack.objects.get(jurisdiction="TR", regulation_code="KVKK", version=1)


# ---------------------------------------------------------------------------
# Onay akışı
# ---------------------------------------------------------------------------
def test_seed_paketleri_draft_olusur(seeded) -> None:
    assert LegalRulePack.objects.count() == 2
    assert not LegalRulePack.objects.exclude(status=LegalRulePack.Status.DRAFT).exists()
    assert LegalRule.objects.count() == 5


def test_seed_idempotenttir(seeded) -> None:
    call_command("seed_rulepacks")
    assert LegalRulePack.objects.count() == 2
    assert LegalRule.objects.count() == 5


def test_onaysiz_paket_sure_uretemez(seeded) -> None:
    start = datetime(2026, 8, 18, 10, 0, tzinfo=IST)
    result = deadline_for("TR", "KVKK", "KVKK-DSR-RESPONSE-30D", start)
    assert result.status == "REVIEW_REQUIRED"
    assert result.deadline is None
    assert "insan incelemesi" in result.reason


def test_onayli_paket_kvkk_30_gun_hesaplar(seeded, admin_user) -> None:
    approve_pack(_kvkk_pack(), approved_by=admin_user)
    start = datetime(2026, 8, 18, 10, 0, tzinfo=IST)
    result = deadline_for("TR", "KVKK", "KVKK-DSR-RESPONSE-30D", start)
    assert result.status == "OK"
    assert result.deadline == start + timedelta(days=30)


def test_kvkk_ihlal_72_saat(seeded, admin_user) -> None:
    approve_pack(_kvkk_pack(), approved_by=admin_user)
    start = datetime(2026, 8, 18, 23, 30, tzinfo=IST)
    result = deadline_for("TR", "KVKK", "KVKK-BREACH-NOTIFY-72H", start)
    assert result.status == "OK"
    assert result.deadline == start + timedelta(hours=72)


def test_gdpr_bir_ay_takvim_dogru(seeded, admin_user) -> None:
    """31 Ocak + 1 ay = 28 Şubat (gün taşması yok)."""
    pack = LegalRulePack.objects.get(jurisdiction="EU", regulation_code="GDPR")
    approve_pack(pack, approved_by=admin_user)
    start = datetime(2026, 1, 31, 9, 0, tzinfo=IST)
    result = deadline_for("EU", "GDPR", "GDPR-DSR-RESPONSE-1M", start)
    assert result.status == "OK"
    assert result.deadline == datetime(2026, 2, 28, 9, 0, tzinfo=IST)


def test_sure_tanimlamayan_kural_review_ister(seeded, admin_user) -> None:
    approve_pack(_kvkk_pack(), approved_by=admin_user)
    start = datetime(2026, 8, 18, 10, 0, tzinfo=IST)
    result = deadline_for("TR", "KVKK", "KVKK-CONSENT-SEPARATE", start)
    assert result.status == "REVIEW_REQUIRED"
    assert result.rule is not None


def test_is_gunu_hesabi_hafta_sonunu_atlar(seeded, admin_user) -> None:
    pack = approve_pack(_kvkk_pack(), approved_by=admin_user)
    rule = pack.rules.get(rule_code="KVKK-DSR-RESPONSE-30D")
    rule.deadline_value = 3
    rule.deadline_unit = DeadlineUnit.BUSINESS_DAYS
    # Cuma + 3 iş günü = Çarşamba
    friday = datetime(2026, 8, 14, 10, 0, tzinfo=IST)
    assert compute_deadline(rule, friday) == datetime(2026, 8, 19, 10, 0, tzinfo=IST)


# ---------------------------------------------------------------------------
# Bütünlük
# ---------------------------------------------------------------------------
def test_onaydan_sonra_degisen_icerik_imzayi_bozar(seeded, admin_user) -> None:
    pack = approve_pack(_kvkk_pack(), approved_by=admin_user)
    assert verify_pack(pack)

    rule = pack.rules.get(rule_code="KVKK-DSR-RESPONSE-30D")
    rule.deadline_value = 90  # sessiz gevşetme denemesi
    rule.save(update_fields=["deadline_value"])

    pack.refresh_from_db()
    assert not verify_pack(pack)
    result = deadline_for(
        "TR", "KVKK", "KVKK-DSR-RESPONSE-30D", datetime(2026, 8, 18, 10, 0, tzinfo=IST)
    )
    assert result.status == "REVIEW_REQUIRED"  # bozuk paket kullanılmaz


def test_yeni_surum_onayi_eskisini_emekli_eder(seeded, admin_user) -> None:
    old = approve_pack(_kvkk_pack(), approved_by=admin_user)
    new = LegalRulePack.objects.create(jurisdiction="TR", regulation_code="KVKK", version=2)
    rule = old.rules.get(rule_code="KVKK-DSR-RESPONSE-30D")
    LegalRule.objects.create(
        pack=new,
        rule_code=rule.rule_code,
        title_tr=rule.title_tr,
        title_en=rule.title_en,
        source=rule.source,
        severity=rule.severity,
        deadline_value=rule.deadline_value,
        deadline_unit=rule.deadline_unit,
    )
    approve_pack(new, approved_by=admin_user)

    old.refresh_from_db()
    assert old.status == LegalRulePack.Status.RETIRED
    found = active_rule("TR", "KVKK", "KVKK-DSR-RESPONSE-30D")
    assert found is not None and found.pack_id == new.pk


def test_bos_paket_yururluge_alinamaz(db, admin_user) -> None:
    pack = LegalRulePack.objects.create(jurisdiction="TR", regulation_code="BOS", version=1)
    with pytest.raises(ValueError):
        approve_pack(pack, approved_by=admin_user)
