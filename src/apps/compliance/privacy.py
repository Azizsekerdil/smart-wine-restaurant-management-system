"""Kişisel veri keşif tarayıcısı ve envanter üretimi (prompt §9).

Django model alanlarını (ad + tür + uygulama bağlamı) tarayarak kişisel veri
*adaylarını* bulur. Alan adı tek başına yeterli değildir: uygulamanın veri
öznesi (müşteri/personel/kullanıcı/misafir), alan türü ve şifreleme durumu
birlikte değerlendirilir; her bulguda kanıt ve güven düzeyi vardır.

Dürüst sınırlar:

* Yalnızca somut model alanları taranır; M2M/FK ilişkileri (ör. favori
  şaraplar) ve serbest metin *içeriği* kapsam dışıdır. Log/exports gibi
  dosya tabanlı kaynaklar taranmaz.
* Sonuçlar aday niteliğindedir; hukuki sınıflandırma DPO/hukuk incelemesine
  bırakılır (``REVIEW_REQUIRED`` yer tutucuları).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from django.apps import apps as django_apps

#: Taranan uygulamalar ve veri öznesi. Bu listede olmayan yerel uygulamalar
#: (catalog, cellar, inventory...) ürün/stok verisi taşır ve kişi öznesi
#: bulunmadığından bu sürümde taranmaz.
SUBJECT_BY_APP: dict[str, str] = {
    "crm": "müşteri",
    "operations": "misafir/müşteri",
    "hr": "personel",
    "accounts": "kullanıcı",
    "core": "kullanıcı",
    "aiservices": "kullanıcı",
    "hsp": "kullanıcı",
}

#: (kalıp, kategori, özel nitelikli mi, güven) — sıra önemlidir; ilk eşleşme kazanır.
_FIELD_PATTERNS: list[tuple[str, str, bool, str]] = [
    (r"national_id|tckn|passport|kimlik", "kimlik (resmî numara)", False, "high"),
    (r"allergy|alerji|dietary|beslenme|health|saglik", "sağlık adayı", True, "high"),
    (r"first_name|last_name|full_name|display_name", "kimlik", False, "high"),
    (r"birth", "kimlik (doğum)", False, "high"),
    (r"\bphone|telefon", "iletişim", False, "high"),
    (r"\bemail|e_posta|eposta", "iletişim", False, "high"),
    (r"ip_address", "çevrimiçi tanımlayıcı", False, "high"),
    (r"address|adres", "iletişim (adres)", False, "high"),
    (r"emergency_contact", "iletişim (acil durum)", False, "high"),
    (r"\biban\b|card_number|kart_no", "finansal", False, "high"),
    (r"salary|hourly_rate|wage|ucret|maas", "finansal (ücret)", False, "high"),
    (r"pin_hash|password|parola|secret|token_hash", "kimlik doğrulama", False, "high"),
    (r"user_agent", "çevrimiçi tanımlayıcı", False, "medium"),
    (r"blacklist", "davranış/değerlendirme", False, "medium"),
    (r"is_vip|segment|loyalty|sadakat", "davranış/tercih", False, "medium"),
    (r"preference|tercih|favorite|favori", "davranış/tercih", False, "medium"),
    (r"note|notlar", "serbest metin (PII içerebilir)", False, "low"),
]

#: Taranan somut alan türleri.
_SCANNABLE_TYPES = (
    "CharField",
    "TextField",
    "EmailField",
    "DateField",
    "DateTimeField",
    "DecimalField",
    "PositiveSmallIntegerField",
    "IntegerField",
    "GenericIPAddressField",
    "EncryptedCharField",
    "EncryptedTextField",
)


@dataclass
class PIIFinding:
    """Tek model alanı için kişisel veri adayı bulgusu."""

    app: str
    model: str
    fld: str
    verbose_name: str
    field_type: str
    category: str
    special_category: bool
    subject: str
    encrypted: bool
    confidence: str  # high | medium | low
    evidence: str = ""

    @property
    def key(self) -> str:
        return f"{self.app}.{self.model}.{self.fld}"


@dataclass
class PIIScanResult:
    findings: list[PIIFinding] = field(default_factory=list)
    scanned_models: int = 0
    scanned_fields: int = 0


def scan_models() -> PIIScanResult:
    """Kayıtlı modellerin somut alanlarını tarar."""
    result = PIIScanResult()
    for model in django_apps.get_models():
        app_label = model._meta.app_label
        if app_label not in SUBJECT_BY_APP:
            continue
        result.scanned_models += 1
        for model_field in model._meta.get_fields():
            field_type = type(model_field).__name__
            if field_type not in _SCANNABLE_TYPES:
                continue
            result.scanned_fields += 1
            name = model_field.name.lower()
            for pattern, category, special, confidence in _FIELD_PATTERNS:
                if not re.search(pattern, name):
                    continue
                result.findings.append(
                    PIIFinding(
                        app=app_label,
                        model=model.__name__,
                        fld=model_field.name,
                        verbose_name=str(getattr(model_field, "verbose_name", "")),
                        field_type=field_type,
                        category=category,
                        special_category=special,
                        subject=SUBJECT_BY_APP[app_label],
                        encrypted="Encrypted" in field_type,
                        confidence=confidence,
                        evidence=f"alan adı '{model_field.name}' ~ /{pattern}/",
                    )
                )
                break
    result.findings.sort(key=lambda f: (f.app, f.model, f.fld))
    return result


def build_ropa_markdown(result: PIIScanResult, retention_days: dict[str, int]) -> str:
    """ROPA (işleme faaliyetleri kaydı) *hazırlık* belgesi üretir.

    Bu çıktı resmî bir başvuru veya tamamlanmış ROPA değildir; amaç/hukuki
    dayanak alanları bilinçli olarak ``REVIEW_REQUIRED`` bırakılır.
    """
    lines = [
        "# ROPA Hazırlık Çıktısı (VERBİS/GDPR m.30 ön çalışması)",
        "",
        "> Bu belge otomatik taramayla üretilmiş bir **hazırlıktır**; resmî kayıt",
        "> veya tamamlanmış işleme envanteri değildir. Amaç ve hukuki dayanak",
        "> alanları DPO/hukuk incelemesi gerektirir (`REVIEW_REQUIRED`).",
        "",
        f"Tarama kapsamı: {result.scanned_models} model · "
        f"{result.scanned_fields} alan · {len(result.findings)} kişisel veri adayı",
        "",
        "## Saklama süresi tanımları (settings.DATA_RETENTION_DAYS)",
        "",
    ]
    if retention_days:
        lines += [f"- `{key}`: {value} gün" for key, value in sorted(retention_days.items())]
    else:
        lines.append("- Tanımlı saklama süresi bulunamadı: `REVIEW_REQUIRED`")
    lines.append("")

    by_app: dict[str, list[PIIFinding]] = {}
    for finding in result.findings:
        by_app.setdefault(finding.app, []).append(finding)

    for app_label, findings in sorted(by_app.items()):
        subject = SUBJECT_BY_APP.get(app_label, "?")
        lines += [
            f"## {app_label} — veri öznesi: {subject}",
            "",
            "| Model.Alan | Kategori | Özel nitelikli | Şifreli | Güven | Amaç | Hukuki dayanak |",
            "|---|---|---|---|---|---|---|",
        ]
        for f in findings:
            lines.append(
                f"| `{f.model}.{f.fld}` | {f.category} "
                f"| {'⚠️ evet' if f.special_category else 'hayır'} "
                f"| {'✅' if f.encrypted else '—'} | {f.confidence} "
                f"| REVIEW_REQUIRED | REVIEW_REQUIRED |"
            )
        lines.append("")

    special = [f for f in result.findings if f.special_category]
    if special:
        lines += [
            "## ⚠️ Özel nitelikli veri adayları (KVKK m.6 / GDPR m.9 ön işareti)",
            "",
        ]
        lines += [f"- `{f.key}` — {f.category} ({f.verbose_name})" for f in special]
        lines += [
            "",
            "Bu alanlar için açık rıza/istisna değerlendirmesi ve ek güvenlik",
            "önlemi incelemesi zorunludur.",
            "",
        ]
    return "\n".join(lines)


def diff_against_baseline(
    result: PIIScanResult, baseline_keys: set[str]
) -> tuple[list[PIIFinding], set[str]]:
    """Taramayı bilinen envanterle karşılaştırır.

    Returns:
        ``(yeni_bulgular, kaybolan_kayitlar)`` — yeni bulgu, envantere
        işlenmemiş kişisel veri alanı demektir (gate kırar); kaybolan kayıt
        alanın kaldırıldığını gösterir (bilgi amaçlı).
    """
    current = {finding.key for finding in result.findings}
    new = [finding for finding in result.findings if finding.key not in baseline_keys]
    removed = baseline_keys - current
    return new, removed
