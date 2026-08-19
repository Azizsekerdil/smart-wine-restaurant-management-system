"""Stok, tedarikçi ve satın alma modelleri.

Stok mantığı:
  * Her stok kalemi (``StockItem``) partiler (``StockLot``) hâlinde tutulur.
  * Çıkışlar FIFO (giriş sırası) veya FEFO (son kullanma sırası) ile yapılır.
  * Her hareket ``StockMovement`` olarak *değiştirilemez* biçimde kaydedilir;
    stok bakiyesi bu hareketlerin toplamıyla her zaman doğrulanabilir.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.fields import EncryptedCharField
from apps.core.models import SoftDeleteModel, TimeStampedModel


class UnitOfMeasure(TimeStampedModel):
    """Ölçü birimi ve temel birime çevrim katsayısı."""

    class Dimension(models.TextChoices):
        MASS = "mass", _("Kütle")
        VOLUME = "volume", _("Hacim")
        COUNT = "count", _("Adet")

    code = models.CharField(_("Kod"), max_length=20, unique=True)
    name = models.CharField(_("Ad"), max_length=60)
    dimension = models.CharField(_("Boyut"), max_length=10, choices=Dimension.choices)
    #: Temel birime (g, ml, adet) çevrim katsayısı
    factor_to_base = models.DecimalField(
        _("Temel birime katsayı"),
        max_digits=16,
        decimal_places=6,
        default=Decimal("1.000000"),
        validators=[MinValueValidator(Decimal("0.000001"))],
    )

    class Meta:
        verbose_name = _("Ölçü birimi")
        verbose_name_plural = _("Ölçü birimleri")
        ordering = ["dimension", "code"]

    def __str__(self) -> str:
        return self.code


class Supplier(SoftDeleteModel):
    """Tedarikçi kaydı.

    İletişim bilgileri kişisel veri sayıldığından şifreli saklanır.
    """

    code = models.CharField(_("Tedarikçi kodu"), max_length=30, unique=True, db_index=True)
    name = models.CharField(_("Unvan"), max_length=250, db_index=True)
    contact_person = models.CharField(_("Yetkili kişi"), max_length=150, blank=True)
    phone = EncryptedCharField(_("Telefon"), blank=True, default="")
    email = EncryptedCharField(_("E-posta"), blank=True, default="")
    address = models.TextField(_("Adres"), blank=True)
    tax_office = models.CharField(_("Vergi dairesi"), max_length=120, blank=True)
    tax_number = EncryptedCharField(_("Vergi numarası"), blank=True, default="")

    payment_terms_days = models.PositiveSmallIntegerField(_("Ödeme vadesi (gün)"), default=30)
    lead_time_days = models.PositiveSmallIntegerField(_("Teslim süresi (gün)"), default=3)
    minimum_order_amount = models.DecimalField(
        _("Asgari sipariş tutarı"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    supplies_wine = models.BooleanField(_("Şarap tedarik eder"), default=False)
    rating = models.PositiveSmallIntegerField(
        _("Değerlendirme (1-5)"), default=3, validators=[MinValueValidator(1)]
    )
    is_active = models.BooleanField(_("Etkin"), default=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Tedarikçi")
        verbose_name_plural = _("Tedarikçiler")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class Warehouse(TimeStampedModel):
    """Depo / saklama noktası (mutfak deposu, bar, kav, ana depo)."""

    code = models.CharField(_("Kod"), max_length=30, unique=True)
    name = models.CharField(_("Ad"), max_length=150)
    is_default = models.BooleanField(_("Varsayılan"), default=False)
    is_active = models.BooleanField(_("Etkin"), default=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Sorumlu"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehouses",
    )

    class Meta:
        verbose_name = _("Depo")
        verbose_name_plural = _("Depolar")
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class StockItemCategory(TimeStampedModel):
    """Stok kalemi kategorisi (et, sebze, kuru gıda, içecek, sarf...)."""

    code = models.SlugField(_("Kod"), max_length=50, unique=True)
    name = models.CharField(_("Ad"), max_length=120)
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Üst kategori"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        verbose_name = _("Stok kategorisi")
        verbose_name_plural = _("Stok kategorileri")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class StockItem(SoftDeleteModel):
    """Stokta izlenen kalem (hammadde, içecek, sarf malzeme)."""

    class TrackingMode(models.TextChoices):
        FIFO = "fifo", _("FIFO — ilk giren ilk çıkar")
        FEFO = "fefo", _("FEFO — son kullanma tarihine göre")

    code = models.CharField(_("Stok kodu"), max_length=40, unique=True, db_index=True)
    name = models.CharField(_("Ad"), max_length=200, db_index=True)
    name_en = models.CharField(_("Ad (EN)"), max_length=200, blank=True)
    category = models.ForeignKey(
        StockItemCategory,
        verbose_name=_("Kategori"),
        on_delete=models.PROTECT,
        related_name="items",
    )
    unit = models.ForeignKey(
        UnitOfMeasure, verbose_name=_("Birim"), on_delete=models.PROTECT, related_name="items"
    )
    tracking_mode = models.CharField(
        _("Çıkış yöntemi"), max_length=10, choices=TrackingMode.choices, default=TrackingMode.FEFO
    )
    #: Şarap kalemleri kav modülünde izlenir; burada yalnızca referans tutulur
    linked_wine = models.OneToOneField(
        "cellar.Wine",
        verbose_name=_("Bağlı şarap"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_item",
    )

    minimum_quantity = models.DecimalField(
        _("Minimum stok"), max_digits=14, decimal_places=4, default=Decimal("0")
    )
    reorder_quantity = models.DecimalField(
        _("Sipariş miktarı"), max_digits=14, decimal_places=4, default=Decimal("0")
    )
    shelf_life_days = models.PositiveSmallIntegerField(_("Raf ömrü (gün)"), null=True, blank=True)
    default_supplier = models.ForeignKey(
        Supplier,
        verbose_name=_("Varsayılan tedarikçi"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_items",
    )
    barcode = models.CharField(_("Barkod"), max_length=64, blank=True, db_index=True)
    is_active = models.BooleanField(_("Etkin"), default=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Stok kalemi")
        verbose_name_plural = _("Stok kalemleri")
        ordering = ["name"]
        permissions = [
            ("can_adjust_stock", _("Stok düzeltmesi yapabilir")),
            ("can_count_stock", _("Stok sayımı yapabilir")),
            ("view_stock_valuation", _("Stok değerlemesini görebilir")),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"

    @property
    def quantity_on_hand(self) -> Decimal:
        """Tüm depolardaki toplam eldeki miktar."""
        total = self.lots.filter(is_deleted=False).aggregate(total=Sum("quantity_remaining"))[
            "total"
        ]
        return total or Decimal("0")

    @property
    def average_unit_cost(self) -> Decimal:
        """Eldeki partilerin ağırlıklı ortalama birim maliyeti."""
        lots = list(self.lots.filter(is_deleted=False, quantity_remaining__gt=0))
        if not lots:
            last = self.lots.order_by("-received_on").first()
            return last.unit_cost if last else Decimal("0.00")
        total_qty = sum((lot.quantity_remaining for lot in lots), Decimal("0"))
        if total_qty == 0:
            return Decimal("0.00")
        total_value = sum((lot.quantity_remaining * lot.unit_cost for lot in lots), Decimal("0"))
        return (total_value / total_qty).quantize(Decimal("0.0001"))

    @property
    def stock_value(self) -> Decimal:
        return sum(
            (lot.quantity_remaining * lot.unit_cost for lot in self.lots.filter(is_deleted=False)),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))

    @property
    def is_below_minimum(self) -> bool:
        return self.minimum_quantity > 0 and self.quantity_on_hand < self.minimum_quantity


class StockLot(SoftDeleteModel):
    """Stok kaleminin tek bir partisi."""

    stock_item = models.ForeignKey(
        StockItem, verbose_name=_("Stok kalemi"), on_delete=models.PROTECT, related_name="lots"
    )
    warehouse = models.ForeignKey(
        Warehouse, verbose_name=_("Depo"), on_delete=models.PROTECT, related_name="lots"
    )
    lot_code = models.CharField(_("Parti kodu"), max_length=60, db_index=True)
    supplier = models.ForeignKey(
        Supplier,
        verbose_name=_("Tedarikçi"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lots",
    )
    received_on = models.DateField(_("Giriş tarihi"), default=timezone.localdate, db_index=True)
    expires_on = models.DateField(_("Son kullanma tarihi"), null=True, blank=True, db_index=True)
    quantity_received = models.DecimalField(
        _("Giren miktar"), max_digits=14, decimal_places=4, default=Decimal("0")
    )
    quantity_remaining = models.DecimalField(
        _("Kalan miktar"), max_digits=14, decimal_places=4, default=Decimal("0"), db_index=True
    )
    unit_cost = models.DecimalField(
        _("Birim maliyet"), max_digits=14, decimal_places=4, default=Decimal("0")
    )

    class Meta:
        verbose_name = _("Stok partisi")
        verbose_name_plural = _("Stok partileri")
        ordering = ["expires_on", "received_on", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["stock_item", "warehouse", "lot_code"], name="uniq_stock_lot"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_remaining__gte=Decimal("0")),
                name="stocklot_remaining_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.stock_item.code} · {self.lot_code} ({self.quantity_remaining})"

    @property
    def days_to_expiry(self) -> int | None:
        if not self.expires_on:
            return None
        return (self.expires_on - timezone.localdate()).days

    @property
    def is_expired(self) -> bool:
        days = self.days_to_expiry
        return days is not None and days < 0

    @property
    def is_expiring_soon(self) -> bool:
        days = self.days_to_expiry
        return days is not None and 0 <= days <= 7


class StockMovement(models.Model):
    """Değiştirilemez stok hareketi.

    Bakiye her zaman hareketlerin toplamıyla doğrulanabilir olmalıdır; bu
    nedenle kayıtlar oluşturulduktan sonra güncellenemez ve silinemez.
    Bir hatanın düzeltilmesi için ters yönlü yeni bir hareket girilir.
    """

    class MovementType(models.TextChoices):
        RECEIPT = "receipt", _("Mal kabul")
        SALE = "sale", _("Satış çıkışı")
        WASTE = "waste", _("Fire / zayi")
        TRANSFER_OUT = "transfer_out", _("Transfer çıkışı")
        TRANSFER_IN = "transfer_in", _("Transfer girişi")
        COUNT_ADJUST = "count_adjust", _("Sayım düzeltmesi")
        RETURN_SUPPLIER = "return_supplier", _("Tedarikçiye iade")
        PRODUCTION_IN = "production_in", _("Üretim girişi")
        PRODUCTION_OUT = "production_out", _("Üretim tüketimi")
        OPENING_BALANCE = "opening", _("Açılış bakiyesi")

    stock_item = models.ForeignKey(
        StockItem, verbose_name=_("Stok kalemi"), on_delete=models.PROTECT, related_name="movements"
    )
    lot = models.ForeignKey(
        StockLot,
        verbose_name=_("Parti"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
    )
    warehouse = models.ForeignKey(
        Warehouse, verbose_name=_("Depo"), on_delete=models.PROTECT, related_name="movements"
    )
    movement_type = models.CharField(
        _("Hareket türü"), max_length=20, choices=MovementType.choices, db_index=True
    )
    #: Girişler pozitif, çıkışlar negatif
    quantity = models.DecimalField(_("Miktar"), max_digits=14, decimal_places=4)
    unit_cost = models.DecimalField(
        _("Birim maliyet"), max_digits=14, decimal_places=4, default=Decimal("0")
    )
    occurred_at = models.DateTimeField(_("Zaman"), default=timezone.now, db_index=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("İşlemi yapan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    reference_type = models.CharField(_("Referans türü"), max_length=60, blank=True)
    reference_id = models.CharField(_("Referans kimliği"), max_length=64, blank=True)
    note = models.CharField(_("Not"), max_length=250, blank=True)

    class Meta:
        verbose_name = _("Stok hareketi")
        verbose_name_plural = _("Stok hareketleri")
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["stock_item", "-occurred_at"], name="movement_item_ts_idx"),
            models.Index(fields=["movement_type", "-occurred_at"], name="movement_type_ts_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.stock_item.code} · {self.get_movement_type_display()} · {self.quantity}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            raise ValueError(
                "Stok hareketleri değiştirilemez. Düzeltme için ters yönlü yeni "
                "bir hareket oluşturun."
            )
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> None:
        raise ValueError("Stok hareketleri silinemez (denetim izi korunur).")

    @property
    def value(self) -> Decimal:
        return (self.quantity * self.unit_cost).quantize(Decimal("0.0001"))


class PurchaseRequest(SoftDeleteModel):
    """Satın alma talebi (mutfak/bar/kav → satın alma)."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Taslak")
        SUBMITTED = "submitted", _("Gönderildi")
        APPROVED = "approved", _("Onaylandı")
        REJECTED = "rejected", _("Reddedildi")
        ORDERED = "ordered", _("Siparişe dönüştürüldü")

    number = models.CharField(_("Talep no"), max_length=30, unique=True, db_index=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Talep eden"),
        on_delete=models.PROTECT,
        related_name="purchase_requests",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        verbose_name=_("Depo"),
        on_delete=models.PROTECT,
        related_name="purchase_requests",
    )
    needed_by = models.DateField(_("İhtiyaç tarihi"), null=True, blank=True)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    justification = models.TextField(_("Gerekçe"), blank=True)
    #: Yapay zekâ önerisiyle oluşturulduysa işaretlenir
    is_ai_suggested = models.BooleanField(_("Yapay zekâ önerisi"), default=False)

    class Meta:
        verbose_name = _("Satın alma talebi")
        verbose_name_plural = _("Satın alma talepleri")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.number} · {self.get_status_display()}"


