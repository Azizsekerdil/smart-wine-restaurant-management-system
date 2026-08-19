"""Kişisel veri keşif tarayıcısı testleri (prompt §9).

Beklentiler: bilinen PII alanları doğru kategoriyle bulunur, şifreleme durumu
kanıt olarak işaretlenir, özel nitelikli adaylar ayrışır, baseline diff'i yeni
alanı yakalar ve gate envantere işlenmemiş PII'de kırılır.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.compliance.privacy import build_ropa_markdown, diff_against_baseline, scan_models

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def scan():
    return scan_models()


def _find(scan, key: str):
    return next((f for f in scan.findings if f.key == key), None)


def test_bilinen_pii_alanlari_bulunur(scan) -> None:
    phone = _find(scan, "crm.Customer.phone")
    assert phone is not None
    assert phone.category == "iletişim"
    assert phone.encrypted  # EncryptedCharField kanıt olarak işaretlenir
    assert phone.subject == "müşteri"

    national_id = _find(scan, "hr.Employee.national_id")
    assert national_id is not None
    assert national_id.category == "kimlik (resmî numara)"
    assert national_id.encrypted

    iban = _find(scan, "hr.Employee.iban")
    assert iban is not None
    assert iban.category == "finansal"


def test_ozel_nitelikli_adaylar_ayrisir(scan) -> None:
    allergy = _find(scan, "crm.Customer.allergy_notes")
    assert allergy is not None
    assert allergy.special_category
    specials = [f for f in scan.findings if f.special_category]
    assert len(specials) >= 2  # Customer + Reservation alerji alanları


def test_kimlik_dogrulama_alanlari_bulunur(scan) -> None:
    pin = _find(scan, "accounts.User.pin_hash")
    assert pin is not None
    assert pin.category == "kimlik doğrulama"


def test_denetim_ip_adresi_cevrimici_tanimlayici(scan) -> None:
    ip = _find(scan, "core.AuditLog.ip_address")
    assert ip is not None
    assert ip.category == "çevrimiçi tanımlayıcı"


def test_urun_uygulamalari_taranmaz(scan) -> None:
    """catalog/cellar gibi kişi öznesi olmayan uygulamalar kapsam dışıdır."""
    assert not any(f.app in {"catalog", "cellar", "inventory"} for f in scan.findings)


def test_baseline_diff_yeni_alani_yakalar(scan) -> None:
    baseline = {f.key for f in scan.findings}
    removed_key = scan.findings[0].key
    baseline.discard(removed_key)
    baseline.add("crm.Customer.artik_yok")

    new, removed = diff_against_baseline(scan, baseline)
    assert [f.key for f in new] == [removed_key]
    assert removed == {"crm.Customer.artik_yok"}


def test_ropa_ciktisi_yer_tutucular_icerir(scan) -> None:
    markdown = build_ropa_markdown(scan, {"audit_log": 730})
    assert "REVIEW_REQUIRED" in markdown
    assert "resmî kayıt" in markdown  # resmî başvuru iddiası yok
    assert "`audit_log`: 730 gün" in markdown
    assert "Özel nitelikli veri adayları" in markdown


def test_privacy_gate_guncel_baseline_ile_gecer(capsys) -> None:
    call_command("privacy_scan", "--gate")
    assert "Privacy gate geçti" in capsys.readouterr().out


def test_privacy_gate_eksik_baseline_kaydinda_kirilir(tmp_path: Path, scan) -> None:
    baseline = {
        "fields": {f.key: f.category for f in scan.findings if f.key != "crm.Customer.phone"}
    }
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline), encoding="utf-8")
    with pytest.raises(SystemExit):
        call_command("privacy_scan", "--gate", "--baseline", str(path))


def test_privacy_gate_baseline_yoksa_kirilir(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        call_command("privacy_scan", "--gate", "--baseline", str(tmp_path / "yok.json"))
