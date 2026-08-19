"""Şifreli veritabanı alanları.

Hassas kişisel veriler (telefon, e-posta, adres) ve API anahtarları
veritabanında Fernet ile şifrelenmiş olarak saklanır.

Kısıt: Şifreli alanlar üzerinde veritabanı seviyesinde arama/sıralama
yapılamaz. Arama gerektiren alanlar için ayrıca *aranabilir özet*
(HMAC) sütunu tutulur.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from django.conf import settings
from django.db import models

from apps.core.security import decrypt_text, encrypt_text, encryption_available


class EncryptedTextField(models.TextField):
    """Değeri veritabanına şifreli yazan, okurken çözen metin alanı.

    Şifreleme anahtarı yapılandırılmamışsa alan düz metin olarak çalışır ve
    sistem kontrolü (``core.W001``) uyarı üretir. Böylece anahtarsız bir
    kurulum çökmez, ancak durum açıkça raporlanır.
    """

    description = "Fernet ile şifrelenmiş metin"

    #: Şifreli değerlerin başına eklenen işaret; geriye dönük uyumluluk sağlar.
    PREFIX = "enc$v1$"

    def get_prep_value(self, value: Any) -> Any:
        if value is None or value == "":
            return value
        text = str(value)
        if text.startswith(self.PREFIX):
            return text  # zaten şifreli
        if not encryption_available():
            return text
        return self.PREFIX + encrypt_text(text)

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> Any:
        return self._decode(value)

    def to_python(self, value: Any) -> Any:
        return self._decode(value)

    def _decode(self, value: Any) -> Any:
        if value is None or value == "":
            return value
        text = str(value)
        if not text.startswith(self.PREFIX):
            return text  # düz metin (anahtarsız kurulumdan kalan kayıt)
        return decrypt_text(text[len(self.PREFIX) :])


class EncryptedCharField(EncryptedTextField):
    """Kısa hassas metinler için şifreli alan (ör. telefon numarası)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Şifreli metin ham metinden uzun olduğu için sütun uzunluğu sabitlenmez.
        kwargs.pop("max_length", None)
        super().__init__(*args, **kwargs)


def blind_index(value: str) -> str:
    """Şifreli alanda eşitlik araması için HMAC-SHA256 özeti üretir.

    Aynı düz metin her zaman aynı özeti verir; özetten düz metne dönülemez.
    Örnek kullanım: müşteri telefonuyla kayıt arama.
    """
    if not value:
        return ""
    key = (getattr(settings, "FIELD_ENCRYPTION_KEY", "") or "winehouse-fallback").encode()
    normalized = value.strip().lower().encode("utf-8")
    return hmac.new(key, normalized, hashlib.sha256).hexdigest()
