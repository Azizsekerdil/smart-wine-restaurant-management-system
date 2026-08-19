"""Wine House — güvenlik ve gizlilik yardımcıları.

Bu modül üç sorumluluğu üstlenir:

1. **Alan şifreleme**  — hassas alanların (telefon, e-posta, API anahtarı)
   veritabanında Fernet ile şifrelenerek saklanması.
2. **Gizli değer maskeleme** — API anahtarlarının günlüklere, terminal
   çıktılarına veya arayüze sızmasının engellenmesi.
3. **Kişisel veri maskeleme** — bulut yapay zekâ sağlayıcısına metin
   gönderilmeden önce KVKK/GDPR kapsamındaki kişisel verilerin maskelenmesi.

Tasarım notu: maskeleme *geri döndürülemez* olacak şekilde tasarlanmıştır.
Bulut sağlayıcıya gönderilen metinden orijinal kişisel veriye ulaşılamaz.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from django.conf import settings

# ---------------------------------------------------------------------------
# 1) ALAN ŞİFRELEME
# ---------------------------------------------------------------------------


class EncryptionUnavailableError(RuntimeError):
    """Şifreleme anahtarı yapılandırılmadığında yükseltilir."""


@lru_cache(maxsize=1)
def _get_fernet() -> Any:
    """Yapılandırılmış Fernet örneğini döndürür (önbelleklenir)."""
    from cryptography.fernet import Fernet

    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""
    if not key:
        raise EncryptionUnavailableError(
            "WINEHOUSE_FIELD_ENCRYPTION_KEY tanımlı değil. Hassas alan şifrelemesi "
            "kullanılamaz. Anahtar üretmek için:\n"
            '    python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def encryption_available() -> bool:
    """Şifrelemenin kullanılabilir olup olmadığını bildirir."""
    try:
        _get_fernet()
    except Exception:
        return False
    return True


def encrypt_text(plaintext: str) -> str:
    """Metni şifreler ve URL güvenli base64 dizgi olarak döndürür."""
    if plaintext is None or plaintext == "":
        return ""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_text(ciphertext: str) -> str:
    """Şifreli metni çözer. Çözülemezse boş dizgi döndürür."""
    if not ciphertext:
        return ""
    from cryptography.fernet import InvalidToken

    try:
        return _get_fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, EncryptionUnavailableError, ValueError):
        return ""


def generate_encryption_key() -> str:
    """Yeni bir Fernet anahtarı üretir (kurulum betiği kullanır)."""
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode("ascii")


# ---------------------------------------------------------------------------
# 2) GİZLİ DEĞER MASKELEME (API anahtarları, parolalar, belirteçler)
# ---------------------------------------------------------------------------

#: Bilinen API anahtarı biçimleri. Sızıntıyı önlemek için agresif davranılır.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Anthropic:  sk-ant-api03-....
    ("anthropic", re.compile(r"sk-ant-[A-Za-z0-9\-_]{8,}")),
    # OpenAI uyumlu: sk-....
    ("openai", re.compile(r"\bsk-(?!ant-)[A-Za-z0-9\-_]{16,}")),
    # NVIDIA NGC: nvapi-....
    ("nvidia", re.compile(r"\bnvapi-[A-Za-z0-9\-_]{8,}")),
    # GitHub: ghp_/gho_/ghs_/ghu_/ghr_ + 36
    ("github", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    # AWS erişim anahtarı
    ("aws", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    # Genel Bearer belirteci
    ("bearer", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]{16,}=*")),
    # KEY=VALUE biçiminde ortam değişkeni sızıntısı
    (
        "env_assignment",
        re.compile(
            r"(?i)\b([A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE_KEY)"
            r"[A-Z0-9_]*)\s*[=:]\s*[\"']?([^\s\"',;]{6,})"
        ),
    ),
    # PEM özel anahtar blokları
    (
        "pem",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
)

MASK_TOKEN = "***GİZLİ***"

#: Kısmi gösterimde kullanılan sabit önek (uzunluk bilgisi sızdırmaz).
REDACTION_PREFIX = "••••"


def mask_secrets(text: str) -> str:
    """Metindeki API anahtarı / parola benzeri değerleri maskeler.

    Günlükler, terminal çıktıları ve arayüzde gösterilecek her metin bu
    fonksiyondan geçirilmelidir.
    """
    if not text:
        return text

    masked = text
    for name, pattern in SECRET_PATTERNS:
        if name == "env_assignment":
            masked = pattern.sub(lambda m: f"{m.group(1)}={MASK_TOKEN}", masked)
        else:
            masked = pattern.sub(MASK_TOKEN, masked)
    return masked


def redact_key(value: str, keep: int = 4) -> str:
    """Gizli değeri arayüzde göstermek için kısaltır: ``••••9f2c``.

    Yalnızca **son** ``keep`` karakter açıkta bırakılır; ön ek gösterilmez.
    Sağlayıcı ön ekleri (``sk-ant-``, ``nvapi-`` gibi) anahtarın hangi hesaba
    ait olduğuna dair bilgi taşır ve arayüzde, ekran görüntüsünde veya destek
    kaydında görünmesine gerek yoktur. Değer kısa ise tamamı maskelenir.
    """
    if not value:
        return ""
    if len(value) <= keep:
        return MASK_TOKEN
    return f"{REDACTION_PREFIX}{value[-keep:]}"


# ---------------------------------------------------------------------------
# 3) KİŞİSEL VERİ (PII) MASKELEME — buluta gönderim öncesi
# ---------------------------------------------------------------------------

PII_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        "[E-POSTA]",
    ),
    (
        "iban",
        re.compile(r"\bTR\s?\d{2}(?:\s?\d{4}){5}\s?\d{2}\b", re.IGNORECASE),
        "[IBAN]",
    ),
    (
        "credit_card",
        re.compile(r"\b(?:\d[ \-]?){13,19}\b"),
        "[KART_NO]",
    ),
    (
        "tckn",
        re.compile(r"\b[1-9]\d{10}\b"),
        "[TCKN]",
    ),
    (
        "phone_tr",
        re.compile(r"(?:\+90|0)?[\s\-.]?\(?5\d{2}\)?[\s\-.]?\d{3}[\s\-.]?\d{2}[\s\-.]?\d{2}\b"),
        "[TELEFON]",
    ),
    (
        "phone_generic",
        re.compile(r"\+\d{1,3}[\s\-.]?\d[\d\s\-.]{7,}\d"),
        "[TELEFON]",
    ),
)


@dataclass
class MaskingResult:
    """Maskeleme sonucu: temizlenmiş metin ve neyin maskelendiği."""

    text: str
    replacements: dict[str, int] = field(default_factory=dict)

    @property
    def was_masked(self) -> bool:
        return bool(self.replacements)

    def summary(self) -> str:
        """Kullanıcıya gösterilecek kısa özet."""
        if not self.replacements:
            return "Kişisel veri bulunamadı."
        parts = [f"{count}× {label}" for label, count in sorted(self.replacements.items())]
        return "Maskelenen: " + ", ".join(parts)


def mask_pii(text: str, *, extra_terms: list[str] | None = None) -> MaskingResult:
    """Kişisel verileri maskeler ve neyin maskelendiğini raporlar.

    Args:
        text: Maskelenecek metin.
        extra_terms: Ek olarak maskelenecek serbest metinler (örn. müşteri
            ad-soyad bilgileri veritabanından okunup buraya verilir).

    Returns:
        Maskelenmiş metni ve maskeleme sayaçlarını içeren ``MaskingResult``.
    """
    if not text:
        return MaskingResult(text="", replacements={})

    counts: dict[str, int] = {}
    result = text

    # Önce gizli anahtarlar — bunlar hiçbir koşulda dışarı çıkmamalı.
    before = result
    result = mask_secrets(result)
    if result != before:
        counts["GİZLİ_ANAHTAR"] = counts.get("GİZLİ_ANAHTAR", 0) + 1

    # Kullanıcıya özel serbest terimler (ad, soyad, adres satırı vb.)
    for term in extra_terms or []:
        cleaned = (term or "").strip()
        if len(cleaned) < 3:
            continue
        pattern = re.compile(re.escape(cleaned), re.IGNORECASE)
        result, n = pattern.subn("[KİŞİ]", result)
        if n:
            counts["KİŞİ"] = counts.get("KİŞİ", 0) + n

    for label, pattern, replacement in PII_PATTERNS:
        if label == "credit_card":
            # Yanlış pozitifleri azalt: yalnızca Luhn geçerli diziler maskelenir.
            hits = 0

            def _card_sub(match: re.Match[str], _repl: str = replacement) -> str:
                nonlocal hits
                digits = re.sub(r"\D", "", match.group(0))
                if _luhn_valid(digits):
                    hits += 1
                    return _repl
                return match.group(0)

            result = pattern.sub(_card_sub, result)
            n = hits
        else:
            result, n = pattern.subn(replacement, result)
        if n:
            key = replacement.strip("[]")
            counts[key] = counts.get(key, 0) + n

    return MaskingResult(text=result, replacements=counts)


def _luhn_valid(digits: str) -> bool:
    """Luhn algoritmasıyla kart numarası doğrulaması."""
    if not digits.isdigit() or not (13 <= len(digits) <= 19):
        return False
    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


# ---------------------------------------------------------------------------
# 4) YOL GÜVENLİĞİ — AI Development Studio çalışma alanı sınırı
# ---------------------------------------------------------------------------


class WorkspaceViolationError(PermissionError):
    """Çalışma alanı dışına yazma girişiminde yükseltilir."""


def resolve_within_workspace(candidate: str, workspace: Any) -> Any:
    """``candidate`` yolunu çözer ve ``workspace`` içinde kaldığını doğrular.

    Sembolik bağlantı ve ``..`` ile kaçış denemelerini engeller.

    Raises:
        WorkspaceViolationError: Yol çalışma alanının dışına çıkıyorsa.
    """
    from pathlib import Path

    workspace_path = Path(workspace).resolve()
    target = Path(candidate)
    if not target.is_absolute():
        target = workspace_path / target
    resolved = target.resolve()

    try:
        resolved.relative_to(workspace_path)
    except ValueError as exc:
        raise WorkspaceViolationError(
            f"Yol çalışma alanının dışında: {resolved}\n"
            f"İzin verilen çalışma alanı: {workspace_path}"
        ) from exc
    return resolved


def partial_mask(value: str, *, keep_last: int = 2, mask_char: str = "•") -> str:
    """Bir tanımlayıcının yalnızca son birkaç karakterini açıkta bırakır.

    Liste ekranlarında veri minimizasyonu için kullanılır: operatör kaydı
    ayırt edebilir ama tam numara ekranda (ve ekran görüntüsünde) görünmez.
    Tam değer yalnızca yetkili rolün açtığı detay ekranında gösterilir.

    Biçim karakterleri (boşluk, ``+``, ``-``, parantez) korunur; yalnızca
    rakam ve harfler maskelenir.

        >>> partial_mask("+90 5XX XXX XX 04")
        '+90 ••• ••• •• 04'
    """
    text = (value or "").strip()
    if not text:
        return ""

    alnum_positions = [i for i, ch in enumerate(text) if ch.isalnum()]
    # Ülke kodu gibi ilk bilgi taşımayan kısımlar da maskelenir; yalnızca
    # sondaki `keep_last` karakter açıkta kalır.
    keep = set(alnum_positions[-keep_last:]) if keep_last > 0 else set()

    out = []
    for i, ch in enumerate(text):
        if not ch.isalnum() or i in keep:
            out.append(ch)
        else:
            out.append(mask_char)
    return "".join(out)
