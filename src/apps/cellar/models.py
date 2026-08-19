"""Dijital şarap kavı modelleri.

Kapsam:
  * Şarap kataloğu (üretici, bölge, apelasyon, üzüm bileşimi, rekolte)
  * Fiziksel yerleşim (kav, dolap, raf, bölme) ve sıcaklık/nem kayıtları
  * Parti (lot) bazlı şişe stoğu ve maliyeti
  * Açılmış şişe takibi, kadeh servisi ve verim
  * Şarap kusurları (mantar hatası, oksidasyon, dökülme)
  * Tadım notları, uzman/müşteri puanları, içim aralığı
  * Yemek ve peynir eşleştirmeleri, şarap uçuşları, tadım etkinlikleri
  * Şarap kulübü ve özel kav müşterileri

SORUMLU TÜKETİM: Bu modül alkollü içecek yönetir. Arayüzdeki her öneri
ekranında sorumlu tüketim uyarısı gösterilir ve sistem hiçbir koşulda
sağlık/tıbbi iddia üretmez.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import SoftDeleteModel, TimeStampedModel

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

#: Standart şişe hacmi (ml)
STANDARD_BOTTLE_ML = 750

#: Sorumlu tüketim uyarısı — arayüzde şarap önerisi gösterilen her yerde kullanılır
RESPONSIBLE_CONSUMPTION_NOTICE_TR = (
    "Alkollü içecekler 18 yaşından küçüklere satılamaz. Aşırı tüketim zararlıdır. "
    "Araç kullanacaksanız alkol almayınız."
)
RESPONSIBLE_CONSUMPTION_NOTICE_EN = (
    "Alcoholic beverages may not be sold to persons under 18. Excessive consumption "
    "is harmful. Do not drink and drive."
)


# ---------------------------------------------------------------------------
# Coğrafya ve üzüm
# ---------------------------------------------------------------------------
class WineRegion(TimeStampedModel):
    """Coğrafi hiyerarşi: ülke › bölge › alt bölge › apelasyon."""

    class Level(models.TextChoices):
        COUNTRY = "country", _("Ülke")
        REGION = "region", _("Bölge")
        SUBREGION = "subregion", _("Alt bölge")
        APPELLATION = "appellation", _("Apelasyon")
        VINEYARD = "vineyard", _("Bağ")

    name = models.CharField(_("Ad"), max_length=150, db_index=True)
    name_en = models.CharField(_("Ad (EN)"), max_length=150, blank=True)
    level = models.CharField(_("Kademe"), max_length=20, choices=Level.choices)
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Üst bölge"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    country_code = models.CharField(_("Ülke kodu"), max_length=2, blank=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Şarap bölgesi")
        verbose_name_plural = _("Şarap bölgeleri")
        ordering = ["level", "name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "parent"], name="uniq_region_name_parent")
        ]

    def __str__(self) -> str:
        return self.full_path

    @property
    def full_path(self) -> str:
        """``Fransa › Bordeaux › Pauillac`` biçiminde tam yol."""
        parts, node, guard = [], self, 0
        while node is not None and guard < 10:
            parts.append(node.name)
            node = node.parent
            guard += 1
        return " › ".join(reversed(parts))


class GrapeVariety(TimeStampedModel):
    """Üzüm çeşidi."""

    class Color(models.TextChoices):
        RED = "red", _("Siyah / Kırmızı")
        WHITE = "white", _("Beyaz")
        OTHER = "other", _("Diğer")

    name = models.CharField(_("Ad"), max_length=120, unique=True, db_index=True)
    name_en = models.CharField(_("Ad (EN)"), max_length=120, blank=True)
    color = models.CharField(_("Renk"), max_length=10, choices=Color.choices, default=Color.RED)
    synonyms = models.CharField(
        _("Eş adlar"), max_length=300, blank=True, help_text=_("Virgülle ayırın.")
    )
    origin = models.ForeignKey(
        WineRegion,
        verbose_name=_("Köken"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="native_grapes",
    )
    is_indigenous_turkish = models.BooleanField(_("Yerli Türk çeşidi"), default=False)
    description = models.TextField(_("Açıklama"), blank=True)

    class Meta:
        verbose_name = _("Üzüm çeşidi")
        verbose_name_plural = _("Üzüm çeşitleri")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class WineProducer(TimeStampedModel):
    """Şarap üreticisi / şaraphane."""

    name = models.CharField(_("Ad"), max_length=200, db_index=True)
    region = models.ForeignKey(
        WineRegion,
        verbose_name=_("Bölge"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="producers",
    )
    website = models.URLField(_("Web sitesi"), blank=True)
    founded_year = models.PositiveSmallIntegerField(_("Kuruluş yılı"), null=True, blank=True)
    is_organic = models.BooleanField(_("Organik"), default=False)
    is_biodynamic = models.BooleanField(_("Biyodinamik"), default=False)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Üretici")
        verbose_name_plural = _("Üreticiler")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "region"], name="uniq_producer_region")
        ]

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Şarap kataloğu
# ---------------------------------------------------------------------------
class Wine(SoftDeleteModel):
    """Kavdaki bir şarap kaydı (üretici + etiket + rekolte)."""

    class WineType(models.TextChoices):
        RED = "red", _("Kırmızı")
        WHITE = "white", _("Beyaz")
        ROSE = "rose", _("Roze")
        SPARKLING = "sparkling", _("Köpüklü")
        ORANGE = "orange", _("Turuncu / Amber")
        DESSERT = "dessert", _("Tatlı")
        FORTIFIED = "fortified", _("Fortifiye")

    class Sweetness(models.TextChoices):
        BONE_DRY = "bone_dry", _("Çok sek")
        DRY = "dry", _("Sek")
        OFF_DRY = "off_dry", _("Yarı sek")
        MEDIUM_SWEET = "medium_sweet", _("Yarı tatlı")
        SWEET = "sweet", _("Tatlı")

    class BottleSize(models.IntegerChoices):
        PICCOLO = 187, _("Piccolo (187 ml)")
        HALF = 375, _("Yarım (375 ml)")
        STANDARD = 750, _("Standart (750 ml)")
        MAGNUM = 1500, _("Magnum (1.5 L)")
        DOUBLE_MAGNUM = 3000, _("Çift Magnum (3 L)")
        JEROBOAM = 5000, _("Jeroboam (5 L)")

    # --- Kimlik ---
    sku = models.CharField(_("Stok kodu"), max_length=40, unique=True, db_index=True)
    name = models.CharField(_("Şarap adı"), max_length=250, db_index=True)
    producer = models.ForeignKey(
        WineProducer, verbose_name=_("Üretici"), on_delete=models.PROTECT, related_name="wines"
    )
    vineyard = models.CharField(_("Bağ"), max_length=200, blank=True)
    region = models.ForeignKey(
        WineRegion,
        verbose_name=_("Bölge / Apelasyon"),
        on_delete=models.PROTECT,
        related_name="wines",
    )
    vintage = models.PositiveSmallIntegerField(
        _("Rekolte"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1800), MaxValueValidator(2100)],
        help_text=_("Boş bırakılırsa NV (rekoltesiz) kabul edilir."),
    )

    # --- Sınıflandırma ---
    wine_type = models.CharField(_("Tür"), max_length=20, choices=WineType.choices, db_index=True)
    sweetness = models.CharField(
        _("Tatlılık"), max_length=20, choices=Sweetness.choices, default=Sweetness.DRY
    )
    alcohol_percent = models.DecimalField(
        _("Alkol (%)"),
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(30)],
    )
    bottle_size_ml = models.PositiveIntegerField(
        _("Şişe hacmi (ml)"), choices=BottleSize.choices, default=BottleSize.STANDARD
    )
    is_organic = models.BooleanField(_("Organik"), default=False)
    is_vegan = models.BooleanField(_("Vegan"), default=False)
    contains_sulfites = models.BooleanField(_("Sülfit içerir"), default=True)

    # --- Servis ---
    serving_temp_min_c = models.DecimalField(
        _("Servis sıcaklığı min (°C)"), max_digits=4, decimal_places=1, null=True, blank=True
    )
    serving_temp_max_c = models.DecimalField(
        _("Servis sıcaklığı maks (°C)"), max_digits=4, decimal_places=1, null=True, blank=True
    )
    decant_minutes = models.PositiveSmallIntegerField(
        _("Dekantasyon (dk)"), default=0, help_text=_("0 = dekantasyon gerekmez.")
    )
    glass_type = models.CharField(_("Kadeh tipi"), max_length=80, blank=True)

    # --- Tadım profili (0-5 ölçeği) ---
    body = models.PositiveSmallIntegerField(
        _("Gövde"), default=3, validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    acidity = models.PositiveSmallIntegerField(
        _("Asidite"), default=3, validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    tannin = models.PositiveSmallIntegerField(
        _("Tanen"), default=3, validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    sweetness_level = models.PositiveSmallIntegerField(
        _("Tatlılık seviyesi"), default=0, validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    aroma_profile = models.JSONField(
        _("Aroma profili"),
        default=list,
        blank=True,
        help_text=_("Örn: ['kiraz', 'vanilya', 'deri']"),
    )

    # --- İçim aralığı ---
    drink_from_year = models.PositiveSmallIntegerField(_("İçim başlangıcı"), null=True, blank=True)
    drink_until_year = models.PositiveSmallIntegerField(_("İçim bitişi"), null=True, blank=True)
    peak_year = models.PositiveSmallIntegerField(_("Zirve yılı"), null=True, blank=True)

    # --- Ticari ---
    purchase_price = models.DecimalField(
        _("Alış fiyatı"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    bottle_price = models.DecimalField(
        _("Şişe satış fiyatı"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    glass_price = models.DecimalField(
        _("Kadeh satış fiyatı"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    glass_pour_ml = models.PositiveSmallIntegerField(
        _("Kadeh servis hacmi (ml)"),
        default=150,
        validators=[MinValueValidator(20), MaxValueValidator(500)],
    )
    sold_by_glass = models.BooleanField(_("Kadeh satışı yapılır"), default=False)

    # --- Tanımlama ---
    barcode = models.CharField(_("Barkod"), max_length=64, blank=True, db_index=True)
    internal_qr = models.CharField(_("İç QR kodu"), max_length=64, blank=True, db_index=True)
    label_image = models.ImageField(
        _("Etiket fotoğrafı"), upload_to="wines/", blank=True, null=True
    )

    # --- Durum ---
    is_active = models.BooleanField(_("Etkin"), default=True, db_index=True)
    is_on_wine_list = models.BooleanField(_("Şarap listesinde"), default=True)
    minimum_bottles = models.PositiveIntegerField(
        _("Minimum şişe"), default=0, help_text=_("Bu sayının altına düşünce uyarı üretilir.")
    )
    tasting_notes_house = models.TextField(_("İşletme tadım notu"), blank=True)
    food_pairing_summary = models.TextField(_("Yemek uyumu özeti"), blank=True)

    class Meta:
        verbose_name = _("Şarap")
        verbose_name_plural = _("Şaraplar")
        ordering = ["producer__name", "name", "-vintage"]
        indexes = [
            models.Index(fields=["wine_type", "is_active"], name="wine_type_active_idx"),
            models.Index(fields=["vintage"], name="wine_vintage_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["producer", "name", "vintage", "bottle_size_ml"],
                name="uniq_wine_producer_name_vintage_size",
            )
        ]
        permissions = [
            ("can_open_bottle", _("Şişe açabilir")),
            ("can_pour_glass", _("Kadeh servis edebilir")),
            ("can_record_wine_fault", _("Şarap kusuru kaydedebilir")),
            ("can_manage_cellar_layout", _("Kav yerleşimini yönetebilir")),
            ("can_view_cellar_valuation", _("Kav değerlemesini görebilir")),
        ]

    def __str__(self) -> str:
        vintage = self.vintage or "NV"
        return f"{self.producer.name} · {self.name} {vintage}"

    # -- Hesaplanan özellikler ---------------------------------------------
    @property
    def display_vintage(self) -> str:
        return str(self.vintage) if self.vintage else "NV"

    @property
    def bottles_on_hand(self) -> int:
        """Açılmamış şişe adedi (tüm partiler)."""
        return sum(lot.bottles_remaining for lot in self.lots.filter(is_deleted=False))

    @property
    def glasses_available(self) -> int:
        """Açık şişelerden servis edilebilecek kadeh sayısı."""
        pour = self.glass_pour_ml or 150
        total_ml = sum(
            opening.remaining_ml
            for opening in self.bottle_openings.filter(status=BottleOpening.Status.OPEN)
        )
        return int(total_ml // pour)

    @property
    def theoretical_glasses_per_bottle(self) -> int:
        """Bir şişeden çıkması beklenen kadeh sayısı."""
        pour = self.glass_pour_ml or 150
        return int(self.bottle_size_ml // pour)

    @property
    def stock_value(self) -> Decimal:
        """Eldeki şişelerin maliyet değeri."""
        total = Decimal("0.00")
        for lot in self.lots.filter(is_deleted=False):
            total += lot.bottles_remaining * lot.unit_cost
        return total.quantize(Decimal("0.01"))

    @property
    def bottle_margin_percent(self) -> Decimal:
        """Şişe satışındaki brüt marj (%)."""
        if not self.bottle_price:
            return Decimal("0.00")
        cost = self.purchase_price or Decimal("0.00")
        return (((self.bottle_price - cost) / self.bottle_price) * 100).quantize(Decimal("0.01"))

    @property
    def is_below_minimum(self) -> bool:
        return self.minimum_bottles > 0 and self.bottles_on_hand < self.minimum_bottles

    def drink_window_status(self, today: date | None = None) -> str:
        """İçim aralığına göre durum kodu döndürür.

        Dönen değerler: ``unknown``, ``too_young``, ``ready``, ``peak``,
        ``drink_soon``, ``past_peak``.
        """
        today = today or timezone.localdate()
        year = today.year
        if not self.drink_from_year and not self.drink_until_year:
            return "unknown"
        if self.drink_from_year and year < self.drink_from_year:
            return "too_young"
        if self.drink_until_year and year > self.drink_until_year:
            return "past_peak"
        if self.peak_year and year == self.peak_year:
            return "peak"
        if self.drink_until_year and (self.drink_until_year - year) <= 1:
            return "drink_soon"
        return "ready"

    def drink_window_label(self, today: date | None = None) -> str:
        """İçim aralığı durumunun okunur karşılığı."""
        return {
            "unknown": _("İçim aralığı belirtilmemiş"),
            "too_young": _("Erken — beklemeye devam"),
            "ready": _("İçilebilir"),
            "peak": _("Zirvede"),
            "drink_soon": _("Yakında tüketilmeli"),
            "past_peak": _("Zirveyi geçmiş — kontrol edin"),
        }[self.drink_window_status(today)]

    @property
    def serving_temp_display(self) -> str:
        if self.serving_temp_min_c is None or self.serving_temp_max_c is None:
            return "—"
        return f"{self.serving_temp_min_c:.0f}–{self.serving_temp_max_c:.0f} °C"

    @property
    def grape_summary(self) -> str:
        """``%60 Öküzgözü, %40 Boğazkere`` biçiminde bileşim."""
        parts = []
        for composition in self.grape_compositions.select_related("grape").order_by("-percentage"):
            if composition.percentage:
                parts.append(f"%{composition.percentage:g} {composition.grape.name}")
            else:
                parts.append(composition.grape.name)
        return ", ".join(parts)


class WineGrapeComposition(TimeStampedModel):
    """Şarabın üzüm bileşimi ve oranları."""

    wine = models.ForeignKey(
        Wine, verbose_name=_("Şarap"), on_delete=models.CASCADE, related_name="grape_compositions"
    )
    grape = models.ForeignKey(
        GrapeVariety, verbose_name=_("Üzüm"), on_delete=models.PROTECT, related_name="wines"
    )
    percentage = models.DecimalField(
        _("Oran (%)"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        verbose_name = _("Üzüm bileşimi")
        verbose_name_plural = _("Üzüm bileşimleri")
        ordering = ["-percentage"]
        constraints = [models.UniqueConstraint(fields=["wine", "grape"], name="uniq_wine_grape")]

    def __str__(self) -> str:
        if self.percentage:
            return f"{self.grape.name} %{self.percentage:g}"
        return self.grape.name


# ---------------------------------------------------------------------------
# Fiziksel yerleşim ve saklama koşulları
# ---------------------------------------------------------------------------
class WineStorageLocation(TimeStampedModel):
    """Kav yerleşimi: kav › dolap › raf › bölme."""

    class LocationType(models.TextChoices):
        CELLAR = "cellar", _("Kav")
        CABINET = "cabinet", _("Dolap")
        RACK = "rack", _("Raf")
        BIN = "bin", _("Bölme")
        DISPLAY = "display", _("Vitrin")
        SERVICE = "service", _("Servis dolabı")

    code = models.CharField(_("Kod"), max_length=40, unique=True, db_index=True)
    name = models.CharField(_("Ad"), max_length=150)
    location_type = models.CharField(
        _("Tür"), max_length=20, choices=LocationType.choices, default=LocationType.RACK
    )
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Üst konum"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    capacity_bottles = models.PositiveIntegerField(_("Kapasite (şişe)"), default=0)

    # --- Hedef saklama koşulları ---
    target_temp_c = models.DecimalField(
        _("Hedef sıcaklık (°C)"), max_digits=4, decimal_places=1, default=Decimal("13.0")
    )
    temp_tolerance_c = models.DecimalField(
        _("Sıcaklık toleransı (±°C)"), max_digits=3, decimal_places=1, default=Decimal("2.0")
    )
    target_humidity_percent = models.PositiveSmallIntegerField(
        _("Hedef nem (%)"), default=70, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    humidity_tolerance_percent = models.PositiveSmallIntegerField(
        _("Nem toleransı (±%)"), default=10
    )
    is_active = models.BooleanField(_("Etkin"), default=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Kav konumu")
        verbose_name_plural = _("Kav konumları")
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"

    @property
    def full_path(self) -> str:
        parts, node, guard = [], self, 0
        while node is not None and guard < 8:
            parts.append(node.code)
            node = node.parent
            guard += 1
        return " / ".join(reversed(parts))

    @property
    def bottles_stored(self) -> int:
        return sum(lot.bottles_remaining for lot in self.lots.filter(is_deleted=False))

    @property
    def occupancy_percent(self) -> Decimal:
        if not self.capacity_bottles:
            return Decimal("0.00")
        return (Decimal(self.bottles_stored) / Decimal(self.capacity_bottles) * 100).quantize(
            Decimal("0.01")
        )

    def latest_reading(self) -> StorageReading | None:
        return self.readings.order_by("-recorded_at").first()


class StorageReading(TimeStampedModel):
    """Kav sıcaklık ve nem ölçümü.

    Ölçüm el ile girilebilir veya ileride bir sensör entegrasyonuyla
    beslenebilir (``source`` alanı bunu ayırt eder).
    """

    class Source(models.TextChoices):
        MANUAL = "manual", _("El ile")
        SENSOR = "sensor", _("Sensör")
        IMPORT = "import", _("İçe aktarım")

    location = models.ForeignKey(
        WineStorageLocation,
        verbose_name=_("Konum"),
        on_delete=models.CASCADE,
        related_name="readings",
    )
    recorded_at = models.DateTimeField(_("Ölçüm zamanı"), default=timezone.now, db_index=True)
    temperature_c = models.DecimalField(_("Sıcaklık (°C)"), max_digits=5, decimal_places=2)
    humidity_percent = models.DecimalField(
        _("Nem (%)"), max_digits=5, decimal_places=2, null=True, blank=True
    )
    source = models.CharField(
        _("Kaynak"), max_length=20, choices=Source.choices, default=Source.MANUAL
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Kaydeden"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storage_readings",
    )
    note = models.CharField(_("Not"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("Saklama ölçümü")
        verbose_name_plural = _("Saklama ölçümleri")
        ordering = ["-recorded_at"]

    def __str__(self) -> str:
        return f"{self.location.code} · {self.temperature_c}°C · {self.recorded_at:%d.%m.%Y %H:%M}"

    @property
    def is_temperature_out_of_range(self) -> bool:
        target = self.location.target_temp_c
        tolerance = self.location.temp_tolerance_c
        return abs(self.temperature_c - target) > tolerance

    @property
    def is_humidity_out_of_range(self) -> bool:
        if self.humidity_percent is None:
            return False
        target = Decimal(self.location.target_humidity_percent)
        tolerance = Decimal(self.location.humidity_tolerance_percent)
        return abs(self.humidity_percent - target) > tolerance

    @property
    def has_alert(self) -> bool:
        return self.is_temperature_out_of_range or self.is_humidity_out_of_range


# ---------------------------------------------------------------------------
# Parti (lot) bazlı şişe stoğu
# ---------------------------------------------------------------------------
class BottleLot(SoftDeleteModel):
    """Tek bir satın alma partisine ait şişeler.

    FIFO/FEFO çıkışı bu model üzerinden yapılır: en eski alınan (veya en
    erken tüketilmesi gereken) parti önce kullanılır.
    """

    wine = models.ForeignKey(
        Wine, verbose_name=_("Şarap"), on_delete=models.PROTECT, related_name="lots"
    )
    lot_code = models.CharField(_("Parti kodu"), max_length=60, db_index=True)
    supplier = models.ForeignKey(
        "inventory.Supplier",
        verbose_name=_("Tedarikçi"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wine_lots",
    )
    location = models.ForeignKey(
        WineStorageLocation,
        verbose_name=_("Konum"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lots",
    )
    received_on = models.DateField(_("Giriş tarihi"), default=timezone.localdate, db_index=True)
    best_before = models.DateField(
        _("Tüketim önerisi tarihi"),
        null=True,
        blank=True,
        help_text=_("FEFO sıralaması bu tarihe göre yapılır."),
    )
    bottles_received = models.PositiveIntegerField(_("Giren şişe"), default=0)
    bottles_remaining = models.PositiveIntegerField(_("Kalan şişe"), default=0, db_index=True)
    unit_cost = models.DecimalField(
        _("Birim maliyet"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    invoice_reference = models.CharField(_("Fatura referansı"), max_length=80, blank=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Şarap partisi")
        verbose_name_plural = _("Şarap partileri")
        ordering = ["best_before", "received_on", "id"]
        constraints = [
            models.UniqueConstraint(fields=["wine", "lot_code"], name="uniq_wine_lot_code"),
            models.CheckConstraint(
                condition=models.Q(bottles_remaining__lte=models.F("bottles_received")),
                name="lot_remaining_lte_received",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.wine.sku} · {self.lot_code} ({self.bottles_remaining} şişe)"

    @property
    def total_value(self) -> Decimal:
        return (self.bottles_remaining * self.unit_cost).quantize(Decimal("0.01"))

    @property
    def is_depleted(self) -> bool:
        return self.bottles_remaining == 0


# ---------------------------------------------------------------------------
# Açılmış şişe ve kadeh servisi
# ---------------------------------------------------------------------------
class BottleOpening(TimeStampedModel):
    """Açılmış tek bir şişe.

    Kadeh satışının stoktan doğru düşmesini sağlar: şişe açıldığında bir
    ``BottleOpening`` oluşur, her kadeh servisi ``PouringRecord`` olarak
    kaydedilir ve ``remaining_ml`` azalır.
    """

    class ServiceMethod(models.TextChoices):
        STANDARD = "standard", _("Standart (mantar açıldı)")
        PRESERVATION = "preservation", _("Koruma sistemi (argon/vakum)")
        CORAVIN = "coravin", _("İğne sistemi (Coravin benzeri)")
        TASTING = "tasting", _("Tadım / etkinlik")

    class Status(models.TextChoices):
        OPEN = "open", _("Açık")
        FINISHED = "finished", _("Bitti")
        DISCARDED = "discarded", _("İmha edildi")

    wine = models.ForeignKey(
        Wine, verbose_name=_("Şarap"), on_delete=models.PROTECT, related_name="bottle_openings"
    )
    lot = models.ForeignKey(
        BottleLot,
        verbose_name=_("Parti"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="openings",
    )
    opened_at = models.DateTimeField(_("Açılma zamanı"), default=timezone.now, db_index=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Açan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bottles_opened",
    )
    service_method = models.CharField(
        _("Servis yöntemi"),
        max_length=20,
        choices=ServiceMethod.choices,
        default=ServiceMethod.STANDARD,
    )
    initial_ml = models.PositiveIntegerField(_("Başlangıç hacmi (ml)"), default=STANDARD_BOTTLE_ML)
    remaining_ml = models.PositiveIntegerField(_("Kalan hacim (ml)"), default=STANDARD_BOTTLE_ML)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    #: Koruma sistemine göre tazelik süresi
    freshness_hours = models.PositiveSmallIntegerField(
        _("Tazelik süresi (saat)"),
        default=48,
        help_text=_("Bu sürenin sonunda arayüzde 'kontrol edin' uyarısı gösterilir."),
    )
    closed_at = models.DateTimeField(_("Kapanış zamanı"), null=True, blank=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Açılmış şişe")
        verbose_name_plural = _("Açılmış şişeler")
        ordering = ["-opened_at"]
        indexes = [
            models.Index(fields=["status", "-opened_at"], name="opening_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.wine} · {self.opened_at:%d.%m.%Y %H:%M} · {self.remaining_ml} ml"

    @property
    def poured_ml(self) -> int:
        return self.initial_ml - self.remaining_ml

    @property
    def glasses_poured(self) -> int:
        pour = self.wine.glass_pour_ml or 150
        return int(self.poured_ml // pour)

    @property
    def glasses_remaining(self) -> int:
        pour = self.wine.glass_pour_ml or 150
        return int(self.remaining_ml // pour)

    @property
    def yield_percent(self) -> Decimal:
        """Gerçekleşen verim: servis edilen hacmin şişe hacmine oranı.

        Düşük verim dökülme veya ölçüsüz servisi işaret eder.
        """
        if not self.initial_ml:
            return Decimal("0.00")
        return (Decimal(self.poured_ml) / Decimal(self.initial_ml) * 100).quantize(Decimal("0.01"))

    @property
    def is_past_freshness(self) -> bool:
        if self.status != self.Status.OPEN:
            return False
        deadline = self.opened_at + timezone.timedelta(hours=self.freshness_hours)
        return timezone.now() > deadline

    @property
    def hours_open(self) -> int:
        end = self.closed_at or timezone.now()
        return int((end - self.opened_at).total_seconds() // 3600)


class PouringRecord(TimeStampedModel):
    """Açılmış şişeden yapılan tek bir servis (kadeh, tadım ölçüsü, dökülme)."""

    class PourType(models.TextChoices):
        GLASS_SALE = "glass_sale", _("Kadeh satışı")
        TASTING = "tasting", _("Tadım ölçüsü")
        COMP = "comp", _("İkram")
        STAFF_TRAINING = "training", _("Personel eğitimi")
        SPILLAGE = "spillage", _("Dökülme")
        WASTE = "waste", _("Fire / imha")

    opening = models.ForeignKey(
        BottleOpening,
        verbose_name=_("Açılmış şişe"),
        on_delete=models.CASCADE,
        related_name="pours",
    )
    pour_type = models.CharField(
        _("Servis türü"), max_length=20, choices=PourType.choices, default=PourType.GLASS_SALE
    )
    volume_ml = models.PositiveSmallIntegerField(
        _("Hacim (ml)"), validators=[MinValueValidator(1), MaxValueValidator(1500)]
    )
    poured_at = models.DateTimeField(_("Servis zamanı"), default=timezone.now, db_index=True)
    poured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Servis eden"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pours",
    )
    order_line = models.ForeignKey(
        "operations.OrderLine",
        verbose_name=_("Sipariş satırı"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pours",
    )
    note = models.CharField(_("Not"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("Servis kaydı")
        verbose_name_plural = _("Servis kayıtları")
        ordering = ["-poured_at"]

    def __str__(self) -> str:
        return f"{self.get_pour_type_display()} · {self.volume_ml} ml"

    @property
    def is_revenue(self) -> bool:
        """Gelir getiren servis mi?"""
        return self.pour_type == self.PourType.GLASS_SALE


class WineFault(TimeStampedModel):
    """Şarap kusuru kaydı: mantar hatası, oksidasyon, dökülme, kırılma."""

    class FaultType(models.TextChoices):
        CORKED = "corked", _("Mantar hatası (TCA)")
        OXIDIZED = "oxidized", _("Oksidasyon")
        REDUCED = "reduced", _("Redüksiyon")
        HEAT_DAMAGE = "heat_damage", _("Isı hasarı")
        REFERMENTATION = "refermentation", _("Yeniden fermantasyon")
        BRETT = "brett", _("Brettanomyces")
        SPILLAGE = "spillage", _("Dökülme")
        BREAKAGE = "breakage", _("Şişe kırılması")
        LABEL_DAMAGE = "label_damage", _("Etiket hasarı")
        OTHER = "other", _("Diğer")

    class Resolution(models.TextChoices):
        PENDING = "pending", _("Beklemede")
        SUPPLIER_CLAIM = "supplier_claim", _("Tedarikçiye iade talebi")
        WRITTEN_OFF = "written_off", _("Zayi yazıldı")
        REPLACED_GUEST = "replaced_guest", _("Misafire yenisi verildi")
        ACCEPTED = "accepted", _("Kabul edildi")

    wine = models.ForeignKey(
        Wine, verbose_name=_("Şarap"), on_delete=models.PROTECT, related_name="faults"
    )
    lot = models.ForeignKey(
        BottleLot,
        verbose_name=_("Parti"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faults",
    )
    opening = models.ForeignKey(
        BottleOpening,
        verbose_name=_("Açılmış şişe"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faults",
    )
    fault_type = models.CharField(_("Kusur türü"), max_length=20, choices=FaultType.choices)
    detected_at = models.DateTimeField(_("Tespit zamanı"), default=timezone.now)
    detected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Tespit eden"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wine_faults",
    )
    bottles_affected = models.PositiveSmallIntegerField(_("Etkilenen şişe"), default=1)
    volume_lost_ml = models.PositiveIntegerField(_("Kaybedilen hacim (ml)"), default=0)
    estimated_loss = models.DecimalField(
        _("Tahmini kayıp"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    resolution = models.CharField(
        _("Çözüm"), max_length=20, choices=Resolution.choices, default=Resolution.PENDING
    )
    description = models.TextField(_("Açıklama"), blank=True)

    class Meta:
        verbose_name = _("Şarap kusuru")
        verbose_name_plural = _("Şarap kusurları")
        ordering = ["-detected_at"]

    def __str__(self) -> str:
        return f"{self.wine.name} · {self.get_fault_type_display()}"


# ---------------------------------------------------------------------------
# Tadım, puanlama, eşleştirme
# ---------------------------------------------------------------------------
class TastingNote(TimeStampedModel):
    """Yapılandırılmış tadım notu."""

    class Author(models.TextChoices):
        SOMMELIER = "sommelier", _("Sommelier")
        STAFF = "staff", _("Personel")
        GUEST = "guest", _("Misafir")
        CRITIC = "critic", _("Uzman / Kritik")

    wine = models.ForeignKey(
        Wine, verbose_name=_("Şarap"), on_delete=models.CASCADE, related_name="tasting_notes"
    )
    author_type = models.CharField(
        _("Yazar türü"), max_length=20, choices=Author.choices, default=Author.SOMMELIER
    )
    author_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Yazan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasting_notes",
    )
    author_name = models.CharField(_("Yazar adı"), max_length=150, blank=True)
    tasted_on = models.DateField(_("Tadım tarihi"), default=timezone.localdate)

    appearance = models.TextField(_("Görünüm"), blank=True)
    nose = models.TextField(_("Burun / Aroma"), blank=True)
    palate = models.TextField(_("Damak"), blank=True)
    finish = models.TextField(_("Bitiş"), blank=True)
    conclusion = models.TextField(_("Sonuç"), blank=True)

    body = models.PositiveSmallIntegerField(
        _("Gövde"), null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    acidity = models.PositiveSmallIntegerField(
        _("Asidite"), null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    tannin = models.PositiveSmallIntegerField(
        _("Tanen"), null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    sweetness = models.PositiveSmallIntegerField(
        _("Tatlılık"),
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )

    is_ai_generated = models.BooleanField(
        _("Yapay zekâ tarafından oluşturuldu"),
        default=False,
        help_text=_("Arayüzde açıkça işaretlenir; insan onayı gerekir."),
    )
    is_published = models.BooleanField(_("Yayınlandı"), default=False)

    class Meta:
        verbose_name = _("Tadım notu")
        verbose_name_plural = _("Tadım notları")
        ordering = ["-tasted_on", "-created_at"]

    def __str__(self) -> str:
        return f"{self.wine.name} · {self.get_author_type_display()} · {self.tasted_on}"


class WineRating(TimeStampedModel):
    """Uzman veya müşteri puanı."""

    class Source(models.TextChoices):
        HOUSE = "house", _("İşletme")
        GUEST = "guest", _("Misafir")
        CRITIC = "critic", _("Uzman")

    wine = models.ForeignKey(
        Wine, verbose_name=_("Şarap"), on_delete=models.CASCADE, related_name="ratings"
    )
    source = models.CharField(
        _("Kaynak"), max_length=20, choices=Source.choices, default=Source.HOUSE
    )
    source_name = models.CharField(
        _("Kaynak adı"), max_length=150, blank=True, help_text=_("Örn: kurum veya kişi adı.")
    )
    score = models.DecimalField(
        _("Puan"), max_digits=5, decimal_places=2, validators=[MinValueValidator(0)]
    )
    scale_max = models.DecimalField(
        _("Ölçek üst sınırı"), max_digits=5, decimal_places=2, default=Decimal("100.00")
    )
    rated_on = models.DateField(_("Puan tarihi"), default=timezone.localdate)
    comment = models.TextField(_("Yorum"), blank=True)

    class Meta:
        verbose_name = _("Şarap puanı")
        verbose_name_plural = _("Şarap puanları")
        ordering = ["-rated_on"]

    def __str__(self) -> str:
        return f"{self.wine.name} · {self.score}/{self.scale_max}"

    @property
    def normalized_score(self) -> Decimal:
        """100'lük ölçeğe normalize edilmiş puan."""
        if not self.scale_max:
            return Decimal("0.00")
        return (self.score / self.scale_max * 100).quantize(Decimal("0.01"))