class PurchaseRequestLine(TimeStampedModel):
    """Satın alma talebi satırı."""

    request = models.ForeignKey(
        PurchaseRequest, verbose_name=_("Talep"), on_delete=models.CASCADE, related_name="lines"
    )
    stock_item = models.ForeignKey(
        StockItem,
        verbose_name=_("Stok kalemi"),
        on_delete=models.PROTECT,
        related_name="request_lines",
    )
    quantity = models.DecimalField(
        _("Miktar"),
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    note = models.CharField(_("Not"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("Talep satırı")
        verbose_name_plural = _("Talep satırları")
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.stock_item.code} × {self.quantity}"


class SupplierQuotation(TimeStampedModel):
    """Tedarikçi teklifi (teklif karşılaştırma için)."""

    request = models.ForeignKey(
        PurchaseRequest,
        verbose_name=_("Talep"),
        on_delete=models.CASCADE,
        related_name="quotations",
    )
    supplier = models.ForeignKey(
        Supplier, verbose_name=_("Tedarikçi"), on_delete=models.PROTECT, related_name="quotations"
    )
    quoted_on = models.DateField(_("Teklif tarihi"), default=timezone.localdate)
    valid_until = models.DateField(_("Geçerlilik"), null=True, blank=True)
    delivery_days = models.PositiveSmallIntegerField(_("Teslim süresi (gün)"), default=3)
    total_amount = models.DecimalField(
        _("Toplam tutar"), max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    is_selected = models.BooleanField(_("Seçildi"), default=False)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Tedarikçi teklifi")
        verbose_name_plural = _("Tedarikçi teklifleri")
        ordering = ["total_amount"]
        constraints = [
            models.UniqueConstraint(
                fields=["request", "supplier"], name="uniq_quotation_request_supplier"
            )
        ]

    def __str__(self) -> str:
        return f"{self.supplier.name} · {self.total_amount}"


class PurchaseOrder(SoftDeleteModel):
    """Satın alma siparişi."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Taslak")
        SENT = "sent", _("Tedarikçiye gönderildi")
        PARTIAL = "partial", _("Kısmen teslim alındı")
        RECEIVED = "received", _("Teslim alındı")
        CANCELLED = "cancelled", _("İptal edildi")

    number = models.CharField(_("Sipariş no"), max_length=30, unique=True, db_index=True)
    supplier = models.ForeignKey(
        Supplier, verbose_name=_("Tedarikçi"), on_delete=models.PROTECT, related_name="orders"
    )
    warehouse = models.ForeignKey(
        Warehouse, verbose_name=_("Teslim deposu"), on_delete=models.PROTECT, related_name="orders"
    )
    request = models.ForeignKey(
        PurchaseRequest,
        verbose_name=_("Kaynak talep"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    ordered_on = models.DateField(_("Sipariş tarihi"), default=timezone.localdate)
    expected_on = models.DateField(_("Beklenen teslim"), null=True, blank=True)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    currency = models.CharField(_("Para birimi"), max_length=3, default="TRY")
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Satın alma siparişi")
        verbose_name_plural = _("Satın alma siparişleri")
        ordering = ["-ordered_on", "-id"]

    def __str__(self) -> str:
        return f"{self.number} · {self.supplier.name}"

    @property
    def total_amount(self) -> Decimal:
        return sum((line.line_total for line in self.lines.all()), Decimal("0.00")).quantize(
            Decimal("0.01")
        )

    @property
    def is_fully_received(self) -> bool:
        return all(line.quantity_received >= line.quantity_ordered for line in self.lines.all())


class PurchaseOrderLine(TimeStampedModel):
    """Satın alma siparişi satırı."""

    order = models.ForeignKey(
        PurchaseOrder, verbose_name=_("Sipariş"), on_delete=models.CASCADE, related_name="lines"
    )
    stock_item = models.ForeignKey(
        StockItem,
        verbose_name=_("Stok kalemi"),
        on_delete=models.PROTECT,
        related_name="order_lines",
    )
    quantity_ordered = models.DecimalField(
        _("Sipariş miktarı"),
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    quantity_received = models.DecimalField(
        _("Teslim alınan"), max_digits=14, decimal_places=4, default=Decimal("0")
    )
    unit_price = models.DecimalField(
        _("Birim fiyat"), max_digits=14, decimal_places=4, default=Decimal("0")
    )
    tax_rate = models.DecimalField(
        _("KDV (%)"), max_digits=5, decimal_places=2, default=Decimal("10.00")
    )

    class Meta:
        verbose_name = _("Sipariş satırı")
        verbose_name_plural = _("Sipariş satırları")
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.stock_item.code} × {self.quantity_ordered}"

    @property
    def line_total(self) -> Decimal:
        return (self.quantity_ordered * self.unit_price).quantize(Decimal("0.01"))

    @property
    def quantity_outstanding(self) -> Decimal:
        return max(Decimal("0"), self.quantity_ordered - self.quantity_received)


class GoodsReceipt(SoftDeleteModel):
    """Mal kabul belgesi."""

    number = models.CharField(_("Kabul no"), max_length=30, unique=True, db_index=True)
    order = models.ForeignKey(
        PurchaseOrder,
        verbose_name=_("Sipariş"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="receipts",
    )
    supplier = models.ForeignKey(
        Supplier, verbose_name=_("Tedarikçi"), on_delete=models.PROTECT, related_name="receipts"
    )
    warehouse = models.ForeignKey(
        Warehouse, verbose_name=_("Depo"), on_delete=models.PROTECT, related_name="receipts"
    )
    received_on = models.DateField(_("Kabul tarihi"), default=timezone.localdate)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Teslim alan"),
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    invoice_number = models.CharField(_("Fatura no"), max_length=60, blank=True)
    temperature_check_ok = models.BooleanField(
        _("Soğuk zincir uygun"), default=True, help_text=_("Soğuk zincir ürünleri için.")
    )
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Mal kabul")
        verbose_name_plural = _("Mal kabulleri")
        ordering = ["-received_on", "-id"]

    def __str__(self) -> str:
        return f"{self.number} · {self.supplier.name}"


class GoodsReceiptLine(TimeStampedModel):
    """Mal kabul satırı — kabul edildiğinde stok partisi oluşturulur."""

    receipt = models.ForeignKey(
        GoodsReceipt, verbose_name=_("Mal kabul"), on_delete=models.CASCADE, related_name="lines"
    )
    stock_item = models.ForeignKey(
        StockItem,
        verbose_name=_("Stok kalemi"),
        on_delete=models.PROTECT,
        related_name="receipt_lines",
    )
    order_line = models.ForeignKey(
        PurchaseOrderLine,
        verbose_name=_("Sipariş satırı"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipt_lines",
    )
    lot = models.ForeignKey(
        StockLot,
        verbose_name=_("Oluşan parti"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipt_lines",
    )
    quantity = models.DecimalField(
        _("Miktar"),
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    unit_cost = models.DecimalField(
        _("Birim maliyet"), max_digits=14, decimal_places=4, default=Decimal("0")
    )
    lot_code = models.CharField(_("Parti kodu"), max_length=60, blank=True)
    expires_on = models.DateField(_("Son kullanma"), null=True, blank=True)
    rejected_quantity = models.DecimalField(
        _("Reddedilen miktar"), max_digits=14, decimal_places=4, default=Decimal("0")
    )
    rejection_reason = models.CharField(_("Ret gerekçesi"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("Mal kabul satırı")
        verbose_name_plural = _("Mal kabul satırları")
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.stock_item.code} × {self.quantity}"


class WastageEntry(TimeStampedModel):
    """Fire, bozulma, dökülme ve zayi kaydı."""

    class Reason(models.TextChoices):
        SPOILAGE = "spoilage", _("Bozulma")
        EXPIRY = "expiry", _("Son kullanma tarihi geçti")
        BREAKAGE = "breakage", _("Kırılma")
        SPILLAGE = "spillage", _("Dökülme")
        PREPARATION = "preparation", _("Hazırlık firesi")
        OVERCOOKED = "overcooked", _("Pişirme hatası")
        CUSTOMER_RETURN = "customer_return", _("Müşteri iadesi")
        THEFT = "theft", _("Kayıp / hırsızlık şüphesi")
        STAFF_MEAL = "staff_meal", _("Personel yemeği")
        TRAINING = "training", _("Eğitim")
        OTHER = "other", _("Diğer")

    stock_item = models.ForeignKey(
        StockItem, verbose_name=_("Stok kalemi"), on_delete=models.PROTECT, related_name="wastages"
    )
    lot = models.ForeignKey(
        StockLot,
        verbose_name=_("Parti"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wastages",
    )
    warehouse = models.ForeignKey(
        Warehouse, verbose_name=_("Depo"), on_delete=models.PROTECT, related_name="wastages"
    )
    quantity = models.DecimalField(
        _("Miktar"),
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    reason = models.CharField(_("Gerekçe"), max_length=20, choices=Reason.choices)
    occurred_at = models.DateTimeField(_("Zaman"), default=timezone.now, db_index=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Kaydeden"),
        on_delete=models.PROTECT,
        related_name="wastage_entries",
    )
    estimated_cost = models.DecimalField(
        _("Tahmini maliyet"), max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    approval = models.ForeignKey(
        "accounts.ApprovalRequest",
        verbose_name=_("Onay talebi"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wastage_entries",
    )
    description = models.TextField(_("Açıklama"), blank=True)

    class Meta:
        verbose_name = _("Fire kaydı")
        verbose_name_plural = _("Fire kayıtları")
        ordering = ["-occurred_at"]

    def __str__(self) -> str:
        return f"{self.stock_item.code} · {self.get_reason_display()} · {self.quantity}"


class StockTransfer(TimeStampedModel):
    """Depolar arası transfer."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Taslak")
        IN_TRANSIT = "in_transit", _("Yolda")
        COMPLETED = "completed", _("Tamamlandı")
        CANCELLED = "cancelled", _("İptal")

    number = models.CharField(_("Transfer no"), max_length=30, unique=True, db_index=True)
    source = models.ForeignKey(
        Warehouse,
        verbose_name=_("Kaynak depo"),
        on_delete=models.PROTECT,
        related_name="transfers_out",
    )
    destination = models.ForeignKey(
        Warehouse,
        verbose_name=_("Hedef depo"),
        on_delete=models.PROTECT,
        related_name="transfers_in",
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    transferred_on = models.DateField(_("Transfer tarihi"), default=timezone.localdate)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Stok transferi")
        verbose_name_plural = _("Stok transferleri")
        ordering = ["-transferred_on"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(source=models.F("destination")),
                name="transfer_source_ne_destination",
            )
        ]

    def __str__(self) -> str:
        return f"{self.number} · {self.source.code} → {self.destination.code}"


class StockTransferLine(TimeStampedModel):
    """Transfer satırı."""

    transfer = models.ForeignKey(
        StockTransfer, verbose_name=_("Transfer"), on_delete=models.CASCADE, related_name="lines"
    )
    stock_item = models.ForeignKey(
        StockItem,
        verbose_name=_("Stok kalemi"),
        on_delete=models.PROTECT,
        related_name="transfer_lines",
    )
    quantity = models.DecimalField(
        _("Miktar"),
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )

    class Meta:
        verbose_name = _("Transfer satırı")
        verbose_name_plural = _("Transfer satırları")
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.stock_item.code} × {self.quantity}"


class StockCount(TimeStampedModel):
    """Stok sayımı oturumu."""

    class Status(models.TextChoices):
        OPEN = "open", _("Açık")
        COUNTED = "counted", _("Sayıldı")
        POSTED = "posted", _("Muhasebeleştirildi")
        CANCELLED = "cancelled", _("İptal")

    number = models.CharField(_("Sayım no"), max_length=30, unique=True, db_index=True)
    warehouse = models.ForeignKey(
        Warehouse, verbose_name=_("Depo"), on_delete=models.PROTECT, related_name="counts"
    )
    counted_on = models.DateField(_("Sayım tarihi"), default=timezone.localdate)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.OPEN
    )
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Sayan"),
        on_delete=models.PROTECT,
        related_name="stock_counts",
    )
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Stok sayımı")
        verbose_name_plural = _("Stok sayımları")
        ordering = ["-counted_on"]

    def __str__(self) -> str:
        return f"{self.number} · {self.warehouse.code}"

    @property
    def total_variance_value(self) -> Decimal:
        return sum((line.variance_value for line in self.lines.all()), Decimal("0.00"))


