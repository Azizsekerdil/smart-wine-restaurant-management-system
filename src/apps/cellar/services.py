"""Şarap kavı iş mantığı.

Bu modül kavın *mali doğruluğunu* koruyan işlemleri içerir:

  * ``open_bottle``   — FEFO sırasına göre partiden şişe düşer
  * ``pour_glass``    — açık şişeden kadeh servis eder ve hacmi azaltır
  * ``finish_bottle`` — kalan hacmi fire olarak kapatır
  * ``record_fault``  — kusurlu şişeyi stoktan düşer ve kaybı hesaplar
  * ``detect_duplicates`` — mükerrer/şüpheli kayıt uyarısı üretir

Tüm işlemler tek bir veritabanı işleminde (atomic) yürütülür; kısmi
güncelleme oluşmaz.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.cellar.models import (
    BottleLot,
    BottleOpening,
    PouringRecord,
    Wine,
    WineDuplicateAlert,
    WineFault,
)
from apps.core.audit import record
from apps.core.models import AuditAction, AuditSeverity

logger = logging.getLogger(__name__)


class CellarError(RuntimeError):
    """Kav işlemlerinde iş kuralı ihlali."""


class InsufficientStockError(CellarError):
    """Yeterli şişe veya hacim yok."""


# ---------------------------------------------------------------------------
# Şişe açma
# ---------------------------------------------------------------------------
def select_lot_fefo(wine: Wine) -> BottleLot:
    """FEFO/FIFO sırasına göre kullanılacak partiyi seçer.

    Öncelik: en erken tüketilmesi gereken (``best_before``), yoksa en eski
    girişli parti. Böylece kavda en uzun bekleyen şişe önce servis edilir.
    """
    lot = (
        BottleLot.objects.filter(wine=wine, is_deleted=False, bottles_remaining__gt=0)
        .order_by("best_before", "received_on", "id")
        .first()
    )
    if lot is None:
        raise InsufficientStockError(f"'{wine}' için stokta kapalı şişe kalmadı.")
    return lot


@transaction.atomic
def open_bottle(
    *,
    wine: Wine,
    user: Any,
    lot: BottleLot | None = None,
    service_method: str = BottleOpening.ServiceMethod.STANDARD,
    freshness_hours: int | None = None,
    note: str = "",
) -> BottleOpening:
    """Bir şişe açar ve stoktan düşer.

    Args:
        wine: Açılacak şarap.
        user: İşlemi yapan kullanıcı.
        lot: Belirli bir parti zorlanmak isteniyorsa; boşsa FEFO seçilir.
        service_method: Servis yöntemi (koruma sistemi tazelik süresini etkiler).
        freshness_hours: Özel tazelik süresi; boşsa yönteme göre belirlenir.

    Returns:
        Oluşturulan ``BottleOpening``.

    Raises:
        InsufficientStockError: Kapalı şişe kalmadıysa.
    """
    selected = lot or select_lot_fefo(wine)

    # Yarış koşulunu önlemek için satırı kilitle
    locked = BottleLot.objects.select_for_update().get(pk=selected.pk)
    if locked.bottles_remaining < 1:
        raise InsufficientStockError(f"'{wine}' partisi {locked.lot_code} tükendi.")

    locked.bottles_remaining -= 1
    locked.save(update_fields=["bottles_remaining", "updated_at"])

    default_freshness = {
        BottleOpening.ServiceMethod.STANDARD: 48,
        BottleOpening.ServiceMethod.PRESERVATION: 168,  # ~1 hafta (argon/vakum)
        BottleOpening.ServiceMethod.CORAVIN: 720,  # ~30 gün (iğne sistemi)
        BottleOpening.ServiceMethod.TASTING: 24,
    }

    opening = BottleOpening.objects.create(
        wine=wine,
        lot=locked,
        opened_by=user if getattr(user, "pk", None) else None,
        service_method=service_method,
        initial_ml=wine.bottle_size_ml,
        remaining_ml=wine.bottle_size_ml,
        status=BottleOpening.Status.OPEN,
        freshness_hours=(
            freshness_hours
            if freshness_hours is not None
            else default_freshness.get(service_method, 48)
        ),
        notes=note,
    )

    record(
        action=AuditAction.STOCK_ADJUST,
        obj=opening,
        message=(
            f"Şişe açıldı: {wine} · parti={locked.lot_code} · "
            f"yöntem={opening.get_service_method_display()}"
        ),
        changes={"kalan_şişe": [locked.bottles_remaining + 1, locked.bottles_remaining]},
        actor=user,
    )
    return opening


# ---------------------------------------------------------------------------
# Kadeh servisi
# ---------------------------------------------------------------------------
@dataclass
class PourResult:
    """Kadeh servisi sonucu."""

    pour: PouringRecord
    opening: BottleOpening
    opened_new_bottle: bool = False

    @property
    def remaining_glasses(self) -> int:
        return self.opening.glasses_remaining


def find_open_bottle(wine: Wine, *, required_ml: int) -> BottleOpening | None:
    """Yeterli hacmi olan açık şişeyi bulur (en eski açılan önce)."""
    return (
        BottleOpening.objects.filter(
            wine=wine, status=BottleOpening.Status.OPEN, remaining_ml__gte=required_ml
        )
        .order_by("opened_at")
        .first()
    )


@transaction.atomic
def pour_glass(
    *,
    wine: Wine,
    user: Any,
    volume_ml: int | None = None,
    pour_type: str = PouringRecord.PourType.GLASS_SALE,
    order_line: Any = None,
    auto_open: bool = True,
    note: str = "",
) -> PourResult:
    """Kadeh servis eder ve açık şişenin hacmini azaltır.

    Akış:
      1. Yeterli hacimli açık şişe aranır.
      2. Yoksa ve ``auto_open`` açıksa yeni bir şişe açılır (stoktan düşer).
      3. Hacim azaltılır ve ``PouringRecord`` yazılır.
      4. Şişe tükendiyse ``FINISHED`` olarak işaretlenir.

    Bu, kabul senaryosu #9'un ("kadeh satışı açılmış şişe miktarından doğru
    düşer") karşılığıdır.

    Raises:
        InsufficientStockError: Ne açık şişe ne de kapalı şişe varsa.
        CellarError: İstenen hacim şişe hacminden büyükse.
    """
    pour_volume = int(volume_ml or wine.glass_pour_ml or 150)
    if pour_volume <= 0:
        raise CellarError("Servis hacmi sıfırdan büyük olmalıdır.")
    if pour_volume > wine.bottle_size_ml:
        raise CellarError(
            f"İstenen hacim ({pour_volume} ml) şişe hacminden ({wine.bottle_size_ml} ml) büyük."
        )

    opening = find_open_bottle(wine, required_ml=pour_volume)
    opened_new = False

    if opening is None:
        if not auto_open:
            raise InsufficientStockError(f"'{wine}' için yeterli hacimde açık şişe yok.")
        opening = open_bottle(wine=wine, user=user)
        opened_new = True

    locked = BottleOpening.objects.select_for_update().get(pk=opening.pk)
    if locked.remaining_ml < pour_volume:
        raise InsufficientStockError(
            f"Açık şişede yalnızca {locked.remaining_ml} ml kaldı; "
            f"{pour_volume} ml servis edilemez."
        )

    previous_ml = locked.remaining_ml
    locked.remaining_ml -= pour_volume
    if locked.remaining_ml < (wine.glass_pour_ml or 150) // 3:
        # Kalan miktar bir yudumdan az: şişe bitmiş sayılır
        locked.status = BottleOpening.Status.FINISHED
        locked.closed_at = timezone.now()
    locked.save(update_fields=["remaining_ml", "status", "closed_at", "updated_at"])

    pour = PouringRecord.objects.create(
        opening=locked,
        pour_type=pour_type,
        volume_ml=pour_volume,
        poured_by=user if getattr(user, "pk", None) else None,
        order_line=order_line,
        note=note,
    )

    record(
        action=AuditAction.STOCK_ADJUST,
        obj=pour,
        message=(
            f"Kadeh servisi: {wine} · {pour_volume} ml · " f"tür={pour.get_pour_type_display()}"
        ),
        changes={"kalan_ml": [previous_ml, locked.remaining_ml]},
        severity=(
            AuditSeverity.NOTICE
            if pour_type in {PouringRecord.PourType.SPILLAGE, PouringRecord.PourType.WASTE}
            else AuditSeverity.INFO
        ),
        actor=user,
    )

    return PourResult(pour=pour, opening=locked, opened_new_bottle=opened_new)


@transaction.atomic
def finish_bottle(
    *, opening: BottleOpening, user: Any, as_waste: bool = True, note: str = ""
) -> BottleOpening:
    """Açık şişeyi kapatır; kalan hacmi fire olarak kaydeder."""
    locked = BottleOpening.objects.select_for_update().get(pk=opening.pk)
    if locked.status != BottleOpening.Status.OPEN:
        raise CellarError("Şişe zaten kapalı.")

    remaining = locked.remaining_ml
    if remaining > 0 and as_waste:
        PouringRecord.objects.create(
            opening=locked,
            pour_type=PouringRecord.PourType.WASTE,
            volume_ml=remaining,
            poured_by=user if getattr(user, "pk", None) else None,
            note=note or "Şişe kapatıldı; kalan hacim fire yazıldı.",
        )

    locked.remaining_ml = 0
    locked.status = (
        BottleOpening.Status.DISCARDED
        if as_waste and remaining > 0
        else BottleOpening.Status.FINISHED
    )
    locked.closed_at = timezone.now()
    locked.save(update_fields=["remaining_ml", "status", "closed_at", "updated_at"])

    record(
        action=AuditAction.WASTE if as_waste and remaining else AuditAction.UPDATE,
        obj=locked,
        message=f"Açık şişe kapatıldı: {locked.wine} · kalan {remaining} ml",
        severity=AuditSeverity.NOTICE if remaining else AuditSeverity.INFO,
        actor=user,
    )
    return locked


# ---------------------------------------------------------------------------
# Kusur kaydı
# ---------------------------------------------------------------------------
@transaction.atomic
def record_fault(
    *,
    wine: Wine,
    user: Any,
    fault_type: str,
    bottles_affected: int = 1,
    lot: BottleLot | None = None,
    opening: BottleOpening | None = None,
    volume_lost_ml: int = 0,
    description: str = "",
    deduct_stock: bool = True,
) -> WineFault:
    """Şarap kusuru kaydeder ve gerekiyorsa stoktan düşer."""
    unit_cost = Decimal("0.00")
    selected_lot = lot

    if deduct_stock and opening is None and bottles_affected > 0:
        selected_lot = lot or select_lot_fefo(wine)
        locked = BottleLot.objects.select_for_update().get(pk=selected_lot.pk)
        if locked.bottles_remaining < bottles_affected:
            raise InsufficientStockError(
                f"Partide yalnızca {locked.bottles_remaining} şişe var; "
                f"{bottles_affected} şişe düşülemez."
            )
        locked.bottles_remaining -= bottles_affected
        locked.save(update_fields=["bottles_remaining", "updated_at"])
        unit_cost = locked.unit_cost
        selected_lot = locked
    elif selected_lot is not None:
        unit_cost = selected_lot.unit_cost
    else:
        unit_cost = wine.purchase_price or Decimal("0.00")

    if opening is not None:
        locked_opening = BottleOpening.objects.select_for_update().get(pk=opening.pk)
        lost = min(volume_lost_ml or locked_opening.remaining_ml, locked_opening.remaining_ml)
        locked_opening.remaining_ml -= lost
        locked_opening.status = BottleOpening.Status.DISCARDED
        locked_opening.closed_at = timezone.now()
        locked_opening.save(update_fields=["remaining_ml", "status", "closed_at", "updated_at"])
        volume_lost_ml = lost
        estimated_loss = (
            unit_cost * Decimal(lost) / Decimal(max(1, wine.bottle_size_ml))
        ).quantize(Decimal("0.01"))
    else:
        estimated_loss = (unit_cost * bottles_affected).quantize(Decimal("0.01"))

    fault = WineFault.objects.create(
        wine=wine,
        lot=selected_lot,
        opening=opening,
        fault_type=fault_type,
        detected_by=user if getattr(user, "pk", None) else None,
        bottles_affected=bottles_affected,
        volume_lost_ml=volume_lost_ml,
        estimated_loss=estimated_loss,
        description=description,
    )

    record(
        action=AuditAction.WASTE,
        obj=fault,
        message=(
            f"Şarap kusuru: {wine} · {fault.get_fault_type_display()} · "
            f"{bottles_affected} şişe · tahmini kayıp {estimated_loss}"
        ),
        severity=AuditSeverity.WARNING,
        actor=user,
    )
    return fault


# ---------------------------------------------------------------------------
# Mükerrer / şüpheli kayıt tespiti
# ---------------------------------------------------------------------------
def _normalize(text: str) -> str:
    """Karşılaştırma için metni sadeleştirir."""
    import re
    import unicodedata

    lowered = (text or "").casefold()
    stripped = "".join(
        char for char in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "", stripped)


def _similarity(left: str, right: str) -> float:
    """0.0–1.0 arası benzerlik oranı."""
    from difflib import SequenceMatcher

    return SequenceMatcher(None, left, right).ratio()


def detect_duplicates(
    *, wine: Wine | None = None, threshold: float = 0.92
) -> list[WineDuplicateAlert]:
    """Mükerrer veya şüpheli şarap kayıtlarını tespit eder.

    Sistem hiçbir kaydı **kendiliğinden silmez veya birleştirmez**; yalnızca
    inceleme için uyarı üretir.

    Kontroller:
      * Aynı barkod farklı kayıtlarda
      * Aynı üretici + çok benzer ad + aynı rekolte
      * Mantıksız rekolte (gelecek yıl / çok eski)
      * Fiyat anomalisi (satış fiyatı alış fiyatının altında)
    """
    candidates = (
        [wine] if wine is not None else list(Wine.objects.filter(is_deleted=False, is_active=True))
    )
    alerts: list[WineDuplicateAlert] = []
    current_year = timezone.localdate().year

    for candidate in candidates:
        if candidate is None:
            continue

        # 1) Barkod çakışması
        if candidate.barcode:
            clash = (
                Wine.objects.filter(barcode=candidate.barcode, is_deleted=False)
                .exclude(pk=candidate.pk)
                .first()
            )
            if clash:
                alerts.append(
                    _upsert_alert(
                        candidate,
                        clash,
                        WineDuplicateAlert.Reason.SAME_BARCODE,
                        f"Aynı barkod başka bir kayıtta da tanımlı: {candidate.barcode}",
                        Decimal("0.99"),
                    )
                )

        # 2) Aynı üretici + benzer ad + aynı rekolte
        siblings = (
            Wine.objects.filter(producer=candidate.producer, is_deleted=False)
            .exclude(pk=candidate.pk)
            .filter(Q(vintage=candidate.vintage) | Q(vintage__isnull=True))
        )
        normalized = _normalize(candidate.name)
        for sibling in siblings[:50]:
            ratio = _similarity(normalized, _normalize(sibling.name))
            if ratio >= threshold:
                alerts.append(
                    _upsert_alert(
                        candidate,
                        sibling,
                        WineDuplicateAlert.Reason.SIMILAR_NAME,
                        (
                            f"'{candidate.name}' ile '{sibling.name}' çok benzer "
                            f"(benzerlik %{ratio * 100:.0f}), aynı üretici ve rekolte."
                        ),
                        Decimal(str(round(ratio, 2))),
                    )
                )

        # 3) Mantıksız rekolte
        if candidate.vintage and (
            candidate.vintage > current_year or candidate.vintage < current_year - 120
        ):
            alerts.append(
                _upsert_alert(
                    candidate,
                    None,
                    WineDuplicateAlert.Reason.IMPLAUSIBLE_VINTAGE,
                    f"Rekolte değeri şüpheli: {candidate.vintage}",
                    Decimal("0.85"),
                )
            )

        # 4) Fiyat anomalisi
        if (
            candidate.bottle_price
            and candidate.purchase_price
            and candidate.bottle_price < candidate.purchase_price
        ):
            alerts.append(
                _upsert_alert(
                    candidate,
                    None,
                    WineDuplicateAlert.Reason.PRICE_ANOMALY,
                    (
                        f"Satış fiyatı ({candidate.bottle_price}) alış fiyatının "
                        f"({candidate.purchase_price}) altında."
                    ),
                    Decimal("0.90"),
                )
            )

    return [alert for alert in alerts if alert is not None]


def _upsert_alert(
    wine: Wine,
    other: Wine | None,
    reason: str,
    detail: str,
    confidence: Decimal,
) -> WineDuplicateAlert:
    """Uyarıyı oluşturur veya var olanı günceller (kopya uyarı üretmez)."""
    alert, _created = WineDuplicateAlert.objects.update_or_create(
        wine=wine,
        other_wine=other,
        reason=reason,
        defaults={"detail": detail, "confidence": confidence},
    )
    return alert


# ---------------------------------------------------------------------------
# Değerleme ve uyarılar
# ---------------------------------------------------------------------------
def cellar_valuation() -> dict[str, Any]:
    """Kavın toplam değerlemesini hesaplar.

    Özel kav müşterilerine ait şişeler **dahil edilmez** (işletme mülkiyeti
    değildir).
    """
    lots = BottleLot.objects.filter(is_deleted=False, bottles_remaining__gt=0).select_related(
        "wine"
    )
    total_bottles = 0
    cost_value = Decimal("0.00")
    retail_value = Decimal("0.00")

    for lot in lots:
        total_bottles += lot.bottles_remaining
        cost_value += lot.bottles_remaining * lot.unit_cost
        retail_value += lot.bottles_remaining * (lot.wine.bottle_price or Decimal("0.00"))

    open_value = Decimal("0.00")
    for opening in BottleOpening.objects.filter(status=BottleOpening.Status.OPEN).select_related(
        "wine"
    ):
        share = Decimal(opening.remaining_ml) / Decimal(max(1, opening.initial_ml))
        open_value += share * (opening.wine.purchase_price or Decimal("0.00"))

    return {
        "closed_bottles": total_bottles,
        "cost_value": cost_value.quantize(Decimal("0.01")),
        "retail_value": retail_value.quantize(Decimal("0.01")),
        "open_bottle_value": open_value.quantize(Decimal("0.01")),
        "potential_margin": (retail_value - cost_value).quantize(Decimal("0.01")),
    }


def drink_window_alerts(limit: int = 50) -> list[dict[str, Any]]:
    """İçim aralığı yaklaşan veya geçen şarapları listeler."""
    alerts: list[dict[str, Any]] = []
    for wine in Wine.objects.filter(is_deleted=False, is_active=True).select_related("producer")[
        :500
    ]:
        status = wine.drink_window_status()
        if status in {"drink_soon", "past_peak", "peak"} and wine.bottles_on_hand > 0:
            alerts.append(
                {
                    "wine": wine,
                    "status": status,
                    "label": wine.drink_window_label(),
                    "bottles": wine.bottles_on_hand,
                    "value": wine.stock_value,
                }
            )
    priority = {"past_peak": 0, "drink_soon": 1, "peak": 2}
    alerts.sort(key=lambda item: (priority.get(item["status"], 9), -item["bottles"]))
    return alerts[:limit]
