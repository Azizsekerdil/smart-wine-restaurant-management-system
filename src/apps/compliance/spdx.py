"""SPDX 2.3 JSON belge üretimi (prompt §8.2).

Tarayıcı çıktısından asgari, şema-uyumlu bir SPDX belgesi üretir.
``licenseConcluded`` bilinçli olarak ``NOASSERTION`` bırakılır: araç lisans
*beyanını* aktarır, hukuki *sonuç* çıkarmaz.
"""

from __future__ import annotations

import hashlib

from django.utils import timezone

from apps.compliance.scanner import ComponentRecord

_SPDX_ID_SAFE = str.maketrans(dict.fromkeys("._", "-"))


def _spdx_id(record: ComponentRecord) -> str:
    return f"SPDXRef-Package-{record.name.translate(_SPDX_ID_SAFE)}"


def build_spdx_document(
    records: list[ComponentRecord], *, project_name: str = "wine-house"
) -> dict:
    """Bileşen kayıtlarından SPDX 2.3 JSON sözlüğü üretir."""
    created = timezone.now().replace(microsecond=0).isoformat().replace("+00:00", "Z")
    namespace_seed = ",".join(f"{r.name}@{r.version}" for r in records)
    namespace_hash = hashlib.sha256(namespace_seed.encode("utf-8")).hexdigest()[:16]

    packages = []
    relationships = []
    for record in records:
        spdx_id = _spdx_id(record)
        packages.append(
            {
                "SPDXID": spdx_id,
                "name": record.name,
                "versionInfo": record.version or "NOASSERTION",
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseDeclared": record.declared_license or "NOASSERTION",
                "licenseConcluded": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": (
                            f"pkg:pypi/{record.name}@{record.version}"
                            if record.version
                            else f"pkg:pypi/{record.name}"
                        ),
                    }
                ],
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": spdx_id,
            }
        )

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{project_name}-runtime-sbom",
        "documentNamespace": (f"https://spdx.org/spdxdocs/{project_name}-runtime-{namespace_hash}"),
        "creationInfo": {
            "created": created,
            "creators": ["Tool: winehouse-compliance-scanner"],
        },
        "packages": packages,
        "relationships": relationships,
    }
