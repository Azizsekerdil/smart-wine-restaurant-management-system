"""Güvenlik ve gizlilik birim testleri.

Kapsam:
  * Gizli değer (API anahtarı) maskeleme
  * KVKK kişisel veri maskeleme
  * Alan şifreleme ve aranabilir özet
  * Denetim kaydının değiştirilemezliği
  * Çalışma alanı sınırı
"""

from __future__ import annotations

import pytest

from apps.core.security import (
    MASK_TOKEN,
    WorkspaceViolationError,
    decrypt_text,
    encrypt_text,
    mask_pii,
    mask_secrets,
    redact_key,
    resolve_within_workspace,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Gizli değer maskeleme
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "ANTHROPIC_API_KEY=sk-ant-api03-abcdefghijklmnopqrstuvwxyz012345",
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9abcdef",
        "nvapi-abcdefghijklmnopqrstuvwxyz0123456789",
        "token: ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        "AWS anahtarı AKIAIOSFODNN7EXAMPLE kullanıldı",
        "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz",
        "password=CokGizliParola123",
    ],
)
def test_gizli_degerler_maskelenir(text: str) -> None:
    """Bilinen anahtar biçimleri günlüğe düz metin olarak yazılamaz."""
    masked = mask_secrets(text)
    assert MASK_TOKEN in masked
    # Anahtarın gövdesi çıktıda kalmamalı
    for fragment in ("abcdefghijklmnop", "IOSFODNN7EXAMPLE", "CokGizliParola123"):
        assert fragment not in masked


def test_pem_ozel_anahtar_maskelenir() -> None:
    pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEAx7Vd8yQ\n"
        "-----END RSA PRIVATE KEY-----"
    )
    assert "MIIEowIBAAKCAQEAx7Vd8yQ" not in mask_secrets(pem)


def test_normal_metin_bozulmaz() -> None:
    text = "Bugün 3 şişe Öküzgözü satıldı; masa 12 kapandı."
    assert mask_secrets(text) == text


def test_redact_key_yalnizca_son_dort_haneyi_gosterir() -> None:
    """Arayüz yalnızca son 4 karakteri görür; sağlayıcı ön eki sızmaz."""
    redacted = redact_key("sk-ant-api03-0123456789abcdef")
    assert redacted == "••••cdef"
    assert "sk-" not in redacted
    assert "api03" not in redacted
    assert redact_key("kisa") == MASK_TOKEN
    assert redact_key("") == ""


# ---------------------------------------------------------------------------
# Kişisel veri (PII) maskeleme
# ---------------------------------------------------------------------------
def test_eposta_ve_telefon_maskelenir() -> None:
    result = mask_pii("Müşteri: ayse@ornek.com, telefon 0555 123 45 67")
    assert "ayse@ornek.com" not in result.text
    assert "[E-POSTA]" in result.text
    assert "[TELEFON]" in result.text
    assert result.was_masked


def test_tckn_maskelenir() -> None:
    result = mask_pii("Kimlik no 12345678901 olarak kaydedildi.")
    assert "12345678901" not in result.text
    assert "[TCKN]" in result.text


def test_gecerli_kart_maskelenir_gecersiz_maskelenmez() -> None:
    """Luhn geçerli kart maskelenir; rastgele uzun sayı maskelenmez."""
    gecerli = mask_pii("Kart 4111111111111111 ile ödendi.")
    assert "4111111111111111" not in gecerli.text
    assert "[KART_NO]" in gecerli.text

    gecersiz = mask_pii("Adisyon numarası 1234567890123456 kaydedildi.")
    assert "1234567890123456" in gecersiz.text


def test_iban_maskelenir() -> None:
    result = mask_pii("IBAN: TR33 0006 1005 1978 6457 8413 26")
    assert "[IBAN]" in result.text


def test_ek_terimler_maskelenir() -> None:
    """Müşteri adı gibi serbest metinler de maskelenebilir."""
    result = mask_pii("Deniz Yılmaz masaya oturdu.", extra_terms=["Deniz Yılmaz"])
    assert "Deniz Yılmaz" not in result.text
    assert "[KİŞİ]" in result.text


def test_maskeleme_ozeti_okunur() -> None:
    result = mask_pii("a@b.com ve c@d.com yazdı, 0555 111 22 33 aradı.")
    assert result.was_masked
    assert "E-POSTA" in result.summary()


def test_temiz_metinde_maskeleme_yok() -> None:
    result = mask_pii("Kuzu tandır için hangi şarabı önerirsin?")
    assert not result.was_masked
    assert result.summary() == "Kişisel veri bulunamadı."


