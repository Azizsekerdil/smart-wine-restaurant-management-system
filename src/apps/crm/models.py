"""Müşteri, rıza, sadakat ve kampanya modelleri.

KVKK / GDPR ilkeleri:
  * **Veri minimizasyonu** — yalnızca hizmet için gerekli alanlar tutulur.
  * **Açık rıza** — pazarlama iletişimi için ayrı ``ConsentRecord`` gerekir.
  * **Şifreleme** — telefon, e-posta ve doğum tarihi şifreli saklanır.
  * **Silme hakkı** — ``DataErasureRequest`` ile kişisel veri anonimleştirilir;
    mali kayıtlar (adisyon tutarları) yasal saklama süresince korunur.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.fields import EncryptedCharField, blind_index
from apps.core.models import SoftDeleteModel, TimeStampedModel


class Customer(SoftDeleteModel):
    """Müşteri kaydı.

    Kişisel veriler şifreli alanlarda tutulur. Telefon ve e-posta ile arama
    yapılabilmesi için ayrıca geri döndürülemez HMAC özeti (``*_index``)
    saklanır.
    """

    class Segment(models.TextChoices):
        NEW = "new", _("Yeni")
        REGULAR = "regular", _("Düzenli")
        VIP = "vip", _("VIP")
        CORPORATE = "corporate", _("Kurumsal")
        INACTIVE = "inactive", _("Pasif")

    code = models.CharField(_("Müşteri kodu"), max_length=30, unique=True, db_index=True)
    first_name = models.CharField(_("Ad"), max_length=100)
    last_name = models.CharField(_("Soyad"), max_length=100, blank=True)
    company_name = models.CharField(_("Firma"), max_length=200, blank=True)

    # --- Şifreli kişisel veriler ---
    phone = EncryptedCharField(_("Telefon"), blank=True, default="")
    phone_index = models.CharField(
        _("Telefon arama özeti"), max_length=64, blank=True, db_index=True, editable=False
    )
    email = EncryptedCharField(_("E-posta"), blank=True, default="")
    email_index = models.CharField(
        _("E-posta arama özeti"), max_length=64, blank=True, db_index=True, editable=False
    )
    birth_date = EncryptedCharField(
        _("Doğum tarihi"), blank=True, default="", help_text=_("GG.AA.YYYY biçiminde.")
    )
    #: Doğum günü kampanyaları için yalnızca gün-ay (yıl saklanmaz — veri minimizasyonu)
    birth_day = models.PositiveSmallIntegerField(_("Doğum günü"), null=True, blank=True)
    birth_month = models.PositiveSmallIntegerField(_("Doğum ayı"), null=True, blank=True)

    segment = models.CharField(
        _("Segment"), max_length=20, choices=Segment.choices, default=Segment.NEW, db_index=True
    )
    preferred_language = models.CharField(
        _("Tercih edilen dil"),
        max_length=5,
        choices=[("tr", "Türkçe"), ("en", "English")],
        default="tr",
    )

    # --- Tercihler ---
    favorite_wines = models.ManyToManyField(
        "cellar.Wine", verbose_name=_("Favori şaraplar"), blank=True, related_name="fans"
    )
    favorite_menu_items = models.ManyToManyField(
        "catalog.MenuItem", verbose_name=_("Favori yemekler"), blank=True, related_name="fans"
    )
    preferred_section = models.ForeignKey(
        "operations.FloorSection",
        verbose_name=_("Tercih edilen bölüm"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regulars",
    )
    dietary_notes = models.TextField(_("Beslenme tercihleri"), blank=True)
    allergy_notes = models.TextField(
        _("Alerji notları"),
        blank=True,
        help_text=_(
            "Misafirin beyanına dayanır. Tıbbi tavsiye değildir; mutfak her "
            "durumda kendi kontrolünü yapmalıdır."
        ),
    )
    notes = models.TextField(_("Genel notlar"), blank=True)
    is_vip = models.BooleanField(_("VIP"), default=False)
    is_blacklisted = models.BooleanField(_("Kara liste"), default=False)
    blacklist_reason = models.CharField(_("Kara liste gerekçesi"), max_length=250, blank=True)

    first_visit_on = models.DateField(_("İlk ziyaret"), null=True, blank=True)
    last_visit_on = models.DateField(_("Son ziyaret"), null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = _("Müşteri")
        verbose_name_plural = _("Müşteriler")
        ordering = ["last_name", "first_name"]
        permissions = [
            ("can_export_customer_data", _("Müşteri verisini dışa aktarabilir")),
            ("can_erase_customer_data", _("Müşteri verisini silebilir (KVKK)")),
            ("view_customer_contact", _("Müşteri iletişim bilgilerini görebilir")),
        ]

    def __str__(self) -> str:
        if self.company_name:
            return f"{self.company_name} ({self.full_name})"
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def visit_count(self) -> int:
        return self.orders.filter(status="paid").count()

    @property
    def lifetime_value(self) -> Decimal:
        total = self.orders.filter(status="paid").aggregate(total=models.Sum("grand_total"))[
            "total"
        ]
        return (total or Decimal("0.00")).quantize(Decimal("0.01"))

    @property
    def average_spend(self) -> Decimal:
        count = self.visit_count
        if not count:
            return Decimal("0.00")
        return (self.lifetime_value / count).quantize(Decimal("0.01"))

    def has_consent(self, purpose: str) -> bool:
        """Belirtilen amaç için geçerli açık rıza var mı?"""
        return self.consents.filter(
            purpose=purpose, is_granted=True, withdrawn_at__isnull=True
        ).exists()

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Aranabilir özetleri güncelle (düz metin saklanmaz)
        self.phone_index = blind_index(self.phone) if self.phone else ""
        self.email_index = blind_index(self.email) if self.email else ""
        super().save(*args, **kwargs)


class ConsentRecord(TimeStampedModel):
    """KVKK / GDPR açık rıza kaydı.

    Her amaç için ayrı rıza alınır. Rıza geri çekildiğinde kayıt silinmez;
    ``withdrawn_at`` doldurulur (ispat yükümlülüğü).
    """

    class Purpose(models.TextChoices):
        SERVICE = "service", _("Hizmet sunumu (rezervasyon, sipariş)")
        MARKETING_EMAIL = "marketing_email", _("E-posta ile pazarlama")
        MARKETING_SMS = "marketing_sms", _("SMS ile pazarlama")
        PROFILING = "profiling", _("Tercih analizi / kişiselleştirme")
        AI_PROCESSING = "ai_processing", _("Yapay zekâ ile analiz")
        PHOTO = "photo", _("Fotoğraf / görüntü kullanımı")

    customer = models.ForeignKey(
        Customer, verbose_name=_("Müşteri"), on_delete=models.CASCADE, related_name="consents"
    )
    purpose = models.CharField(_("Amaç"), max_length=30, choices=Purpose.choices, db_index=True)
    is_granted = models.BooleanField(_("Rıza verildi"), default=False)
    granted_at = models.DateTimeField(_("Rıza zamanı"), null=True, blank=True)
    withdrawn_at = models.DateTimeField(_("Geri çekilme zamanı"), null=True, blank=True)
    #: Rızanın nasıl alındığı (ıslak imza, dijital form, telefon kaydı…)
    collection_method = models.CharField(_("Alınma yöntemi"), max_length=100, blank=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Alan personel"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collected_consents",
    )
    policy_version = models.CharField(_("Aydınlatma metni sürümü"), max_length=20, blank=True)
    note = models.CharField(_("Not"), max_length=250, blank=True)

    class Meta:
        verbose_name = _("Rıza kaydı")
        verbose_name_plural = _("Rıza kayıtları")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "purpose"],
                condition=models.Q(withdrawn_at__isnull=True),
                name="uniq_active_consent_per_purpose",
            )
        ]

    def __str__(self) -> str:
        state = _("verildi") if self.is_granted and not self.withdrawn_at else _("yok")
        return f"{self.customer} · {self.get_purpose_display()} · {state}"

    def withdraw(self) -> None:
        """Rızayı geri çeker."""
        self.withdrawn_at = timezone.now()
        self.is_granted = False
        self.save(update_fields=["withdrawn_at", "is_granted", "updated_at"])


class DataErasureRequest(TimeStampedModel):
    """KVKK madde 11 / GDPR madde 17 kapsamında veri silme talebi.

    Silme işlemi kişisel verileri anonimleştirir; mali kayıtlar yasal
    saklama süresi boyunca (varsayılan 10 yıl) tutulmaya devam eder.
    """

    class Status(models.TextChoices):
        RECEIVED = "received", _("Alındı")
        APPROVED = "approved", _("Onaylandı")
        COMPLETED = "completed", _("Tamamlandı")
        REJECTED = "rejected", _("Reddedildi")

    customer = models.ForeignKey(
        Customer,
        verbose_name=_("Müşteri"),
        on_delete=models.PROTECT,
        related_name="erasure_requests",
    )
    requested_on = models.DateField(_("Talep tarihi"), default=timezone.localdate)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.RECEIVED
    )
    approval = models.ForeignKey(
        "accounts.ApprovalRequest",
        verbose_name=_("Onay talebi"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="erasure_requests",
    )
    completed_at = models.DateTimeField(_("Tamamlanma"), null=True, blank=True)
    rejection_reason = models.CharField(_("Ret gerekçesi"), max_length=250, blank=True)
    retained_records_note = models.TextField(
        _("Saklanan kayıtlar"),
        blank=True,
        help_text=_("Yasal zorunluluk nedeniyle korunan kayıtların açıklaması."),
    )

    class Meta:
        verbose_name = _("Veri silme talebi")
        verbose_name_plural = _("Veri silme talepleri")
        ordering = ["-requested_on"]

    def __str__(self) -> str:
        return f"{self.customer} · {self.get_status_display()}"


class LoyaltyProgram(TimeStampedModel):
    """Sadakat programı tanımı."""

    name = models.CharField(_("Ad"), max_length=150, unique=True)
    points_per_currency = models.DecimalField(
        _("Birim harcama başına puan"), max_digits=8, decimal_places=4, default=Decimal("1.0000")
    )
    currency_per_point = models.DecimalField(
        _("Puan başına indirim tutarı"), max_digits=8, decimal_places=4, default=Decimal("0.0100")
    )
    minimum_redeem_points = models.PositiveIntegerField(_("Asgari kullanım puanı"), default=100)
    points_expire_days = models.PositiveSmallIntegerField(
        _("Puan geçerliliği (gün)"), default=365, help_text=_("0 = süresiz.")
    )
    is_active = models.BooleanField(_("Etkin"), default=True)

    class Meta:
        verbose_name = _("Sadakat programı")
        verbose_name_plural = _("Sadakat programları")

    def __str__(self) -> str:
        return self.name


class LoyaltyAccount(TimeStampedModel):
    """Müşterinin sadakat hesabı."""

    customer = models.OneToOneField(
        Customer,
        verbose_name=_("Müşteri"),
        on_delete=models.CASCADE,
        related_name="loyalty_account",
    )
    program = models.ForeignKey(
        LoyaltyProgram, verbose_name=_("Program"), on_delete=models.PROTECT, related_name="accounts"
    )
    card_number = models.CharField(_("Kart numarası"), max_length=30, unique=True, db_index=True)
    points_balance = models.IntegerField(_("Puan bakiyesi"), default=0)
    tier = models.CharField(_("Kademe"), max_length=40, blank=True)
    joined_on = models.DateField(_("Katılım tarihi"), default=timezone.localdate)
    is_active = models.BooleanField(_("Etkin"), default=True)

    class Meta:
        verbose_name = _("Sadakat hesabı")
        verbose_name_plural = _("Sadakat hesapları")

    def __str__(self) -> str:
        return f"{self.card_number} · {self.points_balance} puan"

    @property
    def redeemable_amount(self) -> Decimal:
        """Puanların para karşılığı."""
        if self.points_balance < self.program.minimum_redeem_points:
            return Decimal("0.00")
        return (Decimal(self.points_balance) * self.program.currency_per_point).quantize(
            Decimal("0.01")
        )


class LoyaltyTransaction(TimeStampedModel):
    """Sadakat puanı hareketi (değiştirilemez)."""

    class Kind(models.TextChoices):
        EARN = "earn", _("Kazanım")
        REDEEM = "redeem", _("Kullanım")
        ADJUST = "adjust", _("Düzeltme")
        EXPIRE = "expire", _("Süre dolumu")
        BONUS = "bonus", _("Bonus")

    account = models.ForeignKey(
        LoyaltyAccount,
        verbose_name=_("Hesap"),
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    kind = models.CharField(_("Tür"), max_length=20, choices=Kind.choices)
    points = models.IntegerField(_("Puan"), help_text=_("Kazanım pozitif, kullanım negatif."))
    order = models.ForeignKey(
        "operations.Order",
        verbose_name=_("Adisyon"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loyalty_transactions",
    )
    occurred_at = models.DateTimeField(_("Zaman"), default=timezone.now, db_index=True)
    expires_on = models.DateField(_("Geçerlilik"), null=True, blank=True)
    note = models.CharField(_("Not"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("Sadakat hareketi")
        verbose_name_plural = _("Sadakat hareketleri")
        ordering = ["-occurred_at"]

    def __str__(self) -> str:
        return f"{self.account.card_number} · {self.get_kind_display()} · {self.points:+d}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            raise ValueError("Sadakat hareketleri değiştirilemez.")
        super().save(*args, **kwargs)


class Campaign(TimeStampedModel):
    """Pazarlama kampanyası.

    NOT: Bu sürümde kampanya *tanımı* ve hedef kitle seçimi çalışır; toplu
    e-posta/SMS gönderimi **Planlandı** durumundadır ve etkin değildir.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Taslak")
        SCHEDULED = "scheduled", _("Planlandı")
        RUNNING = "running", _("Yürürlükte")
        ENDED = "ended", _("Sona erdi")
        CANCELLED = "cancelled", _("İptal")

    class Channel(models.TextChoices):
        IN_HOUSE = "in_house", _("İşletme içi (personel bilgilendirmesi)")
        EMAIL = "email", _("E-posta")
        SMS = "sms", _("SMS")

    name = models.CharField(_("Ad"), max_length=200)
    description = models.TextField(_("Açıklama"), blank=True)
    channel = models.CharField(
        _("Kanal"), max_length=20, choices=Channel.choices, default=Channel.IN_HOUSE
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    starts_on = models.DateField(_("Başlangıç"), null=True, blank=True)
    ends_on = models.DateField(_("Bitiş"), null=True, blank=True)
    target_segments = models.JSONField(_("Hedef segmentler"), default=list, blank=True)
    price_rule = models.ForeignKey(
        "catalog.PriceRule",
        verbose_name=_("Bağlı fiyat kuralı"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
    )
    #: Rıza kontrolü: pazarlama kanalları yalnızca rızası olanlara gösterilir
    requires_consent = models.BooleanField(_("Rıza gerektirir"), default=True)

    class Meta:
        verbose_name = _("Kampanya")
        verbose_name_plural = _("Kampanyalar")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    def eligible_customers(self) -> models.QuerySet[Customer]:
        """Kampanyaya uygun ve rızası olan müşteriler."""
        queryset = Customer.objects.filter(is_deleted=False, is_blacklisted=False)
        if self.target_segments:
            queryset = queryset.filter(segment__in=self.target_segments)
        if self.requires_consent and self.channel != self.Channel.IN_HOUSE:
            purpose = (
                ConsentRecord.Purpose.MARKETING_EMAIL
                if self.channel == self.Channel.EMAIL
                else ConsentRecord.Purpose.MARKETING_SMS
            )
            queryset = queryset.filter(
                consents__purpose=purpose,
                consents__is_granted=True,
                consents__withdrawn_at__isnull=True,
            )
        return queryset.distinct()


class CustomerVisitNote(TimeStampedModel):
    """Ziyarete özel not (misafir tercihi, şikâyet, övgü)."""

    class Kind(models.TextChoices):
        PREFERENCE = "preference", _("Tercih")
        COMPLAINT = "complaint", _("Şikâyet")
        COMPLIMENT = "compliment", _("Övgü")
        INCIDENT = "incident", _("Olay")
        GENERAL = "general", _("Genel")

    customer = models.ForeignKey(
        Customer, verbose_name=_("Müşteri"), on_delete=models.CASCADE, related_name="visit_notes"
    )
    order = models.ForeignKey(
        "operations.Order",
        verbose_name=_("Adisyon"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visit_notes",
    )
    kind = models.CharField(_("Tür"), max_length=20, choices=Kind.choices, default=Kind.GENERAL)
    note = models.TextField(_("Not"))
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Kaydeden"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_notes",
    )
    is_resolved = models.BooleanField(_("Çözüldü"), default=False)

    class Meta:
        verbose_name = _("Ziyaret notu")
        verbose_name_plural = _("Ziyaret notları")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.customer} · {self.get_kind_display()}"
