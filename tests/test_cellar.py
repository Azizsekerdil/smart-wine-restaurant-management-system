"""Şarap kavı iş kuralı testleri.

Kritik doğrulama: kadeh satışı açılmış şişe hacminden doğru düşmelidir
(kabul senaryosu #9).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Şişe açma
# ---------------------------------------------------------------------------
def test_sise_acinca_stok_bir_azalir(wine, sommelier) -> None:
    from apps.cellar import services
    from apps.cellar.models import BottleOpening

    before = wine.bottles_on_hand
    opening = services.open_bottle(wine=wine, user=sommelier)
    wine.refresh_from_db()

    assert wine.bottles_on_hand == before - 1
    assert opening.status == BottleOpening.Status.OPEN
    assert opening.remaining_ml == wine.bottle_size_ml
    assert opening.initial_ml == 750


def test_stok_bitince_sise_acilamaz(wine, sommelier) -> None:
    from apps.cellar import services

    lot = wine.lots.first()
    lot.bottles_remaining = 0
    lot.save()

    with pytest.raises(services.InsufficientStockError, match="kapalı şişe kalmadı"):
        services.open_bottle(wine=wine, user=sommelier)


def test_fefo_en_erken_tuketilecek_partiyi_secer(wine, sommelier) -> None:
    """En erken 'best_before' tarihli parti önce açılmalıdır."""
    from django.utils import timezone

    from apps.cellar import services
    from apps.cellar.models import BottleLot

    eski = wine.lots.first()
    eski.best_before = timezone.localdate() + timezone.timedelta(days=200)
    eski.save()

    acil = BottleLot.objects.create(
        wine=wine,
        lot_code="LOT-ACIL",
        bottles_received=5,
        bottles_remaining=5,
        unit_cost=Decimal("300.00"),
        best_before=timezone.localdate() + timezone.timedelta(days=10),
    )

    opening = services.open_bottle(wine=wine, user=sommelier)
    assert opening.lot_id == acil.pk, "FEFO sırası uygulanmadı."


def test_koruma_sistemi_tazelik_suresini_uzatir(wine, sommelier) -> None:
    from apps.cellar import services
    from apps.cellar.models import BottleOpening

    standart = services.open_bottle(wine=wine, user=sommelier)
    coravin = services.open_bottle(
        wine=wine, user=sommelier, service_method=BottleOpening.ServiceMethod.CORAVIN
    )
    assert coravin.freshness_hours > standart.freshness_hours


# ---------------------------------------------------------------------------
# Kadeh servisi — KABUL SENARYOSU #9
# ---------------------------------------------------------------------------
def test_kadeh_servisi_hacmi_dogru_duser(wine, sommelier) -> None:
    from apps.cellar import services

    result = services.pour_glass(wine=wine, user=sommelier)

    assert result.opened_new_bottle, "İlk serviste şişe açılmalıydı."
    assert result.opening.remaining_ml == 750 - 150
    assert result.remaining_glasses == 4


def test_dort_kadeh_alti_yuz_ml_duser(wine, sommelier) -> None:
    from apps.cellar import services

    for _ in range(4):
        result = services.pour_glass(wine=wine, user=sommelier)

    assert result.opening.poured_ml == 600
    assert result.opening.remaining_ml == 150
    assert result.opening.glasses_poured == 4
    assert result.opening.yield_percent == Decimal("80.00")


def test_sise_bitince_yeni_sise_otomatik_acilir(wine, sommelier) -> None:
    from apps.cellar import services

    before = wine.bottles_on_hand
    yeni_sise_sayisi = 0
    for _ in range(6):  # 5 kadeh 1 şişeden çıkar, 6. yeni şişe gerektirir
        result = services.pour_glass(wine=wine, user=sommelier)
        if result.opened_new_bottle:
            yeni_sise_sayisi += 1

    wine.refresh_from_db()
    assert yeni_sise_sayisi == 2
    assert wine.bottles_on_hand == before - 2


def test_kadeh_hacmi_sise_hacminden_buyuk_olamaz(wine, sommelier) -> None:
    from apps.cellar import services

    with pytest.raises(services.CellarError, match="şişe hacminden"):
        services.pour_glass(wine=wine, user=sommelier, volume_ml=1000)


def test_otomatik_acma_kapaliyken_hata_verir(wine, sommelier) -> None:
    from apps.cellar import services

    with pytest.raises(services.InsufficientStockError, match="açık şişe yok"):
        services.pour_glass(wine=wine, user=sommelier, auto_open=False)


def test_dokulme_gelir_getirmez(wine, sommelier) -> None:
    from apps.cellar import services
    from apps.cellar.models import PouringRecord

    services.pour_glass(wine=wine, user=sommelier)
    result = services.pour_glass(
        wine=wine, user=sommelier, pour_type=PouringRecord.PourType.SPILLAGE
    )
    assert not result.pour.is_revenue
    # Hacim yine de düşer — fire de stoktan çıkar
    assert result.opening.remaining_ml == 750 - 300


def test_sise_kapatilinca_kalan_hacim_fire_yazilir(wine, sommelier) -> None:
    from apps.cellar import services
    from apps.cellar.models import BottleOpening, PouringRecord

    opening = services.open_bottle(wine=wine, user=sommelier)
    services.pour_glass(wine=wine, user=sommelier)

    closed = services.finish_bottle(opening=opening, user=sommelier, as_waste=True)
    assert closed.status == BottleOpening.Status.DISCARDED
    assert closed.remaining_ml == 0
    assert closed.pours.filter(pour_type=PouringRecord.PourType.WASTE).exists()


def test_kapali_sise_tekrar_kapatilamaz(wine, sommelier) -> None:
    from apps.cellar import services

    opening = services.open_bottle(wine=wine, user=sommelier)
    services.finish_bottle(opening=opening, user=sommelier)
    with pytest.raises(services.CellarError, match="zaten kapalı"):
        services.finish_bottle(opening=opening, user=sommelier)


# ---------------------------------------------------------------------------
# Kusur kaydı
# ---------------------------------------------------------------------------
def test_mantar_hatasi_stoktan_duser(wine, sommelier) -> None:
    from apps.cellar import services
    from apps.cellar.models import WineFault

    before = wine.bottles_on_hand
    fault = services.record_fault(
        wine=wine,
        user=sommelier,
        fault_type=WineFault.FaultType.CORKED,
        bottles_affected=1,
        description="TCA belirgin",
    )
    wine.refresh_from_db()

    assert wine.bottles_on_hand == before - 1
    assert fault.estimated_loss == Decimal("300.00")


def test_yetersiz_stokta_kusur_kaydi_reddedilir(wine, sommelier) -> None:
    from apps.cellar import services
    from apps.cellar.models import WineFault

    with pytest.raises(services.InsufficientStockError):
        services.record_fault(
            wine=wine,
            user=sommelier,
            fault_type=WineFault.FaultType.BREAKAGE,
            bottles_affected=99,
        )


def test_acik_sisede_oksidasyon_hacmi_sifirlar(wine, sommelier) -> None:
    from apps.cellar import services
    from apps.cellar.models import BottleOpening, WineFault

    opening = services.open_bottle(wine=wine, user=sommelier)
    services.record_fault(
        wine=wine,
        user=sommelier,
        fault_type=WineFault.FaultType.OXIDIZED,
        opening=opening,
        deduct_stock=False,
    )
    opening.refresh_from_db()
    assert opening.status == BottleOpening.Status.DISCARDED
    assert opening.remaining_ml == 0


# ---------------------------------------------------------------------------
# İçim aralığı
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("bugun_yil", "beklenen"),
    [(2021, "too_young"), (2025, "peak"), (2027, "drink_soon"), (2030, "past_peak")],
)
def test_icim_araligi_durumu(wine, bugun_yil: int, beklenen: str) -> None:
    from datetime import date

    assert wine.drink_window_status(date(bugun_yil, 6, 1)) == beklenen


def test_icim_araligi_belirtilmemisse_bilinmiyor(wine) -> None:
    wine.drink_from_year = None
    wine.drink_until_year = None
    wine.peak_year = None
    wine.save()
    assert wine.drink_window_status() == "unknown"


# ---------------------------------------------------------------------------
# Değerleme ve mükerrer kayıt
# ---------------------------------------------------------------------------
def test_kav_degerlemesi_hesaplanir(wine) -> None:
    from apps.cellar import services

    valuation = services.cellar_valuation()
    assert valuation["closed_bottles"] == 10
    assert valuation["cost_value"] == Decimal("3000.00")
    assert valuation["retail_value"] == Decimal("12000.00")
    assert valuation["potential_margin"] == Decimal("9000.00")


def test_ayni_barkod_mukerrer_uyarisi_uretir(wine) -> None:
    from apps.cellar import services
    from apps.cellar.models import Wine, WineDuplicateAlert

    wine.barcode = "8690000000001"
    wine.save()
    Wine.objects.create(
        sku="TEST-002",
        name="Başka Şarap",
        producer=wine.producer,
        region=wine.region,
        vintage=2021,
        wine_type=Wine.WineType.RED,
        barcode="8690000000001",
    )

    alerts = services.detect_duplicates()
    reasons = {alert.reason for alert in alerts}
    assert WineDuplicateAlert.Reason.SAME_BARCODE in reasons


def test_benzer_ad_mukerrer_uyarisi_uretir(wine) -> None:
    from apps.cellar import services
    from apps.cellar.models import Wine, WineDuplicateAlert

    Wine.objects.create(
        sku="TEST-003",
        name="Öküzgözü Test ",  # yalnızca boşluk farkı
        producer=wine.producer,
        region=wine.region,
        vintage=2020,
        bottle_size_ml=375,  # tekillik kısıtını aşmak için farklı hacim
        wine_type=Wine.WineType.RED,
    )
    alerts = services.detect_duplicates()
    assert any(a.reason == WineDuplicateAlert.Reason.SIMILAR_NAME for a in alerts)


def test_fiyat_anomalisi_tespit_edilir(wine) -> None:
    from apps.cellar import services
    from apps.cellar.models import WineDuplicateAlert

    wine.bottle_price = Decimal("100.00")  # alış 300 iken satış 100
    wine.save()
    alerts = services.detect_duplicates(wine=wine)
    assert any(a.reason == WineDuplicateAlert.Reason.PRICE_ANOMALY for a in alerts)


def test_mukerrer_tarama_kayit_silmez(wine) -> None:
    """Tarama hiçbir koşulda veri silmez."""
    from apps.cellar import services
    from apps.cellar.models import Wine

    before = Wine.objects.count()
    services.detect_duplicates()
    assert Wine.objects.count() == before


# ---------------------------------------------------------------------------
# Saklama koşulları
# ---------------------------------------------------------------------------
def test_aralik_disi_sicaklik_uyari_uretir(db) -> None:
    from apps.cellar.models import StorageReading, WineStorageLocation

    location = WineStorageLocation.objects.create(
        code="KAV-T",
        name="Test Raf",
        target_temp_c=Decimal("13.0"),
        temp_tolerance_c=Decimal("2.0"),
        target_humidity_percent=70,
        humidity_tolerance_percent=10,
    )
    uygun = StorageReading.objects.create(
        location=location, temperature_c=Decimal("14.0"), humidity_percent=Decimal("72")
    )
    sapma = StorageReading.objects.create(
        location=location, temperature_c=Decimal("18.5"), humidity_percent=Decimal("72")
    )
    nem_sapmasi = StorageReading.objects.create(
        location=location, temperature_c=Decimal("13.0"), humidity_percent=Decimal("95")
    )

    assert not uygun.has_alert
    assert sapma.is_temperature_out_of_range
    assert nem_sapmasi.is_humidity_out_of_range


def test_kadeh_verimi_hesabi(wine) -> None:
    assert wine.theoretical_glasses_per_bottle == 5
    wine.glass_pour_ml = 125
    assert wine.theoretical_glasses_per_bottle == 6