class WinePairing(TimeStampedModel):
    """Yemek veya peynir ile şarap eşleştirmesi."""

    class PairingType(models.TextChoices):
        DISH = "dish", _("Yemek")
        CHEESE = "cheese", _("Peynir")
        DESSERT = "dessert", _("Tatlı")
        GENERAL = "general", _("Genel")

    class Strength(models.IntegerChoices):
        POSSIBLE = 1, _("Denenebilir")
        GOOD = 2, _("İyi uyum")
        EXCELLENT = 3, _("Mükemmel uyum")
        CLASSIC = 4, _("Klasik eşleşme")

    wine = models.ForeignKey(
        Wine, verbose_name=_("Şarap"), on_delete=models.CASCADE, related_name="pairings"
    )
    pairing_type = models.CharField(
        _("Eşleşme türü"), max_length=20, choices=PairingType.choices, default=PairingType.DISH
    )
    menu_item = models.ForeignKey(
        "catalog.MenuItem",
        verbose_name=_("Menü ürünü"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="wine_pairings",
    )
    free_text = models.CharField(
        _("Serbest tanım"),
        max_length=200,
        blank=True,
        help_text=_("Menüde olmayan yiyecekler için (ör. 'olgun kaşar')."),
    )
    strength = models.PositiveSmallIntegerField(
        _("Uyum gücü"), choices=Strength.choices, default=Strength.GOOD
    )
    rationale = models.TextField(_("Gerekçe"), blank=True)
    is_ai_suggested = models.BooleanField(
        _("Yapay zekâ önerisi"),
        default=False,
        help_text=_("Sommelier onayına kadar arayüzde 'öneri' olarak gösterilir."),
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Onaylayan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_pairings",
    )
    is_approved = models.BooleanField(_("Onaylandı"), default=False)

    class Meta:
        verbose_name = _("Şarap eşleştirmesi")
        verbose_name_plural = _("Şarap eşleştirmeleri")
        ordering = ["-strength", "wine__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["wine", "menu_item"],
                condition=models.Q(menu_item__isnull=False),
                name="uniq_wine_menuitem_pairing",
            )
        ]

    def __str__(self) -> str:
        target = self.menu_item.name_tr if self.menu_item_id else self.free_text
        return f"{self.wine.name} ↔ {target}"

    @property
    def target_label(self) -> str:
        return self.menu_item.name_tr if self.menu_item_id else self.free_text


