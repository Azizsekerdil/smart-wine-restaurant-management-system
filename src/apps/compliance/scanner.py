"""Python bağımlılık ve lisans tarayıcısı (prompt §8.1).

``requirements.txt`` içindeki doğrudan bağımlılıklardan başlayarak kurulu
ortamdaki *çalışma zamanı kapanımını* (runtime closure) çıkarır; her bileşen
için beyan edilen lisansı, kanıt kaynağını ve risk sınıfını üretir.

Kanıt öncelik sırası: ``License-Expression`` (PEP 639) → trove classifier →
``License`` serbest metni. Hiçbiri yoksa sonuç ``UNKNOWN``'dır — lisans
yokluğu serbestlik sayılmaz.

Kapsam notu (dürüst sınır): yalnızca pip/kurulu ortam taranır. npm/Unity,
vendored kaynak, binary ve OS paketleri bu tarayıcının kapsamı dışındadır.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import metadata as importlib_metadata
from pathlib import Path

from apps.compliance.licenses import UNKNOWN, classify_license


@dataclass
class ComponentRecord:
    """Tek bileşenin lisans değerlendirmesi."""

    name: str
    version: str
    declared_license: str
    evidence_source: str  # license-expression | classifier | license-field | none
    classification: str
    direct: bool
    requires: list[str] = field(default_factory=list)


def _norm(name: str) -> str:
    return name.lower().replace("_", "-").strip()


def parse_requirements(path: Path) -> list[str]:
    """requirements dosyasından paket adlarını çıkarır (pin/işaret ayıklanır)."""
    names: list[str] = []
    if not path.exists():
        return names
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        name = re.split(r"[<>=!\[;\s]", line)[0]
        if name:
            names.append(_norm(name))
    return names


def _installed_distributions() -> dict[str, importlib_metadata.Distribution]:
    dists: dict[str, importlib_metadata.Distribution] = {}
    for dist in importlib_metadata.distributions():
        name = _norm(dist.metadata["Name"] or "")
        if name:
            dists[name] = dist
    return dists


def _requires(dist: importlib_metadata.Distribution) -> list[str]:
    out: list[str] = []
    for req in dist.requires or []:
        if "extra ==" in req:
            continue
        name = re.split(r"[\s\[<>=!;(]", req.strip())[0]
        if name:
            out.append(_norm(name))
    return out


def _license_evidence(dist: importlib_metadata.Distribution) -> tuple[str, str]:
    """(beyan edilen lisans, kanıt kaynağı) çifti döndürür."""
    md = dist.metadata

    expression = (md["License-Expression"] or "").strip() if "License-Expression" in md else ""
    if expression:
        return expression, "license-expression"

    classifiers = [
        c.split("::")[-1].strip()
        for c in (md.get_all("Classifier") or [])
        if c.startswith("License ::") and c.split("::")[-1].strip() != "OSI Approved"
    ]
    if classifiers:
        return " AND ".join(sorted(set(classifiers))), "classifier"

    license_field = (md["License"] or "").strip() if "License" in md else ""
    # Bazı paketler License alanına tam lisans metni gömer; ilk satır yeterlidir.
    if license_field:
        return license_field.splitlines()[0][:120], "license-field"

    return "", "none"


def scan_runtime_closure(requirements_path: Path) -> list[ComponentRecord]:
    """Çalışma zamanı kapanımını tarar ve bileşen kayıtları üretir.

    requirements dosyasında olup kurulu ortamda bulunmayan paketler de
    ``UNKNOWN`` kayıt olarak döner (kanıt yokluğu gizlenmez).
    """
    direct = parse_requirements(requirements_path)
    dists = _installed_distributions()

    closure: set[str] = set()
    stack = list(direct)
    while stack:
        name = stack.pop()
        if name in closure or name not in dists:
            continue
        closure.add(name)
        stack.extend(_requires(dists[name]))

    records: list[ComponentRecord] = []
    for name in sorted(closure):
        dist = dists[name]
        declared, source = _license_evidence(dist)
        records.append(
            ComponentRecord(
                name=name,
                version=dist.version or "",
                declared_license=declared or "NOASSERTION",
                evidence_source=source,
                classification=classify_license(declared),
                direct=name in direct,
                requires=_requires(dist),
            )
        )

    for name in direct:
        if name not in dists:
            records.append(
                ComponentRecord(
                    name=name,
                    version="",
                    declared_license="NOASSERTION",
                    evidence_source="none",
                    classification=UNKNOWN,
                    direct=True,
                )
            )
    return records
