"""Salon operasyonu iş mantığı.

Sipariş yaşam döngüsünün mali doğruluğunu koruyan işlemler:

  * ``open_order``       — masaya adisyon açar
  * ``add_line``         — menü fiyatını *dondurarak* satır ekler
  * ``send_to_stations`` — istasyon başına hazırlık fişi (KOT) üretir
  * ``apply_discount``   — yetki sınırını aşarsa onay talebi oluşturur
  * ``split_order_by_seat`` — hesabı koltuk bazında böler
  * ``merge_orders``     — adisyonları birleştirir
  * ``take_payment``     — tahsilat kaydeder (sandbox)
  * ``void_order``       — onaya bağlı iptal
  * ``close_business_day`` — gün sonu özetini dondurur

Tüm yazma işlemleri atomiktir ve denetim kaydı üretir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from apps.accounts.models import ApprovalRequest
from apps.core.audit import record
from apps.core.models import AuditAction, AuditSeverity
from apps.operations.models import (
    BusinessDay,
    DiningTable,
    Order,
    OrderLine,
    Payment,
    PaymentMethod,
    PrepTicket,
    PrepTicketLine,
    Reservation,
)

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")


class OperationsError(RuntimeError):
    """Operasyon iş kuralı ihlali."""


class ApprovalRequiredError(OperationsError):
    """İşlem ikinci onay gerektiriyor; onay talebi oluşturuldu."""

    def __init__(self, message: str, approval: ApprovalRequest) -> None:
        super().__init__(message)
        self.approval = approval


# ---------------------------------------------------------------------------
# Numaralandırma
# ---------------------------------------------------------------------------
def _next_sequence(model: Any, field: str, prefix: str) -> str:
    """``PREFIX-YYYYMMDD-0001`` biçiminde sıra numarası üretir."""
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
# Adisyon açma
# ---------------------------------------------------------------------------
@transaction.atomic
def open_order(
    *,
    user: Any,
    table: DiningTable | None = None,
    channel: str = Order.Channel.DINE_IN,
    guest_count: int = 1,
    customer: Any = None,
    reservation: Reservation | None = None,
    service_charge_percent: Decimal | None = None,
) -> Order:
    """Yeni adisyon açar ve masayı işaretler."""
    if table is not None:
        locked_table = DiningTable.objects.select_for_update().get(pk=table.pk)
        if locked_table.status == DiningTable.Status.OUT_OF_SERVICE:
            raise OperationsError(f"Masa servis dışı: {locked_table}")
        existing = locked_table.orders.filter(status__in=Order.OPEN_STATUSES).first()
        if existing is not None:
            raise OperationsError(
                f"Masada zaten açık adisyon var: {existing.number}. "
                "Yeni sipariş için mevcut adisyona satır ekleyin."
            )
        locked_table.status = DiningTable.Status.SEATED
        locked_table.save(update_fields=["status", "updated_at"])

    order = Order.objects.create(
        number=_next_sequence(Order, "number", "ADS"),
        channel=channel,
        table=table,
        reservation=reservation,
        customer=customer,
        guest_count=max(1, guest_count),
        server=user,
        status=Order.Status.OPEN,
        service_charge_percent=service_charge_percent or Decimal("0.00"),
        created_by=user if getattr(user, "pk", None) else None,
    )

    if reservation is not None:
        reservation.status = Reservation.Status.SEATED
        reservation.seated_at = timezone.now()
        reservation.save(update_fields=["status", "seated_at", "updated_at"])

    record(
        action=AuditAction.CREATE,
        obj=order,
        message=f"Adisyon açıldı: {order.number} · masa={table or '-'} · {guest_count} kişi",
        actor=user,
    )
    return order


# ---------------------------------------------------------------------------
# Satır ekleme
# ---------------------------------------------------------------------------
@transaction.atomic
def add_line(
    *,
    order: Order,
    menu_item: Any,
    user: Any,
    quantity: Decimal | int = 1,
    service_unit: str = OrderLine.ServiceUnit.PORTION,
    seat_number: int | None = None,
    course: int = 1,
    special_instructions: str = "",
    unit_price: Decimal | None = None,
) -> OrderLine:
    """Adisyona satır ekler.

    Fiyat, KDV oranı, maliyet ve ürün adı bu anda **kopyalanır**; menüdeki
    sonraki değişiklikler bu satırı etkilemez.
    """
    if order.status in {Order.Status.PAID, Order.Status.VOID}:
        raise OperationsError(
            f"Kapanmış adisyona satır eklenemez (durum: {order.get_status_display()})."
        )
    if not menu_item.is_active or not menu_item.is_available:
        raise OperationsError(f"'{menu_item.name_tr}' şu anda serviste değil.")

    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise OperationsError("Adet sıfırdan büyük olmalıdır.")

    # Kadeh şarap satışında kadeh fiyatı, şişede şişe fiyatı geçerlidir.
    wine = menu_item.wine
    if unit_price is not None:
        price = Decimal(str(unit_price))
    elif wine is not None and service_unit == OrderLine.ServiceUnit.GLASS:
        price = wine.glass_price or menu_item.effective_price
    elif wine is not None and service_unit == OrderLine.ServiceUnit.BOTTLE:
        price = wine.bottle_price or menu_item.effective_price
    else:
        price = menu_item.effective_price

    line = OrderLine.objects.create(
        order=order,
        menu_item=menu_item,
        wine=wine,
        service_unit=service_unit,
        item_name=menu_item.name_tr,
        quantity=quantity,
        unit_price=price,
        tax_rate=menu_item.tax_rate,
        unit_cost=menu_item.cost_price,
        seat_number=seat_number,
        course=course,
        special_instructions=special_instructions,
        created_by=user if getattr(user, "pk", None) else None,
    )
    order.recalculate()

    if order.table_id and order.table.status == DiningTable.Status.SEATED:
        order.table.status = DiningTable.Status.ORDERED
        order.table.save(update_fields=["status", "updated_at"])

    return line


@transaction.atomic
def void_line(*, line: OrderLine, user: Any, reason: str) -> OrderLine:
    """Satırı iptal eder (fiziksel silme yapılmaz)."""
    if line.order.status in {Order.Status.PAID, Order.Status.VOID}:
        raise OperationsError("Kapanmış adisyonun satırı iptal edilemez.")
    if not reason.strip():
        raise OperationsError("İptal gerekçesi zorunludur.")

    line.is_voided = True
    line.void_reason = reason.strip()[:200]
    line.save(update_fields=["is_voided", "void_reason", "updated_at"])
    line.order.recalculate()

    record(
        action=AuditAction.VOID,
        obj=line,
        message=f"Satır iptal edildi: {line.item_name} × {line.quantity:g} · gerekçe: {reason}",
        severity=AuditSeverity.NOTICE,
        actor=user,
    )
    return line


# ---------------------------------------------------------------------------
# Mutfağa gönderme (KOT / KDS)
# ---------------------------------------------------------------------------
STATION_BY_PREPARATION = {
    "kitchen": PrepTicket.Station.KITCHEN,
    "bar": PrepTicket.Station.BAR,
    "wine": PrepTicket.Station.WINE,
}


@transaction.atomic
def send_to_stations(*, order: Order, user: Any) -> list[PrepTicket]:
    """Gönderilmemiş satırlardan istasyon başına hazırlık fişi üretir.

    Yemek satırları mutfak (KDS), içecekler bar, şaraplar sommelier
    ekranına düşer.
    """
    pending = list(
        order.lines.filter(is_voided=False, sent_at__isnull=True).select_related(
            "menu_item", "menu_item__category", "wine"
        )
    )
    if not pending:
        return []

    grouped: dict[tuple[str, int], list[OrderLine]] = {}
    for line in pending:
        station_key = line.menu_item.category.preparation_station
        if line.service_unit in {
            OrderLine.ServiceUnit.GLASS,
            OrderLine.ServiceUnit.BOTTLE,
            OrderLine.ServiceUnit.FLIGHT,
        }:
            station_key = "wine"
        if station_key == "none":
            line.sent_at = timezone.now()
            line.save(update_fields=["sent_at", "updated_at"])
            continue
        station = STATION_BY_PREPARATION.get(station_key, PrepTicket.Station.KITCHEN)
        grouped.setdefault((station, line.course), []).append(line)

    tickets: list[PrepTicket] = []
    now = timezone.now()

    for (station, course), lines in grouped.items():
        target = max((line.menu_item.preparation_minutes for line in lines), default=15) or 15
        ticket = PrepTicket.objects.create(
            order=order,
            ticket_number=_next_sequence(PrepTicket, "ticket_number", "KOT"),
            station=station,
            course=course,
            status=PrepTicket.Status.QUEUED,
            sent_at=now,
            target_minutes=target,
            created_by=user if getattr(user, "pk", None) else None,
        )
        for line in lines:
            allergens = ", ".join(allergen.name_tr for allergen in line.menu_item.allergens.all())
            PrepTicketLine.objects.create(
                ticket=ticket,
                order_line=line,
                item_name=line.item_name,
                quantity=line.quantity,
                special_instructions=line.special_instructions,
                allergen_warning=allergens,
            )
            line.sent_at = now
            line.save(update_fields=["sent_at", "updated_at"])
        tickets.append(ticket)

    if order.status == Order.Status.OPEN:
        order.status = Order.Status.SENT
        order.save(update_fields=["status", "updated_at"])

    record(
        action=AuditAction.UPDATE,
        obj=order,
        message=f"{len(tickets)} hazırlık fişi üretildi: {order.number}",
        actor=user,
    )
    return tickets


@transaction.atomic
def bump_ticket(*, ticket: PrepTicket, user: Any, target_status: str = "") -> PrepTicket:
    """Fişi bir sonraki duruma ilerletir (KDS 'bump' hareketi)."""
    flow = {
        PrepTicket.Status.QUEUED: PrepTicket.Status.PREPARING,
        PrepTicket.Status.PREPARING: PrepTicket.Status.READY,
        PrepTicket.Status.READY: PrepTicket.Status.SERVED,
    }
    new_status = target_status or flow.get(PrepTicket.Status(ticket.status))
    if new_status is None:
        raise OperationsError("Fiş zaten son durumda.")

    ticket.status = new_status
    now = timezone.now()
    fields = ["status", "updated_at"]

    if new_status == PrepTicket.Status.PREPARING:
        ticket.started_at = now
        ticket.prepared_by = user if getattr(user, "pk", None) else None
        fields += ["started_at", "prepared_by"]
    elif new_status == PrepTicket.Status.READY:
        ticket.ready_at = now
        fields.append("ready_at")
    elif new_status == PrepTicket.Status.SERVED:
        ticket.served_at = now
        fields.append("served_at")
        ticket.lines.update(is_done=True)
        for ticket_line in ticket.lines.select_related("order_line"):
            ticket_line.order_line.served_at = now
            ticket_line.order_line.save(update_fields=["served_at", "updated_at"])

    ticket.save(update_fields=fields)

    order = ticket.order
    if (
        new_status == PrepTicket.Status.SERVED
        and not order.tickets.exclude(
            status__in=[PrepTicket.Status.SERVED, PrepTicket.Status.CANCELLED]
        ).exists()
    ):
        order.status = Order.Status.SERVED
        order.save(update_fields=["status", "updated_at"])
        if order.table_id:
            order.table.status = DiningTable.Status.SERVED
            order.table.save(update_fields=["status", "updated_at"])

    return ticket


# ---------------------------------------------------------------------------
# İndirim ve ikram
# ---------------------------------------------------------------------------
@transaction.atomic
def apply_discount(
    *,
    line: OrderLine,
    user: Any,
    percent: Decimal,
    reason: str,
    is_comp: bool = False,
    approval: ApprovalRequest | None = None,
) -> OrderLine:
    """Satıra indirim veya ikram uygular.

    Kullanıcının ``discount_limit_percent`` değerini aşan indirimler ve tüm
    ikramlar ikinci onay gerektirir. Onay yoksa ``ApprovalRequiredError``
    yükseltilir ve **indirim uygulanmaz**.
    """
    percent = Decimal(str(percent))
    if percent < 0 or percent > 100:
        raise OperationsError("İndirim oranı 0-100 aralığında olmalıdır.")
    if not reason.strip():
        raise OperationsError("İndirim gerekçesi zorunludur.")

    limit = Decimal(str(getattr(user, "discount_limit_percent", 0) or 0))
    action_code = "comp_item" if is_comp else "discount_over_limit"
    needs_approval = is_comp or percent > limit

    if needs_approval and approval is None and not user.is_superuser:
        if user.can_approve(action_code):
            needs_approval = False
        else:
            request = ApprovalRequest.objects.create(
                action=action_code,
                requested_by=user,
                reason=reason.strip(),
                payload={
                    "order_line_id": line.pk,
                    "percent": str(percent),
                    "is_comp": is_comp,
                },
                object_type=line._meta.label,
                object_id=str(line.pk),
                expires_at=timezone.now() + timezone.timedelta(hours=8),
                created_by=user,
            )
            record(
                action=AuditAction.DISCOUNT,
                obj=line,
                message=(
                    f"İndirim onaya gönderildi: %{percent} · {line.item_name} · "
                    f"yetki sınırı %{limit}"
                ),
                severity=AuditSeverity.NOTICE,
                success=False,
                actor=user,
            )
            raise ApprovalRequiredError(
                f"%{percent} indirim yetki sınırınızı (%{limit}) aşıyor. "
                "Onay talebi oluşturuldu; onaylandıktan sonra uygulanacaktır.",
                request,
            )

    if approval is not None:
        if approval.status != ApprovalRequest.Status.APPROVED:
            raise OperationsError("Onay talebi henüz onaylanmadı.")
        approval.mark_applied()
        line.discount_approval = approval

    line.discount_percent = Decimal("0.00") if is_comp else percent
    line.is_comp = is_comp
    line.discount_reason = reason.strip()[:200]
    line.save(
        update_fields=[
            "discount_percent",
            "is_comp",
            "discount_reason",
            "discount_approval",
            "updated_at",
        ]
    )
    line.order.recalculate()

    record(
        action=AuditAction.DISCOUNT,
        obj=line,
        message=(
            f"{'İkram' if is_comp else f'%{percent} indirim'} uygulandı: "
            f"{line.item_name} · gerekçe: {reason}"
        ),
        severity=AuditSeverity.NOTICE,
        actor=user,
    )
    return line


# ---------------------------------------------------------------------------
# Hesap bölme ve birleştirme
# ---------------------------------------------------------------------------
@dataclass
class SplitResult:
    """Hesap bölme sonucu."""

    source: Order
    created: list[Order]


@transaction.atomic
def split_order_by_seat(*, order: Order, user: Any) -> SplitResult:
    """Adisyonu koltuk numarasına göre ayrı adisyonlara böler.

    Koltuk numarası atanmamış satırlar kaynak adisyonda kalır.
    """
    if order.status in {Order.Status.PAID, Order.Status.VOID}:
        raise OperationsError("Kapanmış adisyon bölünemez.")
    if order.payments.filter(is_voided=False).exists():
        raise OperationsError("Kısmi ödeme alınmış adisyon bölünemez. Önce ödemeleri iptal edin.")

    seats = (
        order.lines.filter(is_voided=False, seat_number__isnull=False)
        .values_list("seat_number", flat=True)
        .distinct()
    )
    seat_numbers = sorted(set(seats))
    if not seat_numbers:
        raise OperationsError("Bölme için satırlara koltuk numarası atanmalıdır.")

    created: list[Order] = []
    for seat in seat_numbers:
        child = Order.objects.create(
            number=_next_sequence(Order, "number", "ADS"),
            channel=order.channel,
            table=order.table,
            reservation=order.reservation,
            customer=order.customer,
            guest_count=1,
            server=order.server,
            status=Order.Status.BILLED,
            service_charge_percent=order.service_charge_percent,
            parent_order=order,
            created_by=user if getattr(user, "pk", None) else None,
        )
        order.lines.filter(is_voided=False, seat_number=seat).update(order=child)
        child.recalculate()
        created.append(child)

    order.recalculate()

    record(
        action=AuditAction.UPDATE,
        obj=order,
        message=f"Hesap {len(created)} parçaya bölündü: {order.number}",
        severity=AuditSeverity.NOTICE,
        actor=user,
    )
    return SplitResult(source=order, created=created)


@transaction.atomic
def merge_orders(*, target: Order, sources: list[Order], user: Any) -> Order:
    """Birden çok adisyonu tek adisyonda birleştirir."""
    if target.status in {Order.Status.PAID, Order.Status.VOID}:
        raise OperationsError("Kapanmış adisyona birleştirme yapılamaz.")

    merged: list[Order] = []
    for source in sources:
        if source.pk == target.pk:
            continue
        if source.status in {Order.Status.PAID, Order.Status.VOID}:
            raise OperationsError(f"{source.number} kapanmış; birleştirilemez.")
        if source.payments.filter(is_voided=False).exists():
            raise OperationsError(f"{source.number} için ödeme alınmış; birleştirilemez.")

        source.lines.update(order=target)
        source.tickets.update(order=target)
        source.merged_into = target
        source.status = Order.Status.VOID
        source.void_reason = f"{target.number} adisyonuna birleştirildi."
        source.closed_at = timezone.now()
        source.save(
            update_fields=["merged_into", "status", "void_reason", "closed_at", "updated_at"]
        )
        target.guest_count += source.guest_count
        merged.append(source)

    target.save(update_fields=["guest_count", "updated_at"])
    target.recalculate()

    record(
        action=AuditAction.UPDATE,
        obj=target,
        message=(
            f"{len(merged)} adisyon birleştirildi → {target.number} "
            f"({', '.join(source.number for source in merged)})"
        ),
        severity=AuditSeverity.NOTICE,
        actor=user,
    )
    return target


# ---------------------------------------------------------------------------
# Ödeme
# ---------------------------------------------------------------------------
@transaction.atomic
def take_payment(
    *,
    order: Order,
    method: PaymentMethod,
    amount: Decimal,
    user: Any,
    tip_amount: Decimal | None = None,
    reference: str = "",
    split_label: str = "",
) -> Payment:
    """Tahsilat kaydeder.

    UYARI: Bu sürümde gerçek ödeme ağ geçidi bağlı değildir. Kayıt her zaman
    ``sandbox`` modunda oluşturulur ve hiçbir gerçek para hareketi olmaz.
    """
    from django.conf import settings

    if order.status == Order.Status.VOID:
        raise OperationsError("İptal edilmiş adisyona ödeme alınamaz.")

    amount = Decimal(str(amount)).quantize(TWO_PLACES)
    if amount <= 0:
        raise OperationsError("Ödeme tutarı sıfırdan büyük olmalıdır.")

    order.recalculate()
    if amount > order.amount_due + TWO_PLACES:
        raise OperationsError(
            f"Ödeme tutarı ({amount}) kalan borçtan ({order.amount_due}) büyük olamaz."
        )
    if method.requires_reference and not reference.strip():
        raise OperationsError(f"'{method.name}' için referans bilgisi zorunludur.")

    gateway_mode = (
        Payment.GatewayMode.LIVE
        if getattr(settings, "PAYMENT_MODE", "sandbox") == "live"
        else Payment.GatewayMode.SANDBOX
    )

    payment = Payment.objects.create(
        order=order,
        method=method,
        amount=amount,
        tip_amount=Decimal(str(tip_amount or 0)).quantize(TWO_PLACES),
        received_by=user,
        reference=reference.strip()[:100],
        gateway_mode=gateway_mode,
        split_label=split_label[:60],
        created_by=user if getattr(user, "pk", None) else None,
    )

    if order.is_fully_paid:
        order.status = Order.Status.PAID
        order.closed_at = timezone.now()
        order.save(update_fields=["status", "closed_at", "updated_at"])
        if order.table_id:
            table = order.table
            if not table.orders.filter(status__in=Order.OPEN_STATUSES).exists():
                table.status = DiningTable.Status.CLEANING
                table.save(update_fields=["status", "updated_at"])
        if order.reservation_id:
            order.reservation.status = Reservation.Status.COMPLETED
            order.reservation.save(update_fields=["status", "updated_at"])

    record(
        action=AuditAction.PAYMENT,
        obj=payment,
        message=(
            f"Tahsilat: {order.number} · {method.name} · {amount} "
            f"({payment.get_gateway_mode_display()})"
        ),
        changes={"kalan_borç": str(order.amount_due)},
        actor=user,
    )
    return payment


@transaction.atomic
def void_order(
    *, order: Order, user: Any, reason: str, approval: ApprovalRequest | None = None
) -> Order:
    """Adisyonu iptal eder. Yetkisi olmayan kullanıcı için onay talebi üretir."""
    if not reason.strip():
        raise OperationsError("İptal gerekçesi zorunludur.")
    if order.status == Order.Status.VOID:
        raise OperationsError("Adisyon zaten iptal edilmiş.")

    if approval is None and not user.can_approve("void_order"):
        request = ApprovalRequest.objects.create(
            action="void_order",
            requested_by=user,
            reason=reason.strip(),
            payload={"order_id": order.pk, "order_number": order.number},
            object_type=order._meta.label,
            object_id=str(order.pk),
            expires_at=timezone.now() + timezone.timedelta(hours=8),
            created_by=user,
        )
        raise ApprovalRequiredError(
            "Adisyon iptali yönetici onayı gerektirir. Onay talebi oluşturuldu.",
            request,
        )

    if approval is not None:
        if approval.status != ApprovalRequest.Status.APPROVED:
            raise OperationsError("Onay talebi henüz onaylanmadı.")
        approval.mark_applied()
        order.void_approval = approval

    order.status = Order.Status.VOID
    order.void_reason = reason.strip()[:250]
    order.closed_at = timezone.now()
    order.save(update_fields=["status", "void_reason", "closed_at", "void_approval", "updated_at"])
    order.tickets.exclude(status=PrepTicket.Status.SERVED).update(
        status=PrepTicket.Status.CANCELLED
    )

    if order.table_id and not order.table.orders.filter(status__in=Order.OPEN_STATUSES).exists():
        order.table.status = DiningTable.Status.FREE
        order.table.save(update_fields=["status", "updated_at"])

    record(
        action=AuditAction.VOID,
        obj=order,
        message=f"Adisyon iptal edildi: {order.number} · gerekçe: {reason}",
        severity=AuditSeverity.WARNING,
        actor=user,
    )
    return order


# ---------------------------------------------------------------------------
# Rezervasyon çakışma denetimi
# ---------------------------------------------------------------------------
def find_reservation_conflicts(reservation: Reservation, table_ids: list[int]) -> list[Reservation]:
    """Verilen masalar için zaman çakışması olan rezervasyonları döndürür.

    İki rezervasyon aynı masayı, zaman aralıkları kesişecek biçimde
    kullanamaz.
    """
    if not table_ids:
        return []

    window_start = reservation.reserved_for
    window_end = reservation.ends_at

    candidates = (
        Reservation.objects.filter(
            tables__in=table_ids,
            status__in=[
                Reservation.Status.PENDING,
                Reservation.Status.CONFIRMED,
                Reservation.Status.SEATED,
            ],
            is_deleted=False,
            reserved_for__lt=window_end,
        )
        .exclude(pk=reservation.pk or 0)
        .distinct()
    )
    return [other for other in candidates if other.ends_at > window_start]


@transaction.atomic
def assign_tables(*, reservation: Reservation, tables: list[DiningTable], user: Any) -> Reservation:
    """Rezervasyona masa atar; çakışma varsa reddeder."""
    conflicts = find_reservation_conflicts(reservation, [table.pk for table in tables])
    if conflicts:
        detail = ", ".join(
            f"{other.code} ({other.reserved_for:%d.%m %H:%M})" for other in conflicts
        )
        raise OperationsError(f"Masa çakışması: {detail}")

    capacity = sum(table.seats for table in tables)
    if capacity < reservation.guest_count:
        raise OperationsError(
            f"Seçilen masaların kapasitesi ({capacity}) misafir sayısından "
            f"({reservation.guest_count}) az."
        )

    reservation.tables.set(tables)
    for table in tables:
        if table.status == DiningTable.Status.FREE:
            table.status = DiningTable.Status.RESERVED
            table.save(update_fields=["status", "updated_at"])

    record(
        action=AuditAction.UPDATE,
        obj=reservation,
        message=f"Masa atandı: {reservation.code} → {', '.join(str(t) for t in tables)}",
        actor=user,
    )
    return reservation


# ---------------------------------------------------------------------------
# Gün sonu
# ---------------------------------------------------------------------------
@transaction.atomic
def close_business_day(
    *, business_day: BusinessDay, user: Any, cash_counted: Decimal
) -> BusinessDay:
    """Gün sonu kapanışını yapar ve özeti dondurur.

    Açık adisyon varsa kapanış reddedilir; böylece eksik hesap gün sonuna
    karışmaz.
    """
    if business_day.status == BusinessDay.Status.CLOSED:
        raise OperationsError("Gün zaten kapatılmış.")

    open_orders = Order.objects.filter(
        status__in=Order.OPEN_STATUSES,
        opened_at__date=business_day.business_date,
        is_deleted=False,
    )
    if open_orders.exists():
        numbers = ", ".join(open_orders.values_list("number", flat=True)[:10])
        raise OperationsError(f"Kapanmamış adisyonlar var: {numbers}. Önce hepsini kapatın.")

    paid = Order.objects.filter(
        status=Order.Status.PAID, opened_at__date=business_day.business_date, is_deleted=False
    )
    aggregates = paid.aggregate(
        orders=Count("id"),
        guests=Sum("guest_count"),
        gross=Sum("subtotal"),
        discounts=Sum("discount_total"),
        tax=Sum("tax_total"),
        total=Sum("grand_total"),
    )

    payments = (
        Payment.objects.filter(order__in=paid, is_voided=False)
        .values("method__code", "method__name", "method__kind")
        .annotate(total=Sum("amount"), count=Count("id"))
    )
    breakdown = {
        row["method__code"]: {
            "name": row["method__name"],
            "kind": row["method__kind"],
            "total": str(row["total"] or Decimal("0.00")),
            "count": row["count"],
        }
        for row in payments
    }
    cash_expected = sum(
        (Decimal(entry["total"]) for entry in breakdown.values() if entry["kind"] == "cash"),
        Decimal("0.00"),
    )

    business_day.total_orders = aggregates["orders"] or 0
    business_day.total_guests = aggregates["guests"] or 0
    business_day.gross_sales = aggregates["gross"] or Decimal("0.00")
    business_day.discounts = aggregates["discounts"] or Decimal("0.00")
    business_day.tax_collected = aggregates["tax"] or Decimal("0.00")
    business_day.net_sales = (aggregates["total"] or Decimal("0.00")) - business_day.tax_collected
    business_day.cash_expected = cash_expected
    business_day.cash_counted = Decimal(str(cash_counted)).quantize(TWO_PLACES)
    business_day.payment_breakdown = breakdown
    business_day.status = BusinessDay.Status.CLOSED
    business_day.closed_at = timezone.now()
    business_day.closed_by = user
    business_day.save()

    _write_daily_snapshot(business_day, paid)

    record(
        action=AuditAction.SETTINGS,
        obj=business_day,
        message=(
            f"Gün sonu kapatıldı: {business_day.business_date:%d.%m.%Y} · "
            f"{business_day.total_orders} adisyon · net {business_day.net_sales} · "
            f"kasa farkı {business_day.cash_variance}"
        ),
        severity=(
            AuditSeverity.WARNING
            if abs(business_day.cash_variance) > Decimal("1.00")
            else AuditSeverity.NOTICE
        ),
        actor=user,
    )
    return business_day


def _write_daily_snapshot(business_day: BusinessDay, paid_orders: Any) -> None:
    """Gün sonu özetini raporlama tablosuna dondurur."""
    from apps.reporting.models import DailySalesSnapshot

    lines = OrderLine.objects.filter(order__in=paid_orders, is_voided=False).select_related(
        "menu_item", "wine"
    )

    food = Decimal("0.00")
    beverage = Decimal("0.00")
    wine_bottle = Decimal("0.00")
    wine_glass = Decimal("0.00")
    cost = Decimal("0.00")
    comps = Decimal("0.00")
    bottles = 0
    glasses = 0

    for line in lines:
        total = line.total_amount
        cost += line.cost_amount
        if line.is_comp:
            comps += line.gross_amount
        if line.service_unit == OrderLine.ServiceUnit.BOTTLE:
            wine_bottle += total
            bottles += int(line.quantity)
        elif line.service_unit == OrderLine.ServiceUnit.GLASS:
            wine_glass += total
            glasses += int(line.quantity)
        elif line.menu_item.item_type == "drink":
            beverage += total
        else:
            food += total

    voided = Order.objects.filter(
        status=Order.Status.VOID, opened_at__date=business_day.business_date
    ).aggregate(count=Count("id"), total=Sum("grand_total"))

    reservations = Reservation.objects.filter(
        reserved_for__date=business_day.business_date, is_deleted=False
    )
    active_tables = DiningTable.objects.filter(is_active=True).count() or 1

    DailySalesSnapshot.objects.update_or_create(
        business_date=business_day.business_date,
        defaults={
            "order_count": business_day.total_orders,
            "guest_count": business_day.total_guests,
            "gross_sales": business_day.gross_sales,
            "discounts": business_day.discounts,
            "comps": comps,
            "service_charge": paid_orders.aggregate(total=Sum("service_charge"))["total"]
            or Decimal("0.00"),
            "tax": business_day.tax_collected,
            "net_sales": business_day.net_sales,
            "cost_of_sales": cost,
            "food_sales": food,
            "beverage_sales": beverage,
            "wine_bottle_sales": wine_bottle,
            "wine_glass_sales": wine_glass,
            "bottles_sold": bottles,
            "glasses_sold": glasses,
            "void_count": voided["count"] or 0,
            "void_amount": voided["total"] or Decimal("0.00"),
            "table_turns": (Decimal(business_day.total_orders) / Decimal(active_tables)).quantize(
                TWO_PLACES
            ),
            "reservation_count": reservations.count(),
            "no_show_count": reservations.filter(status=Reservation.Status.NO_SHOW).count(),
            "payment_breakdown": business_day.payment_breakdown,
        },
    )


def get_or_open_business_day(user: Any, business_date: Any = None) -> BusinessDay:
    """Bugünün iş gününü döndürür; yoksa açar."""
    target = business_date or timezone.localdate()
    day, _created = BusinessDay.objects.get_or_create(
        business_date=target,
        defaults={"opened_by": user, "created_by": user if getattr(user, "pk", None) else None},
    )
    return day
