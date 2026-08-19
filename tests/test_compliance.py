"""Uyum motoru testleri: lisans sınıflandırma, tarayıcı, SPDX, gate.

Prompt §8 ilkeleri: lisans yokluğu serbestlik değildir (UNKNOWN), SPDX OR/AND
ayrımı doğru işlenir, sonuçlar hukuki kesinlik iddiası taşımaz.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.compliance.licenses import (
    GREEN,
    ORANGE,
    RED,
    UNKNOWN,
    YELLOW,
    classify_license,
)
from apps.compliance.scanner import ComponentRecord, parse_requirements, scan_runtime_closure
from apps.compliance.spdx import build_spdx_document

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Sınıflandırma
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT", GREEN),
        ("BSD-3-Clause", GREEN),
        ("Apache-2.0", GREEN),
        ("ISC License", GREEN),
        ("Python Software Foundation License", GREEN),
        ("MIT-CMU", GREEN),
        ("Mozilla Public License 2.0 (MPL 2.0)", YELLOW),
        ("LGPL-3.0-or-later", YELLOW),
        ("GPL-3.0-only", ORANGE),
        ("GNU General Public License v2 (GPLv2)", ORANGE),
        ("AGPL-3.0", RED),
        ("Server Side Public License", RED),
        ("CC-BY-NC-4.0", RED),
        ("", UNKNOWN),
        ("NOASSERTION", UNKNOWN),
        ("Garip Özel Lisans", UNKNOWN),
    ],
)
def test_lisans_siniflari(text: str, expected: str) -> None:
    assert classify_license(text) == expected


def test_or_ifadesinde_gevsek_secenek_gecerli() -> None:
    """Apache-2.0 OR GPL-3.0: kullanıcı izin vericiyi seçebilir."""
    assert classify_license("Apache-2.0 OR GPL-3.0-only") == GREEN


def test_and_ifadesinde_kati_sinif_kazanir() -> None:
    assert classify_license("MIT AND GPL-2.0-only") == ORANGE


def test_lisans_yoklugu_serbestlik_degildir() -> None:
    assert classify_license("") == UNKNOWN
    assert classify_license("None") == UNKNOWN


def test_karisik_proprietary_sinyali_incelemeye_dusar() -> None:
    """'BSD AND Other/Proprietary' gibi karışık sinyal sessizce GREEN olamaz."""
    assert classify_license("BSD License AND Other/Proprietary License") == YELLOW


# ---------------------------------------------------------------------------
# Tarayıcı
# ---------------------------------------------------------------------------
def test_requirements_ayiklama(tmp_path: Path) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text(
        "# yorum\nDjango==5.2.16  # not\nhttpx>=0.28\npython_dotenv[cli]==1.0\n\n-r other.txt\n",
        encoding="utf-8",
    )
    assert parse_requirements(req) == ["django", "httpx", "python-dotenv"]


def test_kurulu_olmayan_paket_unknown_olur(tmp_path: Path) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("boyle-bir-paket-yok==1.0\n", encoding="utf-8")
    records = scan_runtime_closure(req)
    assert len(records) == 1
    assert records[0].classification == UNKNOWN
    assert records[0].direct


def test_gercek_ortam_taramasi_calisiyor() -> None:
    """Projenin gerçek requirements.txt kapanımı taranabilmelidir."""
    records = scan_runtime_closure(Path("requirements.txt"))
    names = {record.name for record in records}
    assert "django" in names
    assert all(record.declared_license for record in records)
    django_record = next(record for record in records if record.name == "django")
    assert django_record.classification == GREEN
    assert django_record.direct


# ---------------------------------------------------------------------------
# SPDX
# ---------------------------------------------------------------------------
def _record(**overrides) -> ComponentRecord:
    defaults = {
        "name": "example",
        "version": "1.0",
        "declared_license": "MIT",
        "evidence_source": "classifier",
        "classification": GREEN,
        "direct": True,
    }
    defaults.update(overrides)
    return ComponentRecord(**defaults)


def test_spdx_belgesi_asgari_alanlari_tasir() -> None:
    document = build_spdx_document([_record(), _record(name="ikinci", declared_license="")])
    assert document["spdxVersion"] == "SPDX-2.3"
    assert document["dataLicense"] == "CC0-1.0"
    assert len(document["packages"]) == 2
    assert len(document["relationships"]) == 2
    first = document["packages"][0]
    assert first["licenseConcluded"] == "NOASSERTION"  # hukuki sonuç çıkarılmaz
    assert first["externalRefs"][0]["referenceLocator"] == "pkg:pypi/example@1.0"
    second = document["packages"][1]
    assert second["licenseDeclared"] == "NOASSERTION"


# ---------------------------------------------------------------------------
# Gate komutu
# ---------------------------------------------------------------------------
def test_license_scan_gate_gercek_ortamda_gecer(capsys) -> None:
    """Projenin gerçek bağımlılıkları gate'i geçmelidir (tamamı izin verici)."""
    call_command("license_scan", "--gate")
    out = capsys.readouterr().out
    assert "Lisans gate geçti" in out


def test_license_scan_gate_unknown_paketle_kirilir(tmp_path: Path, capsys) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("boyle-bir-paket-yok==1.0\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        call_command("license_scan", "--gate", "--requirements", str(req))


def test_license_scan_spdx_dosyasi_yazar(tmp_path: Path) -> None:
    target = tmp_path / "sbom.json"
    call_command("license_scan", "--spdx", str(target))
    document = json.loads(target.read_text(encoding="utf-8"))
    assert document["spdxVersion"] == "SPDX-2.3"
    assert document["packages"]
