"""Lisans sınıflandırma politikası (prompt §8.1).

Sonuçlar açıklanabilir ``GREEN/YELLOW/ORANGE/RED/UNKNOWN`` etiketleridir ve
**hukuki kesinlik iddiası taşımaz**; nihai değerlendirme hukuk incelemesinindir.

Dağıtım senaryosu varsayımı: tescilli (proprietary), on-prem dağıtılan ürün.
Bu senaryoda:

* ``GREEN``   — izin verici; bildirim/atıf yükümlülükleriyle dağıtılabilir.
* ``YELLOW``  — zayıf copyleft; yükümlülükler yönetilebilir, dikkat ister.
* ``ORANGE``  — güçlü copyleft; dağıtım öncesi hukuk incelemesi zorunlu.
* ``RED``     — ağ copyleft / source-available / ticari kısıt; bu senaryoda
  yüksek risk.
* ``UNKNOWN`` — lisans tespit edilemedi. Lisans yokluğu serbestlik değildir;
  ``REVIEW_REQUIRED`` anlamına gelir.
"""

from __future__ import annotations

import re

GREEN = "GREEN"
YELLOW = "YELLOW"
ORANGE = "ORANGE"
RED = "RED"
UNKNOWN = "UNKNOWN"

#: Normalize edilmiş metinde aranan kalıplar; sıra önemlidir — en kısıtlayıcı
#: aile önce denetlenir (ör. AGPL, GPL kalıbından önce yakalanmalıdır).
_FAMILY_PATTERNS: list[tuple[str, str]] = [
    (r"\bAGPL|AFFERO", RED),
    (r"\bSSPL|SERVER SIDE PUBLIC", RED),
    (r"\bBUSL|BUSINESS SOURCE", RED),
    (r"NON-?COMMERCIAL|\bNC\b", RED),
    (r"NO-?DERIVATIVES|\bND\b", RED),
    (r"\bLGPL|LESSER GENERAL PUBLIC", YELLOW),
    (r"\bGPL|GENERAL PUBLIC LICENSE", ORANGE),
    (r"\bMPL|MOZILLA PUBLIC", YELLOW),
    (r"\bEPL|ECLIPSE PUBLIC", YELLOW),
    (r"\bEUPL", ORANGE),
    (r"\bCDDL", YELLOW),
    (r"CC-BY-SA|SHAREALIKE", ORANGE),
    (r"PROPRIETARY|EULA", YELLOW),  # karışık sinyal: insan incelemesi işareti
    (r"CC0|PUBLIC DOMAIN|\bUNLICENSE\b|WTFPL", GREEN),
    (r"CC-BY\b|CREATIVE COMMONS ATTRIBUTION\b", YELLOW),
    (r"\bMIT\b", GREEN),
    (r"\bBSD\b", GREEN),
    (r"\bISC\b", GREEN),
    (r"\bAPACHE", GREEN),
    (r"\bPSF|PYTHON SOFTWARE FOUNDATION|PYTHON-2\.0", GREEN),
    (r"\bZLIB\b|\bZPL\b", GREEN),
    (r"\bHPND\b", GREEN),
    (r"\bMIT-CMU\b|CMU\b", GREEN),
]


def classify_license(text: str) -> str:
    """Lisans metnini/tanımını risk sınıfına çevirir.

    ``text`` SPDX ifadesi, ``License`` metadata alanı veya trove classifier
    birleşimi olabilir. Boş/anlaşılamayan girdi ``UNKNOWN`` döndürür — asla
    sessizce ``GREEN`` sayılmaz.
    """
    normalized = (text or "").upper().strip()
    if not normalized or normalized in {"UNKNOWN", "NOASSERTION", "NONE"}:
        return UNKNOWN

    matches = [cls for pattern, cls in _FAMILY_PATTERNS if re.search(pattern, normalized)]
    if not matches:
        return UNKNOWN

    # SPDX "OR" ifadesinde en gevşek seçenek seçilebilir; "AND"/karışımda en
    # katı sınıf geçerlidir. Ayrım yapılamayan durumda ihtiyatlı davranılır.
    severity = {GREEN: 0, YELLOW: 1, ORANGE: 2, RED: 3}
    if " OR " in normalized and " AND " not in normalized:
        return min(matches, key=lambda c: severity[c])
    return max(matches, key=lambda c: severity[c])


#: Gate'in çalışma zamanı kapanımında (runtime closure) engellediği sınıflar.
BLOCKING_CLASSES = frozenset({ORANGE, RED, UNKNOWN})