class StockCountLine(TimeStampedModel):
    """Sayım satırı: sistem miktarı ile sayılan miktar karşılaştırması."""

    count = models.ForeignKey(
        StockCount, verbose_name=_("Sayım"), on_delete=models.CASCADE, related_name="lines"
    )
    stock_item = models.ForeignKey(
        StockItem,
        verbose_name=_("Stok kalemi"),
        on_delete=models.PROTECT,
        related_name="count_lines",
    )
    system_quantity = models.DecimalField(
        _("Sistem miktarı"), max_digits=14, decimal_places=4, default=Decimal("0")
    )
    counted_quantity = models.DecimalField(
        _("Sayılan miktar"), max_digits=14, decimal_places=4, default=Decimal("0")
    )
    unit_cost = models.DecimalField(
        _("Birim maliyet"), max_digits=14, decimal_places=4, default=Decimal("0")
    )
    note = models.CharField(_("Not"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("Sayım satırı")
        verbose_name_plural = _("Sayım satırları")
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["count", "stock_item"], name="uniq_count_item")
        ]

    def __str__(self) -> str:
        return f"{self.stock_item.code} · fark {self.variance}"

    @property
    def variance(self) -> Decimal:
        return self.counted_quantity - self.system_quantity

    @property
    def variance_value(self) -> Decimal:
        return (self.variance * self.unit_cost).quantize(Decimal("0.01"))
