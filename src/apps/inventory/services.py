"""Stok ve satın alma iş mantığı.

Stok bakiyesi her zaman ``StockMovement`` kayıtlarının toplamıyla
doğrulanabilir olmalıdır. Bu nedenle miktar değiştiren her işlem hem partiyi
günceller hem de değiştirilemez bir hareket kaydı yazar.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.audit import record
from apps.core.models import AuditAction, AuditSeverity
from apps.inventory.models import (
    GoodsReceipt,
    PurchaseRequest,
    StockCount,
    StockItem,
    StockLot,
    StockMovement,
    Warehouse,
)

logger = logging.getLogger(__name__)

FOUR_PLACES = Decimal("0.0001")
TWO_PLACES = Decimal("0.01")


class InventoryError(RuntimeError):
    """Stok iş kuralı ihlali."""


class InsufficientStockError(InventoryError):
    """Yeterli stok yok."""


def next_document_number(model: Any, field: str, prefix: str) -> str:
    """``PREFIX-YYYYMMDD-0001`` biçiminde belge numarası üretir."""
    today = timezone.localdate()
    stem = f"{prefix}-{today:%Y%m%d}-"
    last = (
        model.objects.filter(**{f"{field}__startswith": stem})
        .order_by(f"-{field}")
        .values_list(field, flat=True)
        .first()
    )
    counter = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{stem}{counter:04d}"


# ---------------------------------------------------------------------------
# FIFO / FEFO çıkış
# ---------------------------------------------------------------------------
def select_lots_for_consumption(
    *, stock_item: StockItem, warehouse: Warehouse, quantity: Decimal
) -> list[tuple[StockLot, Decimal]]:
    """Tüketilecek partileri sırayla seçer.

    ``FEFO`` modunda önce son kullanma tarihi en yakın parti, ``FIFO``
    modunda önce en eski girişli parti tüketilir.

    Returns:
        ``[(parti, tüketilecek_miktar), …]``

    Raises:
        InsufficientStockError: Toplam stok yetmiyorsa.
    """
    ordering = (
        ["expires_on", "received_on", "id"]
        if stock_item.tracking_mode == StockItem.TrackingMode.FEFO
        else ["received_on", "id"]
    )
    lots = (
        StockLot.objects.select_for_update()
        .filter(
            stock_item=stock_item,
            warehouse=warehouse,
            is_deleted=False,
            quantity_remaining__gt=0,
        )
        .order_by(*ordering)
    )

    remaining = Decimal(str(quantity))
    plan: list[tuple[StockLot, Decimal]] = []

    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot.quantity_remaining, remaining)
        plan.append((lot, take))
        remaining -= take

    if remaining > 0:
        available = sum((lot.quantity_remaining for lot in lots), Decimal("0"))
        raise InsufficientStockError(
            f"'{stock_item.name}' için yeterli stok yok. "
            f"İstenen: {quantity}, mevcut: {available} {stock_item.unit.code}."
        )
    return plan


@transaction.atomic
def consume_stock(
    *,
    stock_item: StockItem,
    warehouse: Warehouse,
    quantity: Decimal,
    movement_type: str,
    user: Any,
    reference_type: str = "",
    reference_id: str = "",
    note: str = "",
) -> list[StockMovement]:
    """Stoktan çıkış yapar (FIFO/FEFO) ve hareket kaydı yazar."""
    plan = select_lots_for_consumption(
        stock_item=stock_item, warehouse=warehouse, quantity=Decimal(str(quantity))
    )
    movements: list[StockMovement] = []

    for lot, take in plan:
        lot.quantity_remaining = (lot.quantity_remaining - take).quantize(FOUR_PLACES)
        lot.save(update_fields=["quantity_remaining", "updated_at"])
        movements.append(
            StockMovement.objects.create(
                stock_item=stock_item,
                lot=lot,
                warehouse=warehouse,
                movement_type=movement_type,
                quantity=-take,
                unit_cost=lot.unit_cost,
                performed_by=user if getattr(user, "pk", None) else None,
                reference_type=reference_type,
                reference_id=reference_id,
                note=note[:250],
            )
        )
    return movements


@transaction.atomic
def receive_stock(
    *,
    stock_item: StockItem,
    warehouse: Warehouse,
    quantity: Decimal,
    unit_cost: Decimal,
    user: Any,
    lot_code: str = "",
    expires_on: Any = None,
    supplier: Any = None,
    movement_type: str = StockMovement.MovementType.RECEIPT,
    reference_type: str = "",
    reference_id: str = "",
) -> tuple[StockLot, StockMovement]:
    """Stoğa giriş yapar; parti oluşturur veya var olana ekler."""
    quantity = Decimal(str(quantity)).quantize(FOUR_PLACES)
    if quantity <= 0:
        raise InventoryError("Giriş miktarı sıfırdan büyük olmalıdır.")

    code = lot_code or next_document_number(StockLot, "lot_code", "PRT")
    if not expires_on and stock_item.shelf_life_days:
        expires_on = timezone.localdate() + timezone.timedelta(days=stock_item.shelf_life_days)

    lot, created = StockLot.objects.get_or_create(
        stock_item=stock_item,
        warehouse=warehouse,
        lot_code=code,
        defaults={
            "supplier": supplier,
            "expires_on": expires_on,
            "quantity_received": quantity,
            "quantity_remaining": quantity,
            "unit_cost": Decimal(str(unit_cost)).quantize(FOUR_PLACES),
        },
    )
    if not created:
        lot.quantity_received = (lot.quantity_received + quantity).quantize(FOUR_PLACES)
        lot.quantity_remaining = (lot.quantity_remaining + quantity).quantize(FOUR_PLACES)
        lot.save(update_fields=["quantity_received", "quantity_remaining", "updated_at"])

    movement = StockMovement.objects.create(
        stock_item=stock_item,
        lot=lot,
        warehouse=warehouse,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost=lot.unit_cost,
        performed_by=user if getattr(user, "pk", None) else None,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    return lot, movement


# ---------------------------------------------------------------------------
# Mal kabul
# ---------------------------------------------------------------------------
@transaction.atomic
def post_goods_receipt(*, receipt: GoodsReceipt, user: Any) -> list[StockLot]:
    """Mal kabul satırlarını stoğa işler."""
    lines = list(receipt.lines.select_related("stock_item", "order_line"))
    if not lines:
        raise InventoryError("Mal kabulde satır yok.")
    if any(line.lot_id for line in lines):
        raise InventoryError("Bu mal kabul zaten stoğa işlenmiş.")

    created: list[StockLot] = []
    for line in lines:
        accepted = line.quantity - line.rejected_quantity
        if accepted <= 0:
            continue
        lot, _movement = receive_stock(
            stock_item=line.stock_item,
            warehouse=receipt.warehouse,
            quantity=accepted,
            unit_cost=line.unit_cost,
            user=user,
            lot_code=line.lot_code or "",
            expires_on=line.expires_on,
            supplier=receipt.supplier,
            reference_type="inventory.GoodsReceipt",
            reference_id=str(receipt.pk),
        )
        line.lot = lot
        line.save(update_fields=["lot", "updated_at"])
        created.append(lot)

        if line.order_line_id:
            order_line = line.order_line
            order_line.quantity_received = (order_line.quantity_received + accepted).quantize(
                FOUR_PLACES
            )
            order_line.save(update_fields=["quantity_received", "updated_at"])

    if receipt.order_id:
        order = receipt.order
        order.status = order.Status.RECEIVED if order.is_fully_received else order.Status.PARTIAL
        order.save(update_fields=["status", "updated_at"])

    record(
        action=AuditAction.IMPORT,
        obj=receipt,
        message=f"Mal kabul stoğa işlendi: {receipt.number} · {len(created)} parti",
        actor=user,
    )
    return created


# ---------------------------------------------------------------------------
# Sayım
# ---------------------------------------------------------------------------
@transaction.atomic
def post_stock_count(*, count: StockCount, user: Any) -> list[StockMovement]:
    """Sayım farklarını düzeltme hareketi olarak işler."""
    if count.status == StockCount.Status.POSTED:
        raise InventoryError("Sayım zaten muhasebeleştirilmiş.")

    movements: list[StockMovement] = []
    for line in count.lines.select_related("stock_item"):
        variance = line.variance
        if variance == 0:
            continue

        if variance > 0:
            _lot, movement = receive_stock(
                stock_item=line.stock_item,
                warehouse=count.warehouse,
                quantity=variance,
                unit_cost=line.unit_cost or line.stock_item.average_unit_cost,
                user=user,
                movement_type=StockMovement.MovementType.COUNT_ADJUST,
                reference_type="inventory.StockCount",
                reference_id=str(count.pk),
            )
            movements.append(movement)
        else:
            movements.extend(
                consume_stock(
                    stock_item=line.stock_item,
                    warehouse=count.warehouse,
                    quantity=abs(variance),
                    movement_type=StockMovement.MovementType.COUNT_ADJUST,
                    user=user,
                    reference_type="inventory.StockCount",
                    reference_id=str(count.pk),
                    note="Sayım eksiği",
                )
            )

    count.status = StockCount.Status.POSTED
    count.save(update_fields=["status", "updated_at"])

    record(
        action=AuditAction.STOCK_ADJUST,
        obj=count,
        message=(
            f"Sayım muhasebeleştirildi: {count.number} · {len(movements)} hareket · "
            f"fark değeri {count.total_variance_value}"
        ),
        severity=AuditSeverity.NOTICE,
        actor=user,
    )
    return movements


# ---------------------------------------------------------------------------
# Fire
# ---------------------------------------------------------------------------
@transaction.atomic
def record_wastage(
    *,
    stock_item: StockItem,
    warehouse: Warehouse,
    quantity: Decimal,
    reason: str,
    user: Any,
    description: str = "",
) -> Any:
    """Fire kaydeder ve stoktan düşer."""
    from apps.inventory.models import WastageEntry

    quantity = Decimal(str(quantity))
    unit_cost = stock_item.average_unit_cost
    estimated = (quantity * unit_cost).quantize(TWO_PLACES)

    consume_stock(
        stock_item=stock_item,
        warehouse=warehouse,
        quantity=quantity,
        movement_type=StockMovement.MovementType.WASTE,
        user=user,
        reference_type="inventory.WastageEntry",
        note=f"Fire: {reason}",
    )

    entry = WastageEntry.objects.create(
        stock_item=stock_item,
        warehouse=warehouse,
        quantity=quantity,
        reason=reason,
        recorded_by=user,
        estimated_cost=estimated,
        description=description,
    )

    record(
        action=AuditAction.WASTE,
        obj=entry,
        message=(
            f"Fire kaydı: {stock_item.name} · {quantity} {stock_item.unit.code} · "
            f"gerekçe={entry.get_reason_display()} · maliyet {estimated}"
        ),
        severity=AuditSeverity.NOTICE,
        actor=user,
    )
    return entry


# ---------------------------------------------------------------------------
# Öneriler ve uyarılar
# ---------------------------------------------------------------------------
def build_reorder_suggestions(limit: int = 100) -> list[dict[str, Any]]:
    """Minimum seviyenin altındaki kalemler için sipariş önerisi üretir.

    Bu bir *öneridir*; hiçbir satın alma siparişi kendiliğinden oluşturulmaz.
    """
    suggestions: list[dict[str, Any]] = []
    items = (
        StockItem.objects.filter(is_active=True, is_deleted=False, minimum_quantity__gt=0)
        .select_related("unit", "default_supplier")
        .prefetch_related("lots")
    )

    for item in items:
        on_hand = item.quantity_on_hand
        if on_hand >= item.minimum_quantity:
            continue
        shortfall = item.minimum_quantity - on_hand
        order_quantity = max(shortfall, item.reorder_quantity or shortfall)
        suggestions.append(
            {
                "stock_item_id": item.pk,
                "code": item.code,
                "name": item.name,
                "unit": item.unit.code,
                "on_hand": str(on_hand),
                "minimum": str(item.minimum_quantity),
                "shortfall": str(shortfall),
                "suggested_quantity": str(order_quantity),
                "estimated_cost": str(
                    (order_quantity * item.average_unit_cost).quantize(TWO_PLACES)
                ),
                "supplier": item.default_supplier.name if item.default_supplier_id else None,
                "lead_time_days": (
                    item.default_supplier.lead_time_days if item.default_supplier_id else None
                ),
            }
        )
        if len(suggestions) >= limit:
            break

    suggestions.sort(key=lambda row: Decimal(row["shortfall"]), reverse=True)
    return suggestions


def expiring_lots(*, days: int = 7, limit: int = 100) -> list[StockLot]:
    """Son kullanma tarihi yaklaşan veya geçmiş partileri döndürür."""
    deadline = timezone.localdate() + timezone.timedelta(days=days)
    return list(
        StockLot.objects.filter(
            is_deleted=False,
            quantity_remaining__gt=0,
            expires_on__isnull=False,
            expires_on__lte=deadline,
        )
        .select_related("stock_item", "warehouse")
        .order_by("expires_on")[:limit]
    )


def compare_quotations(request: PurchaseRequest) -> dict[str, Any]:
    """Talebe gelen teklifleri karşılaştırır.

    En düşük tutar ve en kısa teslim süresi ayrı ayrı işaretlenir; karar
    kullanıcıya bırakılır.
    """
    quotations = list(request.quotations.select_related("supplier").order_by("total_amount"))
    if not quotations:
        return {"request": request.number, "quotations": [], "recommendation": None}

    cheapest = min(quotations, key=lambda quote: quote.total_amount)
    fastest = min(quotations, key=lambda quote: quote.delivery_days)

    return {
        "request": request.number,
        "quotations": [
            {
                "id": quote.pk,
                "supplier": quote.supplier.name,
                "total_amount": str(quote.total_amount),
                "delivery_days": quote.delivery_days,
                "valid_until": quote.valid_until,
                "is_cheapest": quote.pk == cheapest.pk,
                "is_fastest": quote.pk == fastest.pk,
                "is_selected": quote.is_selected,
            }
            for quote in quotations
        ],
        "recommendation": {
            "cheapest_supplier": cheapest.supplier.name,
            "cheapest_amount": str(cheapest.total_amount),
            "fastest_supplier": fastest.supplier.name,
            "fastest_days": fastest.delivery_days,
            "note": "Seçim kullanıcıya aittir; sistem otomatik sipariş oluşturmaz.",
        },
    }


def stock_valuation(warehouse: Warehouse | None = None) -> dict[str, Any]:
    """Stok değerlemesi."""
    lots = StockLot.objects.filter(is_deleted=False, quantity_remaining__gt=0).select_related(
        "stock_item", "stock_item__category"
    )
    if warehouse is not None:
        lots = lots.filter(warehouse=warehouse)

    by_category: dict[str, Decimal] = {}
    total = Decimal("0.00")
    for lot in lots:
        value = (lot.quantity_remaining * lot.unit_cost).quantize(TWO_PLACES)
        total += value
        key = lot.stock_item.category.name
        by_category[key] = by_category.get(key, Decimal("0.00")) + value

    return {
        "total_value": total.quantize(TWO_PLACES),
        "lot_count": lots.count(),
        "by_category": {key: str(value) for key, value in sorted(by_category.items())},
    }
