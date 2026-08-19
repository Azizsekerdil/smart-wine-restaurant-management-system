"""Menü, kategori, reçete, alerjen ve fiyatlandırma modelleri."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import SoftDeleteModel, TimeStampedModel


class Allergen(TimeStampedModel):
    """AB 1169/2011 ve Türk Gıda Kodeksi'ne göre bildirimi zorunlu alerjenler.

    UYARI: Alerjen bilgisi işletme tarafından girilir ve tıbbi tavsiye
    yerine geçmez. Arayüzde bu uyarı her zaman gösterilir.
    """

    code = models.SlugField(_("Kod"), max_length=40, unique=True)
    name_tr = models.CharField(_("Ad (TR)"), max_length=100)
    name_en = models.CharField(_("Ad (EN)"), max_length=100)
    description = models.TextField(_("Açıklama"), blank=True)
    icon = models.CharField(_("Simge"), max_length=40, blank=True)

    class Meta:
        verbose_name = _("Alerjen")
        verbose_name_plural = _("Alerjenler")
        ordering = ["name_tr"]

    def __str__(self) -> str:
        return self.name_tr


class DietaryTag(TimeStampedModel):
    """Beslenme etiketi: vejetaryen, vegan, glutensiz, helal vb."""

    code = models.SlugField(_("Kod"), max_length=40, unique=True)
    name_tr = models.CharField(_("Ad (TR)"), max_length=100)
    name_en = models.CharField(_("Ad (EN)"), max_length=100)
    badge_class = models.CharField(_("Rozet sınıfı"), max_length=40, default="bg-success")

    class Meta:
        verbose_name = _("Beslenme etiketi")
        verbose_name_plural = _("Beslenme etiketleri")
        ordering = ["name_tr"]

    def __str__(self) -> str:
        return self.name_tr


class MenuCategory(TimeStampedModel):
    """Menü kategorisi (alt kategori desteklidir)."""

    class Channel(models.TextChoices):
        DINE_IN = "dine_in", _("Salon")
        BAR = "bar", _("Bar")
        TAKEAWAY = "takeaway", _("Paket servis")
        EVENT = "event", _("Etkinlik")
        ALL = "all", _("Tümü")

    code = models.SlugField(_("Kod"), max_length=60, unique=True)
    name_tr = models.CharField(_("Ad (TR)"), max_length=120)
    name_en = models.CharField(_("Ad (EN)"), max_length=120, blank=True)
    description_tr = models.TextField(_("Açıklama (TR)"), blank=True)
    description_en = models.TextField(_("Açıklama (EN)"), blank=True)
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Üst kategori"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    channel = models.CharField(
        _("Satış kanalı"), max_length=20, choices=Channel.choices, default=Channel.ALL
    )
    #: Mutfak mı bar mı sommelier mi hazırlar
    preparation_station = models.CharField(
        _("Hazırlık istasyonu"),
        max_length=20,
        choices=[
            ("kitchen", _("Mutfak")),
            ("bar", _("Bar")),
            ("wine", _("Şarap / Sommelier")),
            ("none", _("Hazırlık yok")),
        ],
        default="kitchen",
    )
    sort_order = models.PositiveSmallIntegerField(_("Sıra"), default=100)
    is_active = models.BooleanField(_("Etkin"), default=True)
    show_on_qr_menu = models.BooleanField(_("QR menüde göster"), default=True)

    class Meta:
        verbose_name = _("Menü kategorisi")
        verbose_name_plural = _("Menü kategorileri")
        ordering = ["sort_order", "name_tr"]

    def __str__(self) -> str:
        if self.parent_id:
            return f"{self.parent.name_tr} › {self.name_tr}"
        return self.name_tr

    def name_for(self, language: str) -> str:
        return self.name_en if language == "en" and self.name_en else self.name_tr


class MenuItem(SoftDeleteModel):
    """Menüde satılan ürün (yemek, içecek veya şarap referansı)."""

    class ItemType(models.TextChoices):
        FOOD = "food", _("Yemek")
        DRINK = "drink", _("İçecek")
        WINE = "wine", _("Şarap")
        WINE_BY_GLASS = "wine_glass", _("Kadeh şarap")
        SET_MENU = "set_menu", _("Set menü")
        WINE_FLIGHT = "wine_flight", _("Şarap uçuşu")
        SERVICE = "service", _("Servis / Ücret")

    code = models.CharField(_("Ürün kodu"), max_length=40, unique=True, db_index=True)
    name_tr = models.CharField(_("Ad (TR)"), max_length=200, db_index=True)
    name_en = models.CharField(_("Ad (EN)"), max_length=200, blank=True)
    description_tr = models.TextField(_("Açıklama (TR)"), blank=True)
    description_en = models.TextField(_("Açıklama (EN)"), blank=True)
    category = models.ForeignKey(
        MenuCategory,
        verbose_name=_("Kategori"),
        on_delete=models.PROTECT,
        related_name="items",
    )
    item_type = models.CharField(
        _("Tür"), max_length=20, choices=ItemType.choices, default=ItemType.FOOD
    )
    #: Şarap ürünleri için kav kaydına bağlantı
    wine = models.ForeignKey(
        "cellar.Wine",
        verbose_name=_("Şarap"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="menu_items",
    )

    # --- Fiyatlandırma ---
    base_price = models.DecimalField(
        _("Satış fiyatı"), max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    tax_rate = models.DecimalField(
        _("KDV oranı (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    #: Menü mühendisliği ve kârlılık için hesaplanan maliyet
    cost_price = models.DecimalField(
        _("Maliyet"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Reçeteden otomatik hesaplanır; el ile de girilebilir."),
    )
    cost_is_manual = models.BooleanField(_("Maliyet el ile girildi"), default=False)

    # --- Servis bilgileri ---
    portion_size = models.CharField(_("Porsiyon"), max_length=60, blank=True)
    preparation_minutes = models.PositiveSmallIntegerField(_("Hazırlık (dk)"), default=0)
    calories = models.PositiveIntegerField(_("Kalori"), null=True, blank=True)

    allergens = models.ManyToManyField(
        Allergen, verbose_name=_("Alerjenler"), blank=True, related_name="menu_items"
    )
    dietary_tags = models.ManyToManyField(
        DietaryTag, verbose_name=_("Beslenme etiketleri"), blank=True, related_name="menu_items"
    )

    # --- Görünürlük ---
    is_active = models.BooleanField(_("Etkin"), default=True, db_index=True)
    is_available = models.BooleanField(
        _("Serviste"), default=True, help_text=_("Geçici olarak tükendi/kapalı işaretleyin.")
    )
    show_on_qr_menu = models.BooleanField(_("QR menüde göster"), default=True)
    is_chef_recommendation = models.BooleanField(_("Şef önerisi"), default=False)
    is_sommelier_recommendation = models.BooleanField(_("Sommelier önerisi"), default=False)
    sort_order = models.PositiveSmallIntegerField(_("Sıra"), default=100)
    image = models.ImageField(_("Görsel"), upload_to="menu/", blank=True, null=True)

    #: Stok bağlantısı (yemek ürünleri reçete üzerinden düşer)
    tracks_stock = models.BooleanField(
        _("Stoktan düşer"),
        default=True,
        help_text=_("Kapalıysa satışta stok hareketi oluşturulmaz."),
    )

    class Meta:
        verbose_name = _("Menü ürünü")
        verbose_name_plural = _("Menü ürünleri")
        ordering = ["category__sort_order", "sort_order", "name_tr"]
        indexes = [
            models.Index(fields=["item_type", "is_active"], name="menuitem_type_active_idx"),
        ]
        permissions = [
            ("can_change_price", _("Fiyat değiştirebilir")),
            ("can_manage_promotion", _("Kampanya yönetebilir")),
            ("view_menu_engineering", _("Menü mühendisliği raporunu görebilir")),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name_tr}"

    def name_for(self, language: str) -> str:
        return self.name_en if language == "en" and self.name_en else self.name_tr

    def description_for(self, language: str) -> str:
        if language == "en" and self.description_en:
            return self.description_en
        return self.description_tr

    @property
    def price_with_tax(self) -> Decimal:
        """KDV dahil fiyat."""
        return (self.base_price * (Decimal("1") + self.tax_rate / Decimal("100"))).quantize(
            Decimal("0.01")
        )

    @property
    def margin(self) -> Decimal:
        """Brüt kâr (satış - maliyet)."""
        return self.base_price - self.cost_price

    @property
    def margin_percent(self) -> Decimal:
        """Brüt kâr marjı (%)."""
        if not self.base_price:
            return Decimal("0.00")
        return ((self.margin / self.base_price) * Decimal("100")).quantize(Decimal("0.01"))

    @property
    def food_cost_percent(self) -> Decimal:
        """Maliyet oranı (%). Restoran sektöründe temel gösterge."""
        if not self.base_price:
            return Decimal("0.00")
        return ((self.cost_price / self.base_price) * Decimal("100")).quantize(Decimal("0.01"))

    def recalculate_cost(self, *, save: bool = True) -> Decimal:
        """Reçeteden porsiyon maliyetini hesaplar.

        ``cost_is_manual`` işaretliyse hesaplama yapılmaz ve mevcut değer korunur.
        """
        if self.cost_is_manual:
            return self.cost_price
        recipe = getattr(self, "recipe", None)
        if recipe is None:
            return self.cost_price
        total = recipe.total_cost()
        self.cost_price = total
        if save:
            self.save(update_fields=["cost_price", "updated_at"])
        return total

    @property
    def effective_price(self) -> Decimal:
        """Geçerli kampanya/happy hour indirimlerini uygulanmış fiyat."""
        now = timezone.now()
        best = self.base_price
        for rule in self.price_rules.filter(is_active=True):
            if rule.applies_at(now):
                candidate = rule.apply(self.base_price)
                best = min(best, candidate)
        return best.quantize(Decimal("0.01"))


class Recipe(TimeStampedModel):
    """Menü ürününün reçetesi ve porsiyon maliyeti."""

    menu_item = models.OneToOneField(
        MenuItem, verbose_name=_("Menü ürünü"), on_delete=models.CASCADE, related_name="recipe"
    )
    yield_portions = models.DecimalField(
        _("Verim (porsiyon)"),
        max_digits=8,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    instructions = models.TextField(_("Hazırlama talimatı"), blank=True)
    plating_notes = models.TextField(_("Sunum notu"), blank=True)
    #: Fire/kayıp payı (%). Maliyet hesabına eklenir.
    waste_allowance_percent = models.DecimalField(
        _("Fire payı (%)"), max_digits=5, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        verbose_name = _("Reçete")
        verbose_name_plural = _("Reçeteler")

    def __str__(self) -> str:
        return f"Reçete · {self.menu_item.name_tr}"

    def total_cost(self) -> Decimal:
        """Bir porsiyonun malzeme maliyeti."""
        lines_total = sum(
            (line.line_cost() for line in self.lines.select_related("stock_item")),
            Decimal("0.00"),
        )
        with_waste = lines_total * (Decimal("1") + self.waste_allowance_percent / Decimal("100"))
        portions = self.yield_portions or Decimal("1")
        return (with_waste / portions).quantize(Decimal("0.01"))


class RecipeLine(TimeStampedModel):
    """Reçetedeki tek bir malzeme satırı."""

    recipe = models.ForeignKey(
        Recipe, verbose_name=_("Reçete"), on_delete=models.CASCADE, related_name="lines"
    )
    stock_item = models.ForeignKey(
        "inventory.StockItem",
        verbose_name=_("Stok kalemi"),
        on_delete=models.PROTECT,
        related_name="recipe_lines",
    )
    quantity = models.DecimalField(
        _("Miktar"),
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    note = models.CharField(_("Not"), max_length=200, blank=True)
    is_optional = models.BooleanField(_("İsteğe bağlı"), default=False)

    class Meta:
        verbose_name = _("Reçete satırı")
        verbose_name_plural = _("Reçete satırları")
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["recipe", "stock_item"], name="uniq_recipe_stockitem")
        ]

    def __str__(self) -> str:
        return f"{self.stock_item} × {self.quantity}"

    def line_cost(self) -> Decimal:
        """Bu satırın maliyeti (stok kaleminin ortalama birim maliyeti üzerinden)."""
        if self.is_optional:
            return Decimal("0.00")
        unit_cost = self.stock_item.average_unit_cost or Decimal("0.00")
        return (self.quantity * unit_cost).quantize(Decimal("0.0001"))


class PriceRule(TimeStampedModel):
    """Dinamik fiyatlandırma / happy hour / kampanya kuralı.

    Kurallar üst üste binerse müşteri lehine olan (en düşük) fiyat uygulanır.
    """

    class RuleType(models.TextChoices):
        PERCENT_OFF = "percent_off", _("Yüzde indirim")
        AMOUNT_OFF = "amount_off", _("Tutar indirimi")
        FIXED_PRICE = "fixed_price", _("Sabit fiyat")

    name = models.CharField(_("Kampanya adı"), max_length=200)
    menu_items = models.ManyToManyField(
        MenuItem, verbose_name=_("Ürünler"), blank=True, related_name="price_rules"
    )
    categories = models.ManyToManyField(
        MenuCategory, verbose_name=_("Kategoriler"), blank=True, related_name="price_rules"
    )
    rule_type = models.CharField(
        _("Kural türü"), max_length=20, choices=RuleType.choices, default=RuleType.PERCENT_OFF
    )
    value = models.DecimalField(
        _("Değer"), max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )

    # --- Geçerlilik ---
    starts_on = models.DateField(_("Başlangıç tarihi"), null=True, blank=True)
    ends_on = models.DateField(_("Bitiş tarihi"), null=True, blank=True)
    starts_at = models.TimeField(_("Günlük başlangıç saati"), null=True, blank=True)
    ends_at = models.TimeField(_("Günlük bitiş saati"), null=True, blank=True)
    #: 0=Pazartesi … 6=Pazar. Boş liste = her gün
    weekdays = models.JSONField(_("Geçerli günler"), default=list, blank=True)

    is_active = models.BooleanField(_("Etkin"), default=True)
    requires_approval = models.BooleanField(
        _("Onay gerektirir"),
        default=False,
        help_text=_("İşaretliyse kampanya yönetici onayı olmadan uygulanmaz."),
    )

    class Meta:
        verbose_name = _("Fiyat kuralı")
        verbose_name_plural = _("Fiyat kuralları")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    def applies_at(self, moment: Any) -> bool:
        """Kuralın verilen anda geçerli olup olmadığını bildirir."""
        if not self.is_active:
            return False
        local = timezone.localtime(moment)
        if self.starts_on and local.date() < self.starts_on:
            return False
        if self.ends_on and local.date() > self.ends_on:
            return False
        if self.weekdays and local.weekday() not in self.weekdays:
            return False
        if self.starts_at and self.ends_at:
            current = local.time()
            if self.starts_at <= self.ends_at:
                if not (self.starts_at <= current <= self.ends_at):
                    return False
            # Gece yarısını aşan aralık (ör. 22:00 - 02:00)
            elif not (current >= self.starts_at or current <= self.ends_at):
                return False
        return True

    def apply(self, price: Decimal) -> Decimal:
        """Kuralı fiyata uygular."""
        if self.rule_type == self.RuleType.PERCENT_OFF:
            result = price * (Decimal("1") - self.value / Decimal("100"))
        elif self.rule_type == self.RuleType.AMOUNT_OFF:
            result = price - self.value
        else:
            result = self.value
        return max(Decimal("0.00"), result).quantize(Decimal("0.01"))


class MenuEngineeringSnapshot(TimeStampedModel):
    """Menü mühendisliği anlık görüntüsü (Yıldız / At / Bilmece / Köpek).

    Kasırga-Smith sınıflandırması, popülerlik ve kâr marjı eksenlerine göre
    her ürünü dört kadrandan birine yerleştirir.
    """

    class Quadrant(models.TextChoices):
        STAR = "star", _("Yıldız (yüksek kâr, yüksek satış)")
        PLOWHORSE = "plowhorse", _("At (düşük kâr, yüksek satış)")
        PUZZLE = "puzzle", _("Bilmece (yüksek kâr, düşük satış)")
        DOG = "dog", _("Köpek (düşük kâr, düşük satış)")

    menu_item = models.ForeignKey(
        MenuItem,
        verbose_name=_("Menü ürünü"),
        on_delete=models.CASCADE,
        related_name="engineering_snapshots",
    )
    period_start = models.DateField(_("Dönem başı"))
    period_end = models.DateField(_("Dönem sonu"))
    units_sold = models.PositiveIntegerField(_("Satış adedi"), default=0)
    popularity_index = models.DecimalField(
        _("Popülerlik endeksi"), max_digits=8, decimal_places=4, default=Decimal("0")
    )
    contribution_margin = models.DecimalField(
        _("Katkı payı"), max_digits=12, decimal_places=2, default=Decimal("0")
    )
    quadrant = models.CharField(_("Kadran"), max_length=20, choices=Quadrant.choices)

    class Meta:
        verbose_name = _("Menü mühendisliği kaydı")
        verbose_name_plural = _("Menü mühendisliği kayıtları")
        ordering = ["-period_end", "-contribution_margin"]
        constraints = [
            models.UniqueConstraint(
                fields=["menu_item", "period_start", "period_end"],
                name="uniq_menu_engineering_period",
            )
        ]

    def __str__(self) -> str:
        return f"{self.menu_item.name_tr} · {self.get_quadrant_display()}"
