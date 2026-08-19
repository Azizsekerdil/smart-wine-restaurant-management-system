"""Salon operasyonu modelleri.

Akış:
    Rezervasyon → Masa açılışı → Sipariş → Hazırlık fişi (KOT/KDS) →
    Servis → Hesap (bölme dahil) → Ödeme → Gün sonu

Mali doğruluk ilkeleri:
  * Sipariş satırı tutarları *kaydedildiği anda* dondurulur; menü fiyatı
    sonradan değişse bile geçmiş hesap değişmez.
  * İptal ve iade fiziksel silme yapmaz; ters kayıt üretir.
  * Her indirim/ikram, yetki sınırı aşıldığında ``ApprovalRequest`` gerektirir.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import SoftDeleteModel, TimeStampedModel

TWO_PLACES = Decimal("0.01")


# ---------------------------------------------------------------------------
# Salon ve masa
# ---------------------------------------------------------------------------
class FloorSection(TimeStampedModel):
    """Salon bölümü (ana salon, teras, bar, özel oda, kav odası)."""

    code = models.CharField(_("Kod"), max_length=30, unique=True)
    name = models.CharField(_("Ad"), max_length=120)
    name_en = models.CharField(_("Ad (EN)"), max_length=120, blank=True)
    is_smoking = models.BooleanField(_("Sigara içilebilir"), default=False)
    is_outdoor = models.BooleanField(_("Açık alan"), default=False)
    is_private = models.BooleanField(_("Özel alan"), default=False)
    sort_order = models.PositiveSmallIntegerField(_("Sıra"), default=100)
    is_active = models.BooleanField(_("Etkin"), default=True)

    class Meta:
        verbose_name = _("Salon bölümü")
        verbose_name_plural = _("Salon bölümleri")
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class DiningTable(TimeStampedModel):
    """Masa."""

    class Status(models.TextChoices):
        FREE = "free", _("Boş")
        RESERVED = "reserved", _("Rezerve")
        SEATED = "seated", _("Misafir oturdu")
        ORDERED = "ordered", _("Sipariş alındı")
        SERVED = "served", _("Servis edildi")
        BILL_REQUESTED = "bill_requested", _("Hesap istendi")
        CLEANING = "cleaning", _("Temizleniyor")
        OUT_OF_SERVICE = "out_of_service", _("Servis dışı")

    section = models.ForeignKey(
        FloorSection, verbose_name=_("Bölüm"), on_delete=models.PROTECT, related_name="tables"
    )
    number = models.CharField(_("Masa no"), max_length=20, db_index=True)
    name = models.CharField(_("Ad"), max_length=80, blank=True)
    seats = models.PositiveSmallIntegerField(
        _("Kişi kapasitesi"), default=4, validators=[MinValueValidator(1)]
    )
    min_seats = models.PositiveSmallIntegerField(_("Asgari kişi"), default=1)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.FREE, db_index=True
    )
    #: Salon planındaki konum (yüzde cinsinden, responsive yerleşim için)
    position_x = models.DecimalField(_("X konumu (%)"), max_digits=5, decimal_places=2, default=0)
    position_y = models.DecimalField(_("Y konumu (%)"), max_digits=5, decimal_places=2, default=0)
    shape = models.CharField(
        _("Şekil"),
        max_length=20,
        choices=[("square", _("Kare")), ("round", _("Yuvarlak")), ("rect", _("Dikdörtgen"))],
        default="square",
    )
    is_combinable = models.BooleanField(_("Birleştirilebilir"), default=True)
    is_active = models.BooleanField(_("Etkin"), default=True)
    qr_token = models.CharField(
        _("QR menü belirteci"),
        max_length=64,
        blank=True,
        db_index=True,
        help_text=_("Masaya özel QR menü bağlantısı için."),
    )

    class Meta:
        verbose_name = _("Masa")
        verbose_name_plural = _("Masalar")
        ordering = ["section__sort_order", "number"]
        constraints = [
            models.UniqueConstraint(fields=["section", "number"], name="uniq_table_section_number")
        ]
        permissions = [
            ("can_open_table", _("Masa açabilir")),
            ("can_transfer_table", _("Masa devredebilir")),
            ("can_seat_guest", _("Misafir yerleştirebilir")),
        ]

    def __str__(self) -> str:
        return f"{self.section.name} · {self.number}"

    @property
    def label(self) -> str:
        return self.name or f"{self.number}"

    @property
    def active_order(self) -> Order | None:
        """Masadaki açık sipariş."""
        return self.orders.filter(status__in=Order.OPEN_STATUSES).order_by("-opened_at").first()

    @property
    def status_badge_class(self) -> str:
        return {
            self.Status.FREE: "bg-success",
            self.Status.RESERVED: "bg-info text-dark",
            self.Status.SEATED: "bg-primary",
            self.Status.ORDERED: "bg-warning text-dark",
            self.Status.SERVED: "bg-secondary",
            self.Status.BILL_REQUESTED: "bg-danger",
            self.Status.CLEANING: "bg-light text-dark",
            self.Status.OUT_OF_SERVICE: "bg-dark",
        }.get(self.Status(self.status), "bg-secondary")


# ---------------------------------------------------------------------------
# Rezervasyon
# ---------------------------------------------------------------------------
class Reservation(SoftDeleteModel):
    """Masa rezervasyonu."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Onay bekliyor")
        CONFIRMED = "confirmed", _("Onaylandı")
        SEATED = "seated", _("Misafir geldi")
        COMPLETED = "completed", _("Tamamlandı")
        CANCELLED = "cancelled", _("İptal edildi")
        NO_SHOW = "no_show", _("Gelmedi")

    class Source(models.TextChoices):
        PHONE = "phone", _("Telefon")
        WALK_IN = "walk_in", _("Kapıdan")
        WEB = "web", _("Web")
        PARTNER = "partner", _("İş ortağı")
        STAFF = "staff", _("Personel")

    code = models.CharField(_("Rezervasyon kodu"), max_length=20, unique=True, db_index=True)
    customer = models.ForeignKey(
        "crm.Customer",
        verbose_name=_("Müşteri"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reservations",
    )
    guest_name = models.CharField(_("Misafir adı"), max_length=150)
    guest_count = models.PositiveSmallIntegerField(
        _("Kişi sayısı"), default=2, validators=[MinValueValidator(1)]
    )
    reserved_for = models.DateTimeField(_("Rezervasyon zamanı"), db_index=True)
    duration_minutes = models.PositiveSmallIntegerField(_("Süre (dk)"), default=120)
    tables = models.ManyToManyField(
        DiningTable, verbose_name=_("Masalar"), blank=True, related_name="reservations"
    )
    section_preference = models.ForeignKey(
        FloorSection,
        verbose_name=_("Tercih edilen bölüm"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.CONFIRMED, db_index=True
    )
    source = models.CharField(
        _("Kaynak"), max_length=20, choices=Source.choices, default=Source.PHONE
    )
    special_requests = models.TextField(_("Özel istekler"), blank=True)
    allergy_notes = models.TextField(
        _("Alerji notları"),
        blank=True,
        help_text=_("Mutfağa iletilir. Tıbbi tavsiye yerine geçmez."),
    )
    occasion = models.CharField(_("Özel gün"), max_length=100, blank=True)
    deposit_amount = models.DecimalField(
        _("Kapora"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    seated_at = models.DateTimeField(_("Oturma zamanı"), null=True, blank=True)
    cancelled_reason = models.CharField(_("İptal gerekçesi"), max_length=250, blank=True)

    class Meta:
        verbose_name = _("Rezervasyon")
        verbose_name_plural = _("Rezervasyonlar")
        ordering = ["reserved_for"]
        indexes = [
            models.Index(fields=["reserved_for", "status"], name="reservation_time_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.guest_name} · {self.reserved_for:%d.%m.%Y %H:%M}"

    @property
    def ends_at(self) -> Any:
        return self.reserved_for + timezone.timedelta(minutes=self.duration_minutes)

    @property
    def is_active_status(self) -> bool:
        return self.status in {self.Status.PENDING, self.Status.CONFIRMED, self.Status.SEATED}

    def overlaps(self, other: Reservation) -> bool:
        """İki rezervasyonun zaman aralığı çakışıyor mu?"""
        return self.reserved_for < other.ends_at and other.reserved_for < self.ends_at


class WaitlistEntry(TimeStampedModel):
    """Bekleme listesi kaydı."""

    class Status(models.TextChoices):
        WAITING = "waiting", _("Bekliyor")
        NOTIFIED = "notified", _("Çağrıldı")
        SEATED = "seated", _("Yerleştirildi")
        LEFT = "left", _("Ayrıldı")

    guest_name = models.CharField(_("Misafir adı"), max_length=150)
    guest_count = models.PositiveSmallIntegerField(_("Kişi sayısı"), default=2)
    customer = models.ForeignKey(
        "crm.Customer",
        verbose_name=_("Müşteri"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waitlist_entries",
    )
    joined_at = models.DateTimeField(_("Listeye giriş"), default=timezone.now, db_index=True)
    quoted_wait_minutes = models.PositiveSmallIntegerField(_("Tahmini bekleme (dk)"), default=15)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.WAITING, db_index=True
    )
    notified_at = models.DateTimeField(_("Çağrı zamanı"), null=True, blank=True)
    seated_at = models.DateTimeField(_("Yerleşme zamanı"), null=True, blank=True)
    note = models.CharField(_("Not"), max_length=250, blank=True)

    class Meta:
        verbose_name = _("Bekleme listesi kaydı")
        verbose_name_plural = _("Bekleme listesi")
        ordering = ["joined_at"]

    def __str__(self) -> str:
        return f"{self.guest_name} ({self.guest_count}) · {self.get_status_display()}"

    @property
    def waiting_minutes(self) -> int:
        end = self.seated_at or timezone.now()
        return int((end - self.joined_at).total_seconds() // 60)


# ---------------------------------------------------------------------------
# Sipariş
# ---------------------------------------------------------------------------
class Order(SoftDeleteModel):
    """Hesap / adisyon."""

    class Channel(models.TextChoices):
        DINE_IN = "dine_in", _("Salon")
        BAR = "bar", _("Bar")
        TAKEAWAY = "takeaway", _("Paket servis")
        EVENT = "event", _("Etkinlik")

    class Status(models.TextChoices):
        OPEN = "open", _("Açık")
        SENT = "sent", _("Mutfağa gönderildi")
        SERVED = "served", _("Servis edildi")
        BILLED = "billed", _("Hesap çıkarıldı")
        PAID = "paid", _("Ödendi")
        VOID = "void", _("İptal edildi")

    OPEN_STATUSES = ("open", "sent", "served", "billed")

    number = models.CharField(_("Adisyon no"), max_length=30, unique=True, db_index=True)
    channel = models.CharField(
        _("Kanal"), max_length=20, choices=Channel.choices, default=Channel.DINE_IN
    )
    table = models.ForeignKey(
        DiningTable,
        verbose_name=_("Masa"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
    )
    reservation = models.ForeignKey(
        Reservation,
        verbose_name=_("Rezervasyon"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    customer = models.ForeignKey(
        "crm.Customer",
        verbose_name=_("Müşteri"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    guest_count = models.PositiveSmallIntegerField(_("Kişi sayısı"), default=1)
    server = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Garson"),
        on_delete=models.PROTECT,
        related_name="orders_served",
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True
    )

    opened_at = models.DateTimeField(_("Açılış"), default=timezone.now, db_index=True)
    closed_at = models.DateTimeField(_("Kapanış"), null=True, blank=True)

    # --- Mali alanlar (satırlardan hesaplanır, kapanışta dondurulur) ---
    subtotal = models.DecimalField(_("Ara toplam"), max_digits=14, decimal_places=2, default=0)
    discount_total = models.DecimalField(_("İndirim"), max_digits=14, decimal_places=2, default=0)
    service_charge = models.DecimalField(
        _("Servis bedeli"), max_digits=14, decimal_places=2, default=0
    )
    tax_total = models.DecimalField(_("KDV"), max_digits=14, decimal_places=2, default=0)
    grand_total = models.DecimalField(_("Genel toplam"), max_digits=14, decimal_places=2, default=0)

    service_charge_percent = models.DecimalField(
        _("Servis bedeli (%)"), max_digits=5, decimal_places=2, default=Decimal("0.00")
    )

    #: Bölünmüş hesaplarda ana adisyona bağlantı
    parent_order = models.ForeignKey(
        "self",
        verbose_name=_("Ana adisyon"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="split_orders",
    )
    #: Birleştirilmiş adisyonlarda hedef adisyona bağlantı
    merged_into = models.ForeignKey(
        "self",
        verbose_name=_("Birleştirildiği adisyon"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merged_orders",
    )

    void_reason = models.CharField(_("İptal gerekçesi"), max_length=250, blank=True)
    void_approval = models.ForeignKey(
        "accounts.ApprovalRequest",
        verbose_name=_("İptal onayı"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voided_orders",
    )
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Adisyon")
        verbose_name_plural = _("Adisyonlar")
        ordering = ["-opened_at"]
        indexes = [
            models.Index(fields=["status", "-opened_at"], name="order_status_ts_idx"),
            models.Index(fields=["channel", "-opened_at"], name="order_channel_ts_idx"),
        ]
        permissions = [
            ("can_take_payment", _("Ödeme alabilir")),
            ("can_split_bill", _("Hesap bölebilir")),
            ("can_merge_orders", _("Adisyon birleştirebilir")),
            ("can_void_order", _("Adisyon iptal edebilir")),
            ("can_apply_discount", _("İndirim uygulayabilir")),
            ("can_comp_item", _("İkram yapabilir")),
            ("can_print_receipt", _("Fiş yazdırabilir")),
            ("can_close_day", _("Gün sonu kapatabilir")),
        ]

    def __str__(self) -> str:
        return f"{self.number} · {self.get_status_display()}"

    # -- Hesaplama ----------------------------------------------------------
    def recalculate(self, *, save: bool = True) -> None:
        """Satırlardan mali toplamları yeniden hesaplar.

        Kapanmış (``PAID`` / ``VOID``) adisyonlarda hesaplama yapılmaz;
        geçmiş mali kayıt değiştirilmez.
        """
        if self.status in {self.Status.PAID, self.Status.VOID}:
            return

        lines = list(self.lines.filter(is_voided=False))
        subtotal = sum((line.gross_amount for line in lines), Decimal("0.00"))
        discount = sum((line.discount_amount for line in lines), Decimal("0.00"))
        net = subtotal - discount
        service = (net * self.service_charge_percent / Decimal("100")).quantize(TWO_PLACES)
        tax = sum((line.tax_amount for line in lines), Decimal("0.00"))

        self.subtotal = subtotal.quantize(TWO_PLACES)
        self.discount_total = discount.quantize(TWO_PLACES)
        self.service_charge = service
        self.tax_total = tax.quantize(TWO_PLACES)
        self.grand_total = (net + service + tax).quantize(TWO_PLACES)

        if save:
            self.save(
                update_fields=[
                    "subtotal",
                    "discount_total",
                    "service_charge",
                    "tax_total",
                    "grand_total",
                    "updated_at",
                ]
            )

    @property
    def amount_paid(self) -> Decimal:
        total = self.payments.filter(is_voided=False).aggregate(total=models.Sum("amount"))["total"]
        return (total or Decimal("0.00")).quantize(TWO_PLACES)

    @property
    def amount_due(self) -> Decimal:
        return max(Decimal("0.00"), (self.grand_total - self.amount_paid).quantize(TWO_PLACES))

    @property
    def is_fully_paid(self) -> bool:
        return self.amount_due <= Decimal("0.00") and self.grand_total > Decimal("0.00")

    @property
    def duration_minutes(self) -> int:
        end = self.closed_at or timezone.now()
        return int((end - self.opened_at).total_seconds() // 60)

    @property
    def average_per_guest(self) -> Decimal:
        if not self.guest_count:
            return Decimal("0.00")
        return (self.grand_total / self.guest_count).quantize(TWO_PLACES)


class OrderLine(TimeStampedModel):
    """Adisyon satırı.

    Fiyat, KDV oranı ve ürün adı satır oluşturulurken *kopyalanır*. Menüdeki
    sonraki değişiklikler geçmiş adisyonları etkilemez.
    """

    class ServiceUnit(models.TextChoices):
        PORTION = "portion", _("Porsiyon")
        BOTTLE = "bottle", _("Şişe")
        GLASS = "glass", _("Kadeh")
        FLIGHT = "flight", _("Uçuş / tadım seti")

    order = models.ForeignKey(
        Order, verbose_name=_("Adisyon"), on_delete=models.CASCADE, related_name="lines"
    )
    menu_item = models.ForeignKey(
        "catalog.MenuItem",
        verbose_name=_("Menü ürünü"),
        on_delete=models.PROTECT,
        related_name="order_lines",
    )
    #: Kadeh/şişe şarap satışında hangi şaraptan düşüleceği
    wine = models.ForeignKey(
        "cellar.Wine",
        verbose_name=_("Şarap"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order_lines",
    )
    service_unit = models.CharField(
        _("Servis birimi"), max_length=20, choices=ServiceUnit.choices, default=ServiceUnit.PORTION
    )

    # --- Dondurulmuş ürün bilgisi ---
    item_name = models.CharField(_("Ürün adı"), max_length=250)
    quantity = models.DecimalField(
        _("Adet"), max_digits=10, decimal_places=3, default=Decimal("1.000")
    )
    unit_price = models.DecimalField(_("Birim fiyat"), max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(
        _("KDV (%)"), max_digits=5, decimal_places=2, default=Decimal("10.00")
    )
    unit_cost = models.DecimalField(
        _("Birim maliyet"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    # --- İndirim / ikram ---
    discount_percent = models.DecimalField(
        _("İndirim (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    discount_reason = models.CharField(_("İndirim gerekçesi"), max_length=200, blank=True)
    is_comp = models.BooleanField(_("İkram"), default=False)
    discount_approval = models.ForeignKey(
        "accounts.ApprovalRequest",
        verbose_name=_("İndirim onayı"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discounted_lines",
    )

    # --- Durum ---
    seat_number = models.PositiveSmallIntegerField(
        _("Koltuk no"), null=True, blank=True, help_text=_("Hesap bölüştürmede kullanılır.")
    )
    course = models.PositiveSmallIntegerField(
        _("Servis sırası"), default=1, help_text=_("1=başlangıç, 2=ana yemek, 3=tatlı…")
    )
    special_instructions = models.CharField(_("Özel istek"), max_length=250, blank=True)
    is_voided = models.BooleanField(_("İptal"), default=False, db_index=True)
    void_reason = models.CharField(_("İptal gerekçesi"), max_length=200, blank=True)
    sent_at = models.DateTimeField(_("Gönderim zamanı"), null=True, blank=True)
    served_at = models.DateTimeField(_("Servis zamanı"), null=True, blank=True)

    class Meta:
        verbose_name = _("Adisyon satırı")
        verbose_name_plural = _("Adisyon satırları")
        ordering = ["course", "id"]

    def __str__(self) -> str:
        return f"{self.item_name} × {self.quantity:g}"

    # -- Mali hesaplar ------------------------------------------------------
    @property
    def gross_amount(self) -> Decimal:
        """İndirim öncesi satır tutarı."""
        return (self.quantity * self.unit_price).quantize(TWO_PLACES)

    @property
    def discount_amount(self) -> Decimal:
        """İndirim tutarı (ikram = %100)."""
        if self.is_comp:
            return self.gross_amount
        return (self.gross_amount * self.discount_percent / Decimal("100")).quantize(TWO_PLACES)

    @property
    def net_amount(self) -> Decimal:
        """KDV hariç net tutar."""
        return (self.gross_amount - self.discount_amount).quantize(TWO_PLACES)

    @property
    def tax_amount(self) -> Decimal:
        return (self.net_amount * self.tax_rate / Decimal("100")).quantize(TWO_PLACES)

    @property
    def total_amount(self) -> Decimal:
        """KDV dahil satır toplamı."""
        return (self.net_amount + self.tax_amount).quantize(TWO_PLACES)

    @property
    def cost_amount(self) -> Decimal:
        return (self.quantity * self.unit_cost).quantize(TWO_PLACES)

    @property
    def margin_amount(self) -> Decimal:
        return (self.net_amount - self.cost_amount).quantize(TWO_PLACES)


# ---------------------------------------------------------------------------
# Hazırlık fişleri (KOT) ve ekranlar (KDS)
# ---------------------------------------------------------------------------
class PrepTicket(TimeStampedModel):
    """Hazırlık fişi (Kitchen Order Ticket).

    Sipariş mutfağa gönderildiğinde istasyon başına bir fiş üretilir.
    Mutfak (KDS), bar ve sommelier ekranları aynı modeli farklı
    ``station`` değeriyle kullanır.
    """

    class Station(models.TextChoices):
        KITCHEN = "kitchen", _("Mutfak")
        BAR = "bar", _("Bar")
        WINE = "wine", _("Şarap / Sommelier")
        PASTRY = "pastry", _("Pastane")

    class Status(models.TextChoices):
        QUEUED = "queued", _("Sırada")
        PREPARING = "preparing", _("Hazırlanıyor")
        READY = "ready", _("Hazır")
        SERVED = "served", _("Servis edildi")
        CANCELLED = "cancelled", _("İptal")

    class Priority(models.IntegerChoices):
        LOW = 1, _("Düşük")
        NORMAL = 2, _("Normal")
        HIGH = 3, _("Yüksek")
        RUSH = 4, _("Acele")

    order = models.ForeignKey(
        Order, verbose_name=_("Adisyon"), on_delete=models.CASCADE, related_name="tickets"
    )
    ticket_number = models.CharField(_("Fiş no"), max_length=30, db_index=True)
    station = models.CharField(
        _("İstasyon"),
        max_length=20,
        choices=Station.choices,
        default=Station.KITCHEN,
        db_index=True,
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True
    )
    priority = models.PositiveSmallIntegerField(
        _("Öncelik"), choices=Priority.choices, default=Priority.NORMAL
    )
    course = models.PositiveSmallIntegerField(_("Servis sırası"), default=1)

    sent_at = models.DateTimeField(_("Gönderim"), default=timezone.now, db_index=True)
    started_at = models.DateTimeField(_("Başlama"), null=True, blank=True)
    ready_at = models.DateTimeField(_("Hazır"), null=True, blank=True)
    served_at = models.DateTimeField(_("Servis"), null=True, blank=True)

    target_minutes = models.PositiveSmallIntegerField(
        _("Hedef süre (dk)"),
        default=15,
        help_text=_("Bu süreyi aşan fişler ekranda kırmızı gösterilir."),
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Hazırlayan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prepared_tickets",
    )
    note = models.TextField(_("Not"), blank=True)

    class Meta:
        verbose_name = _("Hazırlık fişi")
        verbose_name_plural = _("Hazırlık fişleri")
        ordering = ["-priority", "sent_at"]
        indexes = [
            models.Index(fields=["station", "status", "sent_at"], name="ticket_station_status_idx"),
        ]
        permissions = [
            ("can_bump_ticket", _("Fişi ilerletebilir (bump)")),
            ("can_view_kitchen_display", _("Mutfak ekranını görebilir")),
            ("can_view_bar_display", _("Bar ekranını görebilir")),
            ("can_view_wine_display", _("Şarap ekranını görebilir")),
        ]

    def __str__(self) -> str:
        return f"{self.ticket_number} · {self.get_station_display()} · {self.get_status_display()}"

    @property
    def elapsed_minutes(self) -> int:
        end = self.ready_at or timezone.now()
        return int((end - self.sent_at).total_seconds() // 60)

    @property
    def is_overdue(self) -> bool:
        return (
            self.status in {self.Status.QUEUED, self.Status.PREPARING}
            and self.elapsed_minutes > self.target_minutes
        )

    @property
    def urgency_class(self) -> str:
        """KDS ekranındaki renk sınıfı."""
        if self.status == self.Status.READY:
            return "border-success"
        if self.is_overdue:
            return "border-danger"
        if self.elapsed_minutes > self.target_minutes * 0.7:
            return "border-warning"
        return "border-secondary"


class PrepTicketLine(TimeStampedModel):
    """Hazırlık fişindeki tek bir ürün."""

    ticket = models.ForeignKey(
        PrepTicket, verbose_name=_("Fiş"), on_delete=models.CASCADE, related_name="lines"
    )
    order_line = models.ForeignKey(
        OrderLine,
        verbose_name=_("Adisyon satırı"),
        on_delete=models.CASCADE,
        related_name="ticket_lines",
    )
    item_name = models.CharField(_("Ürün"), max_length=250)
    quantity = models.DecimalField(_("Adet"), max_digits=10, decimal_places=3)
    special_instructions = models.CharField(_("Özel istek"), max_length=250, blank=True)
    allergen_warning = models.CharField(_("Alerjen uyarısı"), max_length=250, blank=True)
    is_done = models.BooleanField(_("Tamamlandı"), default=False)

    class Meta:
        verbose_name = _("Fiş satırı")
        verbose_name_plural = _("Fiş satırları")
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.item_name} × {self.quantity:g}"


# ---------------------------------------------------------------------------
# Ödeme
# ---------------------------------------------------------------------------
class PaymentMethod(TimeStampedModel):
    """Ödeme yöntemi tanımı."""

    class Kind(models.TextChoices):
        CASH = "cash", _("Nakit")
        CARD = "card", _("Kredi / banka kartı")
        MEAL_CARD = "meal_card", _("Yemek kartı")
        TRANSFER = "transfer", _("Havale / EFT")
        VOUCHER = "voucher", _("Hediye çeki")
        LOYALTY = "loyalty", _("Sadakat puanı")
        ON_ACCOUNT = "on_account", _("Cari hesaba")
        OTHER = "other", _("Diğer")

    code = models.CharField(_("Kod"), max_length=30, unique=True)
    name = models.CharField(_("Ad"), max_length=100)
    kind = models.CharField(_("Tür"), max_length=20, choices=Kind.choices, default=Kind.CASH)
    requires_reference = models.BooleanField(_("Referans zorunlu"), default=False)
    opens_cash_drawer = models.BooleanField(_("Kasa çekmecesini açar"), default=False)
    commission_percent = models.DecimalField(
        _("Komisyon (%)"), max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    is_active = models.BooleanField(_("Etkin"), default=True)
    sort_order = models.PositiveSmallIntegerField(_("Sıra"), default=100)

    class Meta:
        verbose_name = _("Ödeme yöntemi")
        verbose_name_plural = _("Ödeme yöntemleri")
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Payment(TimeStampedModel):
    """Tahsilat kaydı.

    ÖNEMLİ: Bu sürümde gerçek ödeme altyapısı bağlanmamıştır. ``gateway_mode``
    alanı her zaman ``sandbox`` olarak kaydedilir ve hiçbir gerçek para
    hareketi gerçekleşmez. Canlı entegrasyon kullanıcı onayı gerektirir.
    """

    class GatewayMode(models.TextChoices):
        SANDBOX = "sandbox", _("Sandbox (gerçek işlem yok)")
        LIVE = "live", _("Canlı")

    order = models.ForeignKey(
        Order, verbose_name=_("Adisyon"), on_delete=models.PROTECT, related_name="payments"
    )
    method = models.ForeignKey(
        PaymentMethod, verbose_name=_("Yöntem"), on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.DecimalField(
        _("Tutar"), max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    tip_amount = models.DecimalField(
        _("Bahşiş"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    received_at = models.DateTimeField(_("Tahsilat zamanı"), default=timezone.now, db_index=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Tahsil eden"),
        on_delete=models.PROTECT,
        related_name="payments_received",
    )
    reference = models.CharField(_("Referans"), max_length=100, blank=True)
    gateway_mode = models.CharField(
        _("Ağ geçidi modu"),
        max_length=10,
        choices=GatewayMode.choices,
        default=GatewayMode.SANDBOX,
    )
    #: Bölünmüş hesapta hangi koltuk/gruba ait olduğu
    split_label = models.CharField(_("Bölüm etiketi"), max_length=60, blank=True)

    is_voided = models.BooleanField(_("İptal"), default=False, db_index=True)
    void_reason = models.CharField(_("İptal gerekçesi"), max_length=250, blank=True)
    void_approval = models.ForeignKey(
        "accounts.ApprovalRequest",
        verbose_name=_("İptal/iade onayı"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voided_payments",
    )

    class Meta:
        verbose_name = _("Ödeme")
        verbose_name_plural = _("Ödemeler")
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["-received_at", "is_voided"], name="payment_ts_void_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.order.number} · {self.method.name} · {self.amount}"

    @property
    def commission_amount(self) -> Decimal:
        return (self.amount * self.method.commission_percent / Decimal("100")).quantize(TWO_PLACES)

    @property
    def net_amount(self) -> Decimal:
        return (self.amount - self.commission_amount).quantize(TWO_PLACES)


class Refund(TimeStampedModel):
    """İade kaydı — her zaman bir onay talebine bağlıdır."""

    payment = models.ForeignKey(
        Payment, verbose_name=_("Ödeme"), on_delete=models.PROTECT, related_name="refunds"
    )
    amount = models.DecimalField(
        _("Tutar"), max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    reason = models.CharField(_("Gerekçe"), max_length=250)
    refunded_at = models.DateTimeField(_("İade zamanı"), default=timezone.now)
    refunded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("İadeyi yapan"),
        on_delete=models.PROTECT,
        related_name="refunds_issued",
    )
    approval = models.ForeignKey(
        "accounts.ApprovalRequest",
        verbose_name=_("Onay"),
        on_delete=models.PROTECT,
        related_name="refunds",
    )

    class Meta:
        verbose_name = _("İade")
        verbose_name_plural = _("İadeler")
        ordering = ["-refunded_at"]

    def __str__(self) -> str:
        return f"{self.payment.order.number} · iade {self.amount}"


# ---------------------------------------------------------------------------
# Gün sonu ve çevrimdışı senkronizasyon
# ---------------------------------------------------------------------------
class BusinessDay(TimeStampedModel):
    """İş günü ve gün sonu kapanışı."""

    class Status(models.TextChoices):
        OPEN = "open", _("Açık")
        CLOSING = "closing", _("Kapanış yapılıyor")
        CLOSED = "closed", _("Kapandı")

    business_date = models.DateField(_("İş günü"), unique=True, db_index=True)
    opened_at = models.DateTimeField(_("Açılış"), default=timezone.now)
    closed_at = models.DateTimeField(_("Kapanış"), null=True, blank=True)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.OPEN
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Açan"),
        on_delete=models.PROTECT,
        related_name="business_days_opened",
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Kapatan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_days_closed",
    )

    # --- Kapanış özeti (dondurulmuş) ---
    total_orders = models.PositiveIntegerField(_("Adisyon sayısı"), default=0)
    total_guests = models.PositiveIntegerField(_("Misafir sayısı"), default=0)
    gross_sales = models.DecimalField(_("Brüt satış"), max_digits=14, decimal_places=2, default=0)
    discounts = models.DecimalField(_("İndirimler"), max_digits=14, decimal_places=2, default=0)
    net_sales = models.DecimalField(_("Net satış"), max_digits=14, decimal_places=2, default=0)
    tax_collected = models.DecimalField(
        _("Tahsil edilen KDV"), max_digits=14, decimal_places=2, default=0
    )
    cash_expected = models.DecimalField(
        _("Beklenen nakit"), max_digits=14, decimal_places=2, default=0
    )
    cash_counted = models.DecimalField(
        _("Sayılan nakit"), max_digits=14, decimal_places=2, default=0
    )
    payment_breakdown = models.JSONField(_("Ödeme dağılımı"), default=dict, blank=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("İş günü")
        verbose_name_plural = _("İş günleri")
        ordering = ["-business_date"]

    def __str__(self) -> str:
        return f"{self.business_date:%d.%m.%Y} · {self.get_status_display()}"

    @property
    def cash_variance(self) -> Decimal:
        return (self.cash_counted - self.cash_expected).quantize(TWO_PLACES)


class OfflineOperation(TimeStampedModel):
    """Çevrimdışı çalışırken kaydedilen ve senkronizasyon bekleyen işlem.

    Wine House yerel-öncelikli çalışır: uygulama ve veritabanı aynı makinededir,
    bu nedenle internet kesildiğinde tüm temel işlevler çalışmaya devam eder.
    Bu model, *ikinci bir terminalin* veya bulut yedeğinin bağlantısı
    koptuğunda biriken işlemleri güvenli biçimde kuyruğa alır.

    DURUM: Çok terminalli senkronizasyon **Deneysel** olarak işaretlidir.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Bekliyor")
        SYNCED = "synced", _("Eşitlendi")
        CONFLICT = "conflict", _("Çakışma")
        FAILED = "failed", _("Başarısız")

    operation_type = models.CharField(_("İşlem türü"), max_length=60, db_index=True)
    payload = models.JSONField(_("Veri"), default=dict)
    device_id = models.CharField(_("Cihaz kimliği"), max_length=80, db_index=True)
    created_offline_at = models.DateTimeField(
        _("Çevrimdışı oluşturma zamanı"), default=timezone.now
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    synced_at = models.DateTimeField(_("Eşitlenme zamanı"), null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(_("Deneme sayısı"), default=0)
    last_error = models.TextField(_("Son hata"), blank=True)
    #: İdempotans anahtarı — aynı işlemin iki kez uygulanmasını önler
    idempotency_key = models.CharField(
        _("İdempotans anahtarı"), max_length=80, unique=True, db_index=True
    )

    class Meta:
        verbose_name = _("Çevrimdışı işlem")
        verbose_name_plural = _("Çevrimdışı işlemler")
        ordering = ["created_offline_at"]

    def __str__(self) -> str:
        return f"{self.operation_type} · {self.get_status_display()}"