class WineFlight(TimeStampedModel):
    """Şarap uçuşu / tadım seti."""

    name = models.CharField(_("Ad"), max_length=200)
    name_en = models.CharField(_("Ad (EN)"), max_length=200, blank=True)
    description = models.TextField(_("Açıklama"), blank=True)
    price = models.DecimalField(
        _("Fiyat"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    pour_size_ml = models.PositiveSmallIntegerField(_("Ölçü başına hacim (ml)"), default=50)
    is_active = models.BooleanField(_("Etkin"), default=True)
    menu_item = models.OneToOneField(
        "catalog.MenuItem",
        verbose_name=_("Menü ürünü"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wine_flight",
    )

    class Meta:
        verbose_name = _("Şarap uçuşu")
        verbose_name_plural = _("Şarap uçuşları")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def total_pour_ml(self) -> int:
        return self.items.count() * self.pour_size_ml


class WineFlightItem(TimeStampedModel):
    """Şarap uçuşundaki tek bir şarap."""

    flight = models.ForeignKey(
        WineFlight, verbose_name=_("Uçuş"), on_delete=models.CASCADE, related_name="items"
    )
    wine = models.ForeignKey(
        Wine, verbose_name=_("Şarap"), on_delete=models.PROTECT, related_name="flight_items"
    )
    sort_order = models.PositiveSmallIntegerField(_("Sıra"), default=1)
    tasting_hint = models.CharField(_("Tadım ipucu"), max_length=250, blank=True)

    class Meta:
        verbose_name = _("Uçuş şarabı")
        verbose_name_plural = _("Uçuş şarapları")
        ordering = ["sort_order"]
        constraints = [models.UniqueConstraint(fields=["flight", "wine"], name="uniq_flight_wine")]

    def __str__(self) -> str:
        return f"{self.flight.name} · {self.wine.name}"


class TastingEvent(TimeStampedModel):
    """Tadım etkinliği."""

    class Status(models.TextChoices):
        PLANNED = "planned", _("Planlandı")
        OPEN = "open", _("Kayıt açık")
        FULL = "full", _("Kontenjan doldu")
        COMPLETED = "completed", _("Tamamlandı")
        CANCELLED = "cancelled", _("İptal edildi")

    title = models.CharField(_("Başlık"), max_length=200)
    description = models.TextField(_("Açıklama"), blank=True)
    starts_at = models.DateTimeField(_("Başlangıç"))
    ends_at = models.DateTimeField(_("Bitiş"), null=True, blank=True)
    capacity = models.PositiveSmallIntegerField(_("Kontenjan"), default=20)
    price_per_person = models.DecimalField(
        _("Kişi başı ücret"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Sunan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hosted_tastings",
    )
    wines = models.ManyToManyField(
        Wine, verbose_name=_("Şaraplar"), blank=True, related_name="tasting_events"
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.PLANNED
    )

    class Meta:
        verbose_name = _("Tadım etkinliği")
        verbose_name_plural = _("Tadım etkinlikleri")
        ordering = ["-starts_at"]

    def __str__(self) -> str:
        return f"{self.title} · {self.starts_at:%d.%m.%Y}"

    @property
    def seats_taken(self) -> int:
        return sum(reg.guest_count for reg in self.registrations.filter(is_cancelled=False))

    @property
    def seats_available(self) -> int:
        return max(0, self.capacity - self.seats_taken)


class TastingEventRegistration(TimeStampedModel):
    """Tadım etkinliği kaydı."""

    event = models.ForeignKey(
        TastingEvent,
        verbose_name=_("Etkinlik"),
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    customer = models.ForeignKey(
        "crm.Customer",
        verbose_name=_("Müşteri"),
        on_delete=models.PROTECT,
        related_name="tasting_registrations",
    )
    guest_count = models.PositiveSmallIntegerField(_("Kişi sayısı"), default=1)
    is_paid = models.BooleanField(_("Ödendi"), default=False)
    is_cancelled = models.BooleanField(_("İptal"), default=False)
    note = models.CharField(_("Not"), max_length=250, blank=True)

    class Meta:
        verbose_name = _("Etkinlik kaydı")
        verbose_name_plural = _("Etkinlik kayıtları")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["event", "customer"], name="uniq_event_customer")
        ]

    def __str__(self) -> str:
        return f"{self.event.title} · {self.customer}"


# ---------------------------------------------------------------------------
# Şarap kulübü ve özel kav müşterileri
# ---------------------------------------------------------------------------
class WineClubTier(TimeStampedModel):
    """Şarap kulübü üyelik kademesi."""

    name = models.CharField(_("Ad"), max_length=120, unique=True)
    description = models.TextField(_("Açıklama"), blank=True)
    monthly_fee = models.DecimalField(
        _("Aylık ücret"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    discount_percent = models.DecimalField(
        _("İndirim (%)"), max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    bottles_per_period = models.PositiveSmallIntegerField(_("Dönem başına şişe"), default=0)
    benefits = models.JSONField(_("Ayrıcalıklar"), default=list, blank=True)
    is_active = models.BooleanField(_("Etkin"), default=True)

    class Meta:
        verbose_name = _("Kulüp kademesi")
        verbose_name_plural = _("Kulüp kademeleri")
        ordering = ["monthly_fee"]

    def __str__(self) -> str:
        return self.name


class WineClubMembership(TimeStampedModel):
    """Müşterinin şarap kulübü üyeliği."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Etkin")
        PAUSED = "paused", _("Duraklatıldı")
        CANCELLED = "cancelled", _("İptal edildi")

    customer = models.ForeignKey(
        "crm.Customer",
        verbose_name=_("Müşteri"),
        on_delete=models.PROTECT,
        related_name="club_memberships",
    )
    tier = models.ForeignKey(
        WineClubTier, verbose_name=_("Kademe"), on_delete=models.PROTECT, related_name="memberships"
    )
    started_on = models.DateField(_("Başlangıç"), default=timezone.localdate)
    ended_on = models.DateField(_("Bitiş"), null=True, blank=True)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    member_number = models.CharField(_("Üye numarası"), max_length=30, unique=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Kulüp üyeliği")
        verbose_name_plural = _("Kulüp üyelikleri")
        ordering = ["-started_on"]

    def __str__(self) -> str:
        return f"{self.member_number} · {self.customer}"


class PrivateCellarClient(TimeStampedModel):
    """Özel kav müşterisi: kendi şaraplarını işletmenin kavında saklayan misafir."""

    customer = models.OneToOneField(
        "crm.Customer",
        verbose_name=_("Müşteri"),
        on_delete=models.PROTECT,
        related_name="private_cellar",
    )
    client_code = models.CharField(_("Müşteri kav kodu"), max_length=30, unique=True)
    contract_started_on = models.DateField(_("Sözleşme başlangıcı"), default=timezone.localdate)
    contract_ends_on = models.DateField(_("Sözleşme bitişi"), null=True, blank=True)
    monthly_fee = models.DecimalField(
        _("Aylık saklama ücreti"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    corkage_fee = models.DecimalField(
        _("Şişe açma ücreti"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    allocated_locations = models.ManyToManyField(
        WineStorageLocation,
        verbose_name=_("Ayrılan konumlar"),
        blank=True,
        related_name="private_clients",
    )
    is_active = models.BooleanField(_("Etkin"), default=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Özel kav müşterisi")
        verbose_name_plural = _("Özel kav müşterileri")
        ordering = ["client_code"]

    def __str__(self) -> str:
        return f"{self.client_code} · {self.customer}"

    @property
    def bottle_count(self) -> int:
        return sum(item.quantity for item in self.bottles.filter(is_withdrawn=False))


class PrivateCellarBottle(TimeStampedModel):
    """Özel kav müşterisine ait şişe kaydı.

    Bu şişeler işletmenin stok değerlemesine DAHİL EDİLMEZ; müşteri
    mülkiyetindedir ve ayrı raporlanır.
    """

    client = models.ForeignKey(
        PrivateCellarClient,
        verbose_name=_("Özel kav müşterisi"),
        on_delete=models.CASCADE,
        related_name="bottles",
    )
    wine = models.ForeignKey(
        Wine,
        verbose_name=_("Şarap"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="private_bottles",
    )
    free_text_label = models.CharField(
        _("Etiket açıklaması"),
        max_length=250,
        blank=True,
        help_text=_("Kavda kayıtlı olmayan şaraplar için."),
    )
    location = models.ForeignKey(
        WineStorageLocation,
        verbose_name=_("Konum"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="private_bottles",
    )
    quantity = models.PositiveSmallIntegerField(_("Adet"), default=1)
    deposited_on = models.DateField(_("Teslim tarihi"), default=timezone.localdate)
    declared_value = models.DecimalField(
        _("Beyan edilen değer"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    is_withdrawn = models.BooleanField(_("Teslim alındı"), default=False)
    withdrawn_on = models.DateField(_("Teslim alma tarihi"), null=True, blank=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Özel kav şişesi")
        verbose_name_plural = _("Özel kav şişeleri")
        ordering = ["-deposited_on"]

    def __str__(self) -> str:
        label = self.wine.name if self.wine_id else self.free_text_label
        return f"{self.client.client_code} · {label} × {self.quantity}"


class WineDuplicateAlert(TimeStampedModel):
    """Mükerrer veya şüpheli şarap kaydı uyarısı.

    ``cellar.services.detect_duplicates`` tarafından üretilir. Sistem hiçbir
    kaydı kendiliğinden silmez; yalnızca kullanıcıya inceleme için sunar.
    """

    class Reason(models.TextChoices):
        SAME_PRODUCER_NAME_VINTAGE = "same_pnv", _("Aynı üretici, ad ve rekolte")
        SAME_BARCODE = "same_barcode", _("Aynı barkod")
        SIMILAR_NAME = "similar_name", _("Çok benzer ad")
        IMPLAUSIBLE_VINTAGE = "implausible_vintage", _("Şüpheli rekolte")
        PRICE_ANOMALY = "price_anomaly", _("Fiyat anomalisi")

    class Status(models.TextChoices):
        OPEN = "open", _("İnceleme bekliyor")
        CONFIRMED = "confirmed", _("Mükerrer doğrulandı")
        DISMISSED = "dismissed", _("Uyarı kapatıldı")

    wine = models.ForeignKey(
        Wine, verbose_name=_("Şarap"), on_delete=models.CASCADE, related_name="duplicate_alerts"
    )
    other_wine = models.ForeignKey(
        Wine,
        verbose_name=_("Karşılaştırılan şarap"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="duplicate_alerts_as_other",
    )
    reason = models.CharField(_("Gerekçe"), max_length=30, choices=Reason.choices)
    detail = models.TextField(_("Ayrıntı"), blank=True)
    confidence = models.DecimalField(
        _("Güven"), max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.OPEN
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("İnceleyen"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_duplicate_alerts",
    )

    class Meta:
        verbose_name = _("Mükerrer kayıt uyarısı")
        verbose_name_plural = _("Mükerrer kayıt uyarıları")
        ordering = ["-confidence", "-created_at"]

    def __str__(self) -> str:
        return f"{self.wine.name} · {self.get_reason_display()}"
