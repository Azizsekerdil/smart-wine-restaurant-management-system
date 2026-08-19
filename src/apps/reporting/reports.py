"""Rapor üreteçleri ve kayıt defteri.

Her rapor bir ``ReportTable`` döndürür; dışa aktarım katmanı (PDF/Excel/CSV)
bu ortak yapıyı kullanır. Böylece her rapor üç biçimde de aynı veriyi verir.

Yeni rapor eklemek için ``@register`` dekoratörünü kullanın::

    @register("gunluk-satis", category="sales", name_tr="Günlük satış")
    def daily_sales(params: ReportParams) -> ReportTable:
        ...
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, F, Sum
from django.utils import timezone

from apps.reporting.exporters import ReportTable

logger = logging.getLogger(__name__)


@dataclass
class ReportParams:
    """Rapor parametreleri."""

    start_date: date
    end_date: date
    language: str = "tr"
    limit: int = 200
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def period_label(self) -> str:
        if self.start_date == self.end_date:
            return f"{self.start_date:%d.%m.%Y}"
        return f"{self.start_date:%d.%m.%Y} – {self.end_date:%d.%m.%Y}"


@dataclass(frozen=True)
class ReportSpec:
    """Kayıtlı rapor tanımı."""

    code: str
    name_tr: str
    name_en: str
    category: str
    generator: Callable[[ReportParams], ReportTable]
    permission: str = ""
    is_experimental: bool = False
    description: str = ""


REGISTRY: dict[str, ReportSpec] = {}


def register(
    code: str,
    *,
    name_tr: str,
    name_en: str,
    category: str,
    permission: str = "",
    is_experimental: bool = False,
    description: str = "",
) -> Callable:
    """Rapor üretecini kayıt defterine ekler."""

    def decorator(func: Callable[[ReportParams], ReportTable]) -> Callable:
        REGISTRY[code] = ReportSpec(
            code=code,
            name_tr=name_tr,
            name_en=name_en,
            category=category,
            generator=func,
            permission=permission,
            is_experimental=is_experimental,
            description=description,
        )
        return func

    return decorator


def get_report(code: str) -> ReportSpec:
    """Kayıtlı raporu döndürür."""
    if code not in REGISTRY:
        raise KeyError(f"Bilinmeyen rapor: {code}. Tanımlı raporlar: {', '.join(sorted(REGISTRY))}")
    return REGISTRY[code]


def available_reports(user: Any) -> list[ReportSpec]:
    """Kullanıcının görebileceği raporlar."""
    result = []
    for spec in REGISTRY.values():
        if spec.permission and not (user.has_perm(spec.permission) or user.is_superuser):
            continue
        result.append(spec)
    return sorted(result, key=lambda spec: (spec.category, spec.name_tr))


# ===========================================================================
# SATIŞ RAPORLARI
# ===========================================================================
@register(
    "gunluk-satis",
    name_tr="Günlük satış özeti",
    name_en="Daily sales summary",
    category="sales",
    permission="reporting.view_dailysalessnapshot",
    description="Gün sonu kapanışında dondurulan günlük satış verileri.",
)
def daily_sales(params: ReportParams) -> ReportTable:
    """Günlük satış özetlerini listeler."""
    from apps.reporting.models import DailySalesSnapshot

    snapshots = DailySalesSnapshot.objects.filter(
        business_date__gte=params.start_date, business_date__lte=params.end_date
    ).order_by("business_date")

    rows: list[list[Any]] = []
    totals = {
        "orders": 0,
        "guests": 0,
        "net": Decimal("0.00"),
        "cost": Decimal("0.00"),
        "wine": Decimal("0.00"),
    }

    for snapshot in snapshots:
        wine_total = snapshot.wine_bottle_sales + snapshot.wine_glass_sales
        rows.append(
            [
                snapshot.business_date,
                snapshot.order_count,
                snapshot.guest_count,
                snapshot.net_sales,
                snapshot.average_check,
                snapshot.average_per_guest,
                wine_total,
                snapshot.wine_share_percent,
                snapshot.gross_margin_percent,
            ]
        )
        totals["orders"] += snapshot.order_count
        totals["guests"] += snapshot.guest_count
        totals["net"] += snapshot.net_sales
        totals["cost"] += snapshot.cost_of_sales
        totals["wine"] += wine_total

    average_check = (
        (totals["net"] / totals["orders"]).quantize(Decimal("0.01"))
        if totals["orders"]
        else Decimal("0.00")
    )
    average_guest = (
        (totals["net"] / totals["guests"]).quantize(Decimal("0.01"))
        if totals["guests"]
        else Decimal("0.00")
    )
    margin = (
        ((totals["net"] - totals["cost"]) / totals["net"] * 100).quantize(Decimal("0.01"))
        if totals["net"]
        else Decimal("0.00")
    )
    wine_share = (
        (totals["wine"] / totals["net"] * 100).quantize(Decimal("0.01"))
        if totals["net"]
        else Decimal("0.00")
    )

    return ReportTable(
        title="Günlük Satış Özeti",
        subtitle=f"Dönem: {params.period_label}",
        columns=[
            "Tarih",
            "Adisyon",
            "Misafir",
            "Net satış",
            "Ort. adisyon",
            "Kişi başı",
            "Şarap satışı",
            "Şarap payı %",
            "Brüt marj %",
        ],
        rows=rows,
        totals=[
            "TOPLAM",
            totals["orders"],
            totals["guests"],
            totals["net"],
            average_check,
            average_guest,
            totals["wine"],
            wine_share,
            margin,
        ],
    )


@register(
    "urun-satis",
    name_tr="Ürün ve kategori satışları",
    name_en="Product and category sales",
    category="product",
    permission="reporting.view_reportdefinition",
)
def product_sales(params: ReportParams) -> ReportTable:
    """Menü ürünü bazında satış adedi ve tutarı."""
    from apps.operations.models import Order, OrderLine

    lines = (
        OrderLine.objects.filter(
            is_voided=False,
            order__status=Order.Status.PAID,
            order__opened_at__date__gte=params.start_date,
            order__opened_at__date__lte=params.end_date,
        )
        .values(
            "menu_item__code",
            "menu_item__name_tr",
            "menu_item__category__name_tr",
            "menu_item__item_type",
        )
        .annotate(qty=Sum("quantity"), gross=Sum(F("quantity") * F("unit_price")))
        .order_by("-gross")[: params.limit]
    )

    rows = [
        [
            row["menu_item__code"],
            row["menu_item__name_tr"],
            row["menu_item__category__name_tr"],
            row["qty"] or Decimal("0"),
            row["gross"] or Decimal("0.00"),
        ]
        for row in lines
    ]
    total_gross = sum((row[4] for row in rows), Decimal("0.00"))
    total_quantity = sum((row[3] for row in rows), Decimal("0"))

    return ReportTable(
        title="Ürün ve Kategori Satışları",
        subtitle=f"Dönem: {params.period_label}",
        columns=["Kod", "Ürün", "Kategori", "Adet", "Tutar"],
        rows=rows,
        totals=["TOPLAM", "", "", total_quantity, total_gross],
    )


@register(
    "odeme-dagilimi",
    name_tr="Ödeme yöntemi dağılımı",
    name_en="Payment method breakdown",
    category="finance",
    permission="reporting.can_view_financial_report",
)
def payment_breakdown(params: ReportParams) -> ReportTable:
    """Ödeme yöntemlerine göre tahsilat dağılımı."""
    from apps.operations.models import Payment

    payments = (
        Payment.objects.filter(
            is_voided=False,
            received_at__date__gte=params.start_date,
            received_at__date__lte=params.end_date,
        )
        .values("method__name", "method__kind", "method__commission_percent")
        .annotate(total=Sum("amount"), tips=Sum("tip_amount"), count=Count("id"))
        .order_by("-total")
    )

    rows: list[list[Any]] = []
    grand_total = Decimal("0.00")
    grand_commission = Decimal("0.00")

    for row in payments:
        amount = row["total"] or Decimal("0.00")
        commission = (amount * (row["method__commission_percent"] or 0) / 100).quantize(
            Decimal("0.01")
        )
        grand_total += amount
        grand_commission += commission
        rows.append(
            [
                row["method__name"],
                row["count"],
                amount,
                row["tips"] or Decimal("0.00"),
                commission,
                (amount - commission).quantize(Decimal("0.01")),
            ]
        )

    return ReportTable(
        title="Ödeme Yöntemi Dağılımı",
        subtitle=f"Dönem: {params.period_label}",
        columns=["Yöntem", "İşlem", "Tutar", "Bahşiş", "Komisyon", "Net"],
        rows=rows,
        totals=[
            "TOPLAM",
            sum(row[1] for row in rows),
            grand_total,
            sum((row[3] for row in rows), Decimal("0.00")),
            grand_commission,
            (grand_total - grand_commission).quantize(Decimal("0.01")),
        ],
    )


# ===========================================================================
# ŞARAP RAPORLARI
# ===========================================================================
@register(
    "sarap-karlilik",
    name_tr="Şarap kârlılığı",
    name_en="Wine profitability",
    category="wine",
    permission="cellar.can_view_cellar_valuation",
)
def wine_profitability(params: ReportParams) -> ReportTable:
    """Şarap bazında satış, maliyet ve marj."""
    from apps.operations.models import Order, OrderLine

    lines = (
        OrderLine.objects.filter(
            is_voided=False,
            wine__isnull=False,
            order__status=Order.Status.PAID,
            order__opened_at__date__gte=params.start_date,
            order__opened_at__date__lte=params.end_date,
        )
        .values(
            "wine__id",
            "wine__name",
            "wine__producer__name",
            "wine__vintage",
            "service_unit",
        )
        .annotate(qty=Sum("quantity"), revenue=Sum(F("quantity") * F("unit_price")))
    )

    aggregated: dict[int, dict[str, Any]] = {}
    for row in lines:
        key = row["wine__id"]
        entry = aggregated.setdefault(
            key,
            {
                "name": row["wine__name"],
                "producer": row["wine__producer__name"],
                "vintage": row["wine__vintage"] or "NV",
                "bottles": Decimal("0"),
                "glasses": Decimal("0"),
                "revenue": Decimal("0.00"),
            },
        )
        entry["revenue"] += row["revenue"] or Decimal("0.00")
        if row["service_unit"] == "bottle":
            entry["bottles"] += row["qty"] or Decimal("0")
        elif row["service_unit"] == "glass":
            entry["glasses"] += row["qty"] or Decimal("0")

    from apps.cellar.models import Wine

    wine_costs = {wine.pk: wine for wine in Wine.objects.filter(pk__in=aggregated.keys())}

    rows: list[list[Any]] = []
    for wine_id, entry in aggregated.items():
        wine = wine_costs.get(wine_id)
        unit_cost = wine.purchase_price if wine else Decimal("0.00")
        pour = (wine.glass_pour_ml or 150) if wine else 150
        size = (wine.bottle_size_ml or 750) if wine else 750
        glass_cost = (unit_cost * Decimal(pour) / Decimal(size)).quantize(Decimal("0.01"))
        cost = (entry["bottles"] * unit_cost + entry["glasses"] * glass_cost).quantize(
            Decimal("0.01")
        )
        margin = entry["revenue"] - cost
        margin_percent = (
            (margin / entry["revenue"] * 100).quantize(Decimal("0.01"))
            if entry["revenue"]
            else Decimal("0.00")
        )
        rows.append(
            [
                entry["producer"],
                entry["name"],
                entry["vintage"],
                entry["bottles"],
                entry["glasses"],
                entry["revenue"],
                cost,
                margin,
                margin_percent,
            ]
        )

    rows.sort(key=lambda row: row[7], reverse=True)
    rows = rows[: params.limit]

    return ReportTable(
        title="Şarap Kârlılığı",
        subtitle=f"Dönem: {params.period_label}",
        columns=[
            "Üretici",
            "Şarap",
            "Rekolte",
            "Şişe",
            "Kadeh",
            "Ciro",
            "Maliyet",
            "Kâr",
            "Marj %",
        ],
        rows=rows,
        totals=[
            "TOPLAM",
            "",
            "",
            sum((row[3] for row in rows), Decimal("0")),
            sum((row[4] for row in rows), Decimal("0")),
            sum((row[5] for row in rows), Decimal("0.00")),
            sum((row[6] for row in rows), Decimal("0.00")),
            sum((row[7] for row in rows), Decimal("0.00")),
            "",
        ],
    )


@register(
    "kadeh-sise-karsilastirma",
    name_tr="Kadeh / şişe satış karşılaştırması",
    name_en="Glass vs bottle comparison",
    category="wine",
    permission="cellar.view_wine",
)
def glass_vs_bottle(params: ReportParams) -> ReportTable:
    """Kadeh ve şişe satışlarının karşılaştırması ve gerçekleşen verim."""
    from apps.cellar.models import BottleOpening, PouringRecord

    openings = (
        BottleOpening.objects.filter(
            opened_at__date__gte=params.start_date, opened_at__date__lte=params.end_date
        )
        .select_related("wine")
        .prefetch_related("pours")
    )

    rows: list[list[Any]] = []
    for opening in openings[: params.limit]:
        sale_ml = sum(
            pour.volume_ml
            for pour in opening.pours.all()
            if pour.pour_type == PouringRecord.PourType.GLASS_SALE
        )
        waste_ml = sum(
            pour.volume_ml
            for pour in opening.pours.all()
            if pour.pour_type in {PouringRecord.PourType.SPILLAGE, PouringRecord.PourType.WASTE}
        )
        expected = opening.wine.theoretical_glasses_per_bottle
        actual = opening.glasses_poured
        rows.append(
            [
                opening.wine.name,
                opening.wine.display_vintage,
                opening.get_service_method_display(),
                opening.opened_at.date(),
                expected,
                actual,
                sale_ml,
                waste_ml,
                opening.yield_percent,
                opening.get_status_display(),
            ]
        )

    return ReportTable(
        title="Kadeh / Şişe Satış Karşılaştırması",
        subtitle=(
            f"Dönem: {params.period_label} · "
            "Beklenen kadeh sayısı ile gerçekleşen arasındaki fark dökülme veya "
            "ölçüsüz servisi işaret eder."
        ),
        columns=[
            "Şarap",
            "Rekolte",
            "Yöntem",
            "Açılış",
            "Beklenen kadeh",
            "Gerçekleşen",
            "Satılan ml",
            "Fire ml",
            "Verim %",
            "Durum",
        ],
        rows=rows,
    )


@register(
    "kav-degerleme",
    name_tr="Kav stok değerlemesi",
    name_en="Cellar stock valuation",
    category="wine",
    permission="cellar.can_view_cellar_valuation",
)
def cellar_valuation_report(params: ReportParams) -> ReportTable:
    """Kavdaki şişelerin maliyet ve satış değeri."""
    from apps.cellar.models import Wine

    rows: list[list[Any]] = []
    for wine in (
        Wine.objects.filter(is_deleted=False, is_active=True)
        .select_related("producer", "region")
        .prefetch_related("lots")
    ):
        bottles = wine.bottles_on_hand
        if bottles == 0:
            continue
        cost_value = wine.stock_value
        retail_value = (bottles * (wine.bottle_price or Decimal("0.00"))).quantize(Decimal("0.01"))
        rows.append(
            [
                wine.sku,
                wine.producer.name,
                wine.name,
                wine.display_vintage,
                bottles,
                cost_value,
                retail_value,
                (retail_value - cost_value).quantize(Decimal("0.01")),
                str(wine.drink_window_label()),
            ]
        )

    rows.sort(key=lambda row: row[6], reverse=True)
    rows = rows[: params.limit]

    return ReportTable(
        title="Kav Stok Değerlemesi",
        subtitle=(
            f"Rapor tarihi: {timezone.localdate():%d.%m.%Y} · "
            "Özel kav müşterilerine ait şişeler dâhil değildir."
        ),
        columns=[
            "SKU",
            "Üretici",
            "Şarap",
            "Rekolte",
            "Şişe",
            "Maliyet değeri",
            "Satış değeri",
            "Potansiyel kâr",
            "İçim durumu",
        ],
        rows=rows,
        totals=[
            "TOPLAM",
            "",
            "",
            "",
            sum(row[4] for row in rows),
            sum((row[5] for row in rows), Decimal("0.00")),
            sum((row[6] for row in rows), Decimal("0.00")),
            sum((row[7] for row in rows), Decimal("0.00")),
            "",
        ],
    )


# ===========================================================================
# STOK VE FİRE
# ===========================================================================
@register(
    "fire-analizi",
    name_tr="Fire ve israf analizi",
    name_en="Waste analysis",
    category="inventory",
    permission="inventory.view_wastageentry",
)
def waste_analysis(params: ReportParams) -> ReportTable:
    """Fire kayıtlarının gerekçe bazında dağılımı."""
    from apps.inventory.models import WastageEntry

    entries = (
        WastageEntry.objects.filter(
            occurred_at__date__gte=params.start_date, occurred_at__date__lte=params.end_date
        )
        .values("reason")
        .annotate(count=Count("id"), cost=Sum("estimated_cost"))
        .order_by("-cost")
    )

    labels = dict(WastageEntry.Reason.choices)
    rows = [
        [
            str(labels.get(row["reason"], row["reason"])),
            row["count"],
            row["cost"] or Decimal("0.00"),
        ]
        for row in entries
    ]
    total_cost = sum((row[2] for row in rows), Decimal("0.00"))
    for row in rows:
        row.append(
            (row[2] / total_cost * 100).quantize(Decimal("0.01")) if total_cost else Decimal("0.00")
        )

    return ReportTable(
        title="Fire ve İsraf Analizi",
        subtitle=f"Dönem: {params.period_label}",
        columns=["Gerekçe", "Kayıt", "Maliyet", "Pay %"],
        rows=rows,
        totals=["TOPLAM", sum(row[1] for row in rows), total_cost, Decimal("100.00")],
    )


@register(
    "stok-degerleme",
    name_tr="Stok değerlemesi",
    name_en="Stock valuation",
    category="inventory",
    permission="inventory.view_stock_valuation",
)
def stock_valuation_report(params: ReportParams) -> ReportTable:
    """Stok kalemi bazında miktar ve değer."""
    from apps.inventory.models import StockItem

    rows: list[list[Any]] = []
    for item in (
        StockItem.objects.filter(is_active=True, is_deleted=False)
        .select_related("category", "unit")
        .prefetch_related("lots")
    ):
        quantity = item.quantity_on_hand
        if quantity <= 0:
            continue
        rows.append(
            [
                item.code,
                item.name,
                item.category.name,
                quantity,
                item.unit.code,
                item.average_unit_cost,
                item.stock_value,
                "Evet" if item.is_below_minimum else "Hayır",
            ]
        )

    rows.sort(key=lambda row: row[6], reverse=True)
    rows = rows[: params.limit]

    return ReportTable(
        title="Stok Değerlemesi",
        subtitle=f"Rapor tarihi: {timezone.localdate():%d.%m.%Y}",
        columns=[
            "Kod",
            "Kalem",
            "Kategori",
            "Miktar",
            "Birim",
            "Ort. maliyet",
            "Değer",
            "Min. altında",
        ],
        rows=rows,
        totals=["TOPLAM", "", "", "", "", "", sum((row[6] for row in rows), Decimal("0.00")), ""],
    )


# ===========================================================================
# OPERASYON VE PERSONEL
# ===========================================================================
@register(
    "masa-devir",
    name_tr="Masa devir hızı ve doluluk",
    name_en="Table turnover and occupancy",
    category="operations",
    permission="reporting.view_dailysalessnapshot",
)
def table_turnover(params: ReportParams) -> ReportTable:
    """Masa devir hızı, rezervasyon doluluğu ve no-show oranı."""
    from apps.reporting.models import DailySalesSnapshot

    snapshots = DailySalesSnapshot.objects.filter(
        business_date__gte=params.start_date, business_date__lte=params.end_date
    ).order_by("business_date")

    rows = [
        [
            snapshot.business_date,
            snapshot.order_count,
            snapshot.guest_count,
            snapshot.table_turns,
            snapshot.reservation_count,
            snapshot.no_show_count,
            snapshot.no_show_rate,
        ]
        for snapshot in snapshots
    ]

    return ReportTable(
        title="Masa Devir Hızı ve Doluluk",
        subtitle=f"Dönem: {params.period_label}",
        columns=[
            "Tarih",
            "Adisyon",
            "Misafir",
            "Devir hızı",
            "Rezervasyon",
            "Gelmeyen",
            "No-show %",
        ],
        rows=rows,
    )


@register(
    "personel-performans",
    name_tr="Personel performansı",
    name_en="Staff performance",
    category="staff",
    permission="reporting.can_view_staff_report",
)
def staff_performance(params: ReportParams) -> ReportTable:
    """Garson bazında satış ve şarap ekleme oranı."""
    from apps.operations.models import Order

    orders = (
        Order.objects.filter(
            status=Order.Status.PAID,
            is_deleted=False,
            opened_at__date__gte=params.start_date,
            opened_at__date__lte=params.end_date,
        )
        .values("server__id", "server__display_name", "server__username")
        .annotate(
            order_count=Count("id"),
            guests=Sum("guest_count"),
            revenue=Sum("grand_total"),
            average=Avg("grand_total"),
            discounts=Sum("discount_total"),
        )
        .order_by("-revenue")
    )

    from apps.operations.models import OrderLine

    rows: list[list[Any]] = []
    for row in orders:
        server_id = row["server__id"]
        wine_orders = (
            OrderLine.objects.filter(
                order__server_id=server_id,
                order__status=Order.Status.PAID,
                order__opened_at__date__gte=params.start_date,
                order__opened_at__date__lte=params.end_date,
                is_voided=False,
                wine__isnull=False,
            )
            .values("order_id")
            .distinct()
            .count()
        )
        attach_rate = (
            (Decimal(wine_orders) / Decimal(row["order_count"]) * 100).quantize(Decimal("0.01"))
            if row["order_count"]
            else Decimal("0.00")
        )
        rows.append(
            [
                row["server__display_name"] or row["server__username"],
                row["order_count"],
                row["guests"] or 0,
                row["revenue"] or Decimal("0.00"),
                (row["average"] or Decimal("0.00")).quantize(Decimal("0.01")),
                row["discounts"] or Decimal("0.00"),
                wine_orders,
                attach_rate,
            ]
        )

    return ReportTable(
        title="Personel Performansı",
        subtitle=f"Dönem: {params.period_label}",
        columns=[
            "Personel",
            "Adisyon",
            "Misafir",
            "Ciro",
            "Ort. adisyon",
            "İndirim",
            "Şaraplı adisyon",
            "Şarap oranı %",
        ],
        rows=rows,
        totals=[
            "TOPLAM",
            sum(row[1] for row in rows),
            sum(row[2] for row in rows),
            sum((row[3] for row in rows), Decimal("0.00")),
            "",
            sum((row[5] for row in rows), Decimal("0.00")),
            sum(row[6] for row in rows),
            "",
        ],
    )


@register(
    "menu-muhendisligi",
    name_tr="Menü mühendisliği",
    name_en="Menu engineering",
    category="product",
    permission="catalog.view_menu_engineering",
)
def menu_engineering(params: ReportParams) -> ReportTable:
    """Ürünleri popülerlik ve kâr marjına göre kadranlara ayırır.

    Kasavana-Smith yöntemi: ortalama popülerliğin ve ortalama katkı payının
    üstünde/altında olma durumuna göre dört kadran.
    """
    from apps.operations.models import Order, OrderLine

    lines = (
        OrderLine.objects.filter(
            is_voided=False,
            order__status=Order.Status.PAID,
            order__opened_at__date__gte=params.start_date,
            order__opened_at__date__lte=params.end_date,
        )
        .values("menu_item__id", "menu_item__name_tr")
        .annotate(
            qty=Sum("quantity"),
            revenue=Sum(F("quantity") * F("unit_price")),
            cost=Sum(F("quantity") * F("unit_cost")),
        )
    )

    data = list(lines)
    if not data:
        return ReportTable(
            title="Menü Mühendisliği",
            subtitle=f"Dönem: {params.period_label} · Bu dönemde satış verisi yok.",
            columns=["Ürün", "Adet", "Ciro", "Katkı payı", "Popülerlik %", "Kadran"],
            rows=[],
        )

    total_quantity = sum(Decimal(str(row["qty"] or 0)) for row in data)
    contributions = []
    for row in data:
        revenue = row["revenue"] or Decimal("0.00")
        cost = row["cost"] or Decimal("0.00")
        contributions.append(revenue - cost)
    average_contribution = sum(contributions, Decimal("0.00")) / Decimal(len(contributions))
    average_popularity = Decimal("100") / Decimal(len(data)) * Decimal("0.7")  # %70 kuralı

    rows: list[list[Any]] = []
    for row, contribution in zip(data, contributions, strict=True):
        quantity = Decimal(str(row["qty"] or 0))
        popularity = (
            (quantity / total_quantity * 100).quantize(Decimal("0.01"))
            if total_quantity
            else Decimal("0.00")
        )
        high_popularity = popularity >= average_popularity
        high_margin = contribution >= average_contribution
        if high_popularity and high_margin:
            quadrant = "Yıldız"
        elif high_popularity:
            quadrant = "At (yük hayvanı)"
        elif high_margin:
            quadrant = "Bilmece"
        else:
            quadrant = "Köpek"

        rows.append(
            [
                row["menu_item__name_tr"],
                quantity,
                row["revenue"] or Decimal("0.00"),
                contribution.quantize(Decimal("0.01")),
                popularity,
                quadrant,
            ]
        )

    rows.sort(key=lambda row: row[3], reverse=True)
    rows = rows[: params.limit]

    return ReportTable(
        title="Menü Mühendisliği",
        subtitle=(
            f"Dönem: {params.period_label} · "
            f"Ortalama katkı payı: {average_contribution.quantize(Decimal('0.01'))} · "
            f"Popülerlik eşiği: %{average_popularity.quantize(Decimal('0.01'))}"
        ),
        columns=["Ürün", "Adet", "Ciro", "Katkı payı", "Popülerlik %", "Kadran"],
        rows=rows,
    )


@register(
    "ai-maliyet",
    name_tr="Yapay zekâ maliyeti ve kullanımı",
    name_en="AI cost and usage",
    category="ai",
    permission="aiservices.can_view_ai_costs",
)
def ai_usage(params: ReportParams) -> ReportTable:
    """Sağlayıcı ve işlev bazında belirteç kullanımı ve maliyet."""
    from apps.aiservices.models import AICallLog, AIFeature

    calls = (
        AICallLog.objects.filter(
            occurred_at__date__gte=params.start_date, occurred_at__date__lte=params.end_date
        )
        .values("provider", "feature", "is_local_provider")
        .annotate(
            count=Count("id"),
            prompt=Sum("prompt_tokens"),
            completion=Sum("completion_tokens"),
            cost=Sum("estimated_cost_usd"),
            latency=Avg("latency_ms"),
        )
        .order_by("-cost", "-count")
    )

    labels = dict(AIFeature.choices)
    rows = [
        [
            row["provider"],
            str(labels.get(row["feature"], row["feature"])),
            "Yerel" if row["is_local_provider"] else "Bulut",
            row["count"],
            row["prompt"] or 0,
            row["completion"] or 0,
            (row["prompt"] or 0) + (row["completion"] or 0),
            row["cost"] or Decimal("0.000000"),
            int(row["latency"] or 0),
        ]
        for row in calls
    ]

    return ReportTable(
        title="Yapay Zekâ Maliyeti ve Kullanımı",
        subtitle=(
            f"Dönem: {params.period_label} · "
            "Maliyet yalnızca fiyatı tanımlanmış modeller için hesaplanır."
        ),
        columns=[
            "Sağlayıcı",
            "İşlev",
            "Tür",
            "Çağrı",
            "İstem belirteci",
            "Yanıt belirteci",
            "Toplam belirteç",
            "Maliyet (USD)",
            "Ort. gecikme (ms)",
        ],
        rows=rows,
        totals=[
            "TOPLAM",
            "",
            "",
            sum(row[3] for row in rows),
            sum(row[4] for row in rows),
            sum(row[5] for row in rows),
            sum(row[6] for row in rows),
            sum((row[7] for row in rows), Decimal("0.000000")),
            "",
        ],
    )


@register(
    "satis-tahmini",
    name_tr="Satış tahmini",
    name_en="Sales forecast",
    category="sales",
    permission="reporting.view_salesforecast",
    is_experimental=True,
    description="İstatistiksel taban çizgisi ile üretilen tahmin. Deneyseldir.",
)
def sales_forecast_report(params: ReportParams) -> ReportTable:
    """Haftanın günü mevsimselliğine dayalı tahmin.

    DURUM: **Deneysel.** Tahmin, geçmiş 8 haftanın aynı gün ortalamasına
    dayanır; yapay zekâ yalnızca yorum ekler, sayıyı değiştirmez.
    """
    from apps.reporting.models import DailySalesSnapshot

    history = DailySalesSnapshot.objects.filter(
        business_date__lt=params.start_date,
        business_date__gte=params.start_date - timedelta(days=56),
    )

    by_weekday: dict[int, list[Decimal]] = {}
    for snapshot in history:
        by_weekday.setdefault(snapshot.business_date.weekday(), []).append(snapshot.net_sales)

    weekday_names = [
        "Pazartesi",
        "Salı",
        "Çarşamba",
        "Perşembe",
        "Cuma",
        "Cumartesi",
        "Pazar",
    ]

    rows: list[list[Any]] = []
    current = params.start_date
    while current <= params.end_date:
        samples = by_weekday.get(current.weekday(), [])
        if samples:
            average = (sum(samples, Decimal("0.00")) / Decimal(len(samples))).quantize(
                Decimal("0.01")
            )
            lowest = min(samples)
            highest = max(samples)
        else:
            average = lowest = highest = Decimal("0.00")
        rows.append(
            [
                current,
                weekday_names[current.weekday()],
                len(samples),
                average,
                lowest,
                highest,
            ]
        )
        current += timedelta(days=1)

    return ReportTable(
        title="Satış Tahmini (Deneysel)",
        subtitle=(
            f"Dönem: {params.period_label} · Yöntem: son 8 haftanın aynı gün ortalaması · "
            "Örneklem yetersizse tahmin sıfır gösterilir."
        ),
        columns=["Tarih", "Gün", "Örneklem", "Tahmini net satış", "En düşük", "En yüksek"],
        rows=rows,
    )
