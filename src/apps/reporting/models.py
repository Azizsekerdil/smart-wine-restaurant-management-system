"""Raporlama modelleri: rapor tanımı, koşum kaydı, günlük özet ve tahmin."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class ReportDefinition(TimeStampedModel):
    """Kayıtlı rapor tanımı.

    Rapor mantığı ``apps.reporting.reports`` içindeki kayıtlı üreteçlerde
    bulunur; bu model yalnızca hangi raporun kimlere görünür olduğunu ve
    varsayılan parametrelerini tutar.
    """

    class Category(models.TextChoices):
        SALES = "sales", _("Satış")
        PRODUCT = "product", _("Ürün")
        WINE = "wine", _("Şarap")
        INVENTORY = "inventory", _("Stok")
        PURCHASING = "purchasing", _("Satın alma")
        STAFF = "staff", _("Personel")
        CUSTOMER = "customer", _("Müşteri")
        OPERATIONS = "operations", _("Operasyon")
        AI = "ai", _("Yapay zekâ")
        FINANCE = "finance", _("Mali")

    code = models.SlugField(_("Kod"), max_length=80, unique=True, db_index=True)
    name_tr = models.CharField(_("Ad (TR)"), max_length=200)
    name_en = models.CharField(_("Ad (EN)"), max_length=200, blank=True)
    description = models.TextField(_("Açıklama"), blank=True)
    category = models.CharField(_("Kategori"), max_length=20, choices=Category.choices)
    #: Bu raporu görebilecek rol kodları. Boş = izin sistemine bırakılır.
    allowed_roles = models.JSONField(_("İzinli roller"), default=list, blank=True)
    default_parameters = models.JSONField(_("Varsayılan parametreler"), default=dict, blank=True)
    supports_pdf = models.BooleanField(_("PDF desteği"), default=True)
    supports_excel = models.BooleanField(_("Excel desteği"), default=True)
    supports_csv = models.BooleanField(_("CSV desteği"), default=True)
    is_experimental = models.BooleanField(
        _("Deneysel"),
        default=False,
        help_text=_("Arayüzde 'Deneysel' rozetiyle gösterilir."),
    )
    is_active = models.BooleanField(_("Etkin"), default=True)
    sort_order = models.PositiveSmallIntegerField(_("Sıra"), default=100)

    class Meta:
        verbose_name = _("Rapor tanımı")
        verbose_name_plural = _("Rapor tanımları")
        ordering = ["category", "sort_order", "name_tr"]
        permissions = [
            ("can_export_report", _("Rapor dışa aktarabilir")),
            ("can_view_financial_report", _("Mali raporları görebilir")),
            ("can_view_staff_report", _("Personel raporlarını görebilir")),
        ]

    def __str__(self) -> str:
        return self.name_tr

    def name_for(self, language: str) -> str:
        return self.name_en if language == "en" and self.name_en else self.name_tr


class ReportRun(TimeStampedModel):
    """Rapor koşum kaydı — kim, ne zaman, hangi parametrelerle çalıştırdı."""

    class Format(models.TextChoices):
        HTML = "html", _("Ekran")
        PDF = "pdf", _("PDF")
        EXCEL = "xlsx", _("Excel")
        CSV = "csv", _("CSV")

    class Status(models.TextChoices):
        RUNNING = "running", _("Çalışıyor")
        SUCCESS = "success", _("Tamamlandı")
        FAILED = "failed", _("Başarısız")

    definition = models.ForeignKey(
        ReportDefinition, verbose_name=_("Rapor"), on_delete=models.PROTECT, related_name="runs"
    )
    run_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Çalıştıran"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="report_runs",
    )
    parameters = models.JSONField(_("Parametreler"), default=dict, blank=True)
    output_format = models.CharField(
        _("Biçim"), max_length=10, choices=Format.choices, default=Format.HTML
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.RUNNING
    )
    row_count = models.PositiveIntegerField(_("Satır sayısı"), default=0)
    duration_ms = models.PositiveIntegerField(_("Süre (ms)"), default=0)
    file_path = models.CharField(_("Dosya yolu"), max_length=500, blank=True)
    error_message = models.TextField(_("Hata"), blank=True)

    class Meta:
        verbose_name = _("Rapor koşumu")
        verbose_name_plural = _("Rapor koşumları")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.definition.name_tr} · {self.created_at:%d.%m.%Y %H:%M}"


class DailySalesSnapshot(TimeStampedModel):
    """Günlük satış özeti.

    Gün sonu kapanışında hesaplanır ve *dondurulur*. Raporlar bu tablodan
    okunduğu için geçmiş dönem raporları her zaman aynı sonucu verir.
    """

    business_date = models.DateField(_("İş günü"), unique=True, db_index=True)

    order_count = models.PositiveIntegerField(_("Adisyon"), default=0)
    guest_count = models.PositiveIntegerField(_("Misafir"), default=0)
    gross_sales = models.DecimalField(_("Brüt satış"), max_digits=14, decimal_places=2, default=0)
    discounts = models.DecimalField(_("İndirim"), max_digits=14, decimal_places=2, default=0)
    comps = models.DecimalField(_("İkram"), max_digits=14, decimal_places=2, default=0)
    service_charge = models.DecimalField(
        _("Servis bedeli"), max_digits=14, decimal_places=2, default=0
    )
    tax = models.DecimalField(_("KDV"), max_digits=14, decimal_places=2, default=0)
    net_sales = models.DecimalField(_("Net satış"), max_digits=14, decimal_places=2, default=0)
    cost_of_sales = models.DecimalField(
        _("Satış maliyeti"), max_digits=14, decimal_places=2, default=0
    )

    food_sales = models.DecimalField(_("Yemek satışı"), max_digits=14, decimal_places=2, default=0)
    beverage_sales = models.DecimalField(
        _("İçecek satışı"), max_digits=14, decimal_places=2, default=0
    )
    wine_bottle_sales = models.DecimalField(
        _("Şişe şarap satışı"), max_digits=14, decimal_places=2, default=0
    )
    wine_glass_sales = models.DecimalField(
        _("Kadeh şarap satışı"), max_digits=14, decimal_places=2, default=0
    )

    bottles_sold = models.PositiveIntegerField(_("Satılan şişe"), default=0)
    glasses_sold = models.PositiveIntegerField(_("Satılan kadeh"), default=0)

    void_count = models.PositiveIntegerField(_("İptal sayısı"), default=0)
    void_amount = models.DecimalField(_("İptal tutarı"), max_digits=14, decimal_places=2, default=0)
    refund_amount = models.DecimalField(
        _("İade tutarı"), max_digits=14, decimal_places=2, default=0
    )
    waste_cost = models.DecimalField(_("Fire maliyeti"), max_digits=14, decimal_places=2, default=0)

    table_turns = models.DecimalField(
        _("Masa devir hızı"), max_digits=6, decimal_places=2, default=0
    )
    reservation_count = models.PositiveIntegerField(_("Rezervasyon"), default=0)
    no_show_count = models.PositiveIntegerField(_("Gelmeyen"), default=0)

    payment_breakdown = models.JSONField(_("Ödeme dağılımı"), default=dict, blank=True)

    class Meta:
        verbose_name = _("Günlük satış özeti")
        verbose_name_plural = _("Günlük satış özetleri")
        ordering = ["-business_date"]

    def __str__(self) -> str:
        return f"{self.business_date:%d.%m.%Y} · {self.net_sales}"

    @property
    def average_check(self) -> Decimal:
        if not self.order_count:
            return Decimal("0.00")
        return (self.net_sales / self.order_count).quantize(Decimal("0.01"))

    @property
    def average_per_guest(self) -> Decimal:
        if not self.guest_count:
            return Decimal("0.00")
        return (self.net_sales / self.guest_count).quantize(Decimal("0.01"))

    @property
    def gross_margin_percent(self) -> Decimal:
        if not self.net_sales:
            return Decimal("0.00")
        return ((self.net_sales - self.cost_of_sales) / self.net_sales * 100).quantize(
            Decimal("0.01")
        )

    @property
    def no_show_rate(self) -> Decimal:
        if not self.reservation_count:
            return Decimal("0.00")
        return (Decimal(self.no_show_count) / self.reservation_count * 100).quantize(
            Decimal("0.01")
        )

    @property
    def wine_share_percent(self) -> Decimal:
        """Şarabın toplam satış içindeki payı."""
        if not self.net_sales:
            return Decimal("0.00")
        wine_total = self.wine_bottle_sales + self.wine_glass_sales
        return (wine_total / self.net_sales * 100).quantize(Decimal("0.01"))


class SalesForecast(TimeStampedModel):
    """Satış / talep tahmini.

    DURUM: **Deneysel.** Tahminler istatistiksel taban çizgisi (hareketli
    ortalama + haftanın günü mevsimselliği) ile üretilir; yapay zekâ
    sağlayıcısı yalnızca yorum katmanı ekler. Hiçbir tahmin otomatik olarak
    sipariş oluşturmaz — yalnızca öneri üretir.
    """

    class Method(models.TextChoices):
        MOVING_AVERAGE = "moving_average", _("Hareketli ortalama")
        WEEKDAY_SEASONAL = "weekday_seasonal", _("Haftanın günü mevsimselliği")
        AI_ASSISTED = "ai_assisted", _("Yapay zekâ destekli")

    target_date = models.DateField(_("Hedef tarih"), db_index=True)
    method = models.CharField(
        _("Yöntem"), max_length=30, choices=Method.choices, default=Method.WEEKDAY_SEASONAL
    )
    predicted_covers = models.PositiveIntegerField(_("Tahmini misafir"), default=0)
    predicted_sales = models.DecimalField(
        _("Tahmini satış"), max_digits=14, decimal_places=2, default=0
    )
    confidence_low = models.DecimalField(_("Alt sınır"), max_digits=14, decimal_places=2, default=0)
    confidence_high = models.DecimalField(
        _("Üst sınır"), max_digits=14, decimal_places=2, default=0
    )
    sample_days = models.PositiveSmallIntegerField(_("Örneklem (gün)"), default=0)
    actual_sales = models.DecimalField(
        _("Gerçekleşen satış"), max_digits=14, decimal_places=2, null=True, blank=True
    )
    ai_commentary = models.TextField(_("Yapay zekâ yorumu"), blank=True)
    generated_at = models.DateTimeField(_("Üretim zamanı"), default=timezone.now)

    class Meta:
        verbose_name = _("Satış tahmini")
        verbose_name_plural = _("Satış tahminleri")
        ordering = ["-target_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["target_date", "method"], name="uniq_forecast_date_method"
            )
        ]

    def __str__(self) -> str:
        return f"{self.target_date:%d.%m.%Y} · {self.predicted_sales}"

    @property
    def error_percent(self) -> Decimal | None:
        """Gerçekleşen sonuca göre tahmin hatası (%)."""
        if self.actual_sales is None or not self.actual_sales:
            return None
        return (abs(self.predicted_sales - self.actual_sales) / self.actual_sales * 100).quantize(
            Decimal("0.01")
        )