# ---------------------------------------------------------------------------
# Şifreleme
# ---------------------------------------------------------------------------
def test_sifrele_coz_tur_gidis_donus() -> None:
    plaintext = "Öküzgözü — 0555 123 45 67 · ğüşiöçĞÜŞİÖÇ"
    ciphertext = encrypt_text(plaintext)
    assert ciphertext != plaintext
    assert plaintext not in ciphertext
    assert decrypt_text(ciphertext) == plaintext


def test_bozuk_sifreli_metin_bos_doner() -> None:
    assert decrypt_text("bu-gecerli-bir-token-degil") == ""


@pytest.mark.django_db
def test_sifreli_alan_veritabaninda_duz_metin_degil(waiter) -> None:
    """Müşteri telefonu veritabanı seviyesinde okunamaz olmalı."""
    from django.db import connection

    from apps.crm.models import Customer

    customer = Customer.objects.create(
        code="MST-TEST", first_name="Test", last_name="Müşteri", phone="+90 555 999 88 77"
    )

    with connection.cursor() as cursor:
        cursor.execute("SELECT phone FROM crm_customer WHERE id = %s", [customer.pk])
        raw = cursor.fetchone()[0]

    assert "555 999 88 77" not in raw
    assert raw.startswith("enc$v1$")
    # Uygulama katmanı doğru çözer
    assert Customer.objects.get(pk=customer.pk).phone == "+90 555 999 88 77"


@pytest.mark.django_db
def test_aranabilir_ozet_ile_telefon_bulunur() -> None:
    """Şifreli alanda eşitlik araması HMAC özeti üzerinden çalışır."""
    from apps.core.fields import blind_index
    from apps.crm.models import Customer

    Customer.objects.create(code="MST-A", first_name="A", phone="+90 555 111 22 33")
    found = Customer.objects.filter(phone_index=blind_index("+90 555 111 22 33"))
    assert found.count() == 1
    # Özetten düz metne dönülemez
    assert "555" not in blind_index("+90 555 111 22 33")


# ---------------------------------------------------------------------------
# Denetim kaydı değiştirilemezliği
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_denetim_kaydi_guncellenemez(admin_user) -> None:
    from apps.core.audit import record
    from apps.core.models import AuditAction

    entry = record(action=AuditAction.LOGIN, message="test", actor=admin_user)
    entry.message = "değiştirildi"
    with pytest.raises(ValueError, match="değiştirilemez"):
        entry.save()


@pytest.mark.django_db
def test_denetim_kaydi_silinemez(admin_user) -> None:
    from apps.core.audit import record
    from apps.core.models import AuditAction

    entry = record(action=AuditAction.LOGIN, message="test", actor=admin_user)
    with pytest.raises(ValueError, match="silinemez"):
        entry.delete()


@pytest.mark.django_db
def test_denetim_kaydinda_gizli_deger_maskelenir(admin_user) -> None:
    """Denetim mesajına anahtar sızarsa kayda maskelenmiş girer."""
    from apps.core.audit import record
    from apps.core.models import AuditAction

    entry = record(
        action=AuditAction.SETTINGS,
        message="Anahtar güncellendi: sk-ant-api03-gizliolmayanbirseyler123456",
        actor=admin_user,
    )
    entry.refresh_from_db()
    assert "gizliolmayanbirseyler" not in entry.message
    assert MASK_TOKEN in entry.message


@pytest.mark.django_db
def test_stok_hareketi_degistirilemez(stock_item, warehouse) -> None:
    """Stok hareketleri denetim izi olduğundan güncellenemez."""
    from decimal import Decimal

    from apps.inventory.models import StockMovement

    movement = StockMovement.objects.filter(stock_item=stock_item).first()
    movement.quantity = Decimal("999")
    with pytest.raises(ValueError, match="değiştirilemez"):
        movement.save()
    with pytest.raises(ValueError, match="silinemez"):
        movement.delete()


# ---------------------------------------------------------------------------
# Çalışma alanı sınırı
# ---------------------------------------------------------------------------
def test_calisma_alani_disina_cikilamaz(tmp_path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()

    inside = resolve_within_workspace("src/app.py", workspace)
    assert str(inside).startswith(str(workspace.resolve()))

    for escape in ["../gizli.txt", "../../etc/passwd", "/etc/passwd"]:
        with pytest.raises(WorkspaceViolationError):
            resolve_within_workspace(escape, workspace)


def test_gunluk_filtresi_maskeler() -> None:
    """Logging filtresi kayda giren gizli değeri maskeler."""
    import logging

    from apps.core.logging_filters import SecretMaskingFilter

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Bağlanılıyor: nvapi-0123456789abcdefghijklmnop",
        args=(),
        exc_info=None,
    )
    SecretMaskingFilter().filter(record)
    assert "0123456789abcdefghijklmnop" not in record.msg
    assert MASK_TOKEN in record.msg
