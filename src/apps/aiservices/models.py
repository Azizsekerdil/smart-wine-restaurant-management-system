"""Yapay zekâ modülü veri modelleri: sohbet, çağrı günlüğü, öneri ve maliyet."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class AIFeature(models.TextChoices):
    """Yapay zekânın kullanıldığı işlevler.

    Maliyet ve kullanım raporları bu ayrım üzerinden üretilir.
    """

    SOMMELIER = "sommelier", _("Sommelier asistanı")
    PAIRING = "pairing", _("Yemek–şarap eşleştirme")
    REPORT_QUERY = "report_query", _("Doğal dille rapor sorgulama")
    FORECAST = "forecast", _("Satış tahmini")
    INVENTORY = "inventory", _("Stok ve satın alma önerisi")
    WASTE = "waste", _("Fire / israf analizi")
    ANOMALY = "anomaly", _("Anormal işlem tespiti")
    CUSTOMER = "customer", _("Müşteri tercih analizi")
    MENU_TEXT = "menu_text", _("Menü açıklaması oluşturma")
    TRANSLATION = "translation", _("Çok dilli çeviri")
    VISION = "vision", _("Etiket / görsel analizi")
    TRAINING = "training", _("Personel eğitim asistanı")
    DECISION = "decision", _("Yönetici karar desteği")
    DAY_SUMMARY = "day_summary", _("Gün sonu yönetici özeti")
    DEVSTUDIO = "devstudio", _("AI Development Studio")
    CAIO = "caio", _("CAIO ajanı")
    OTHER = "other", _("Diğer")


class AIConversation(TimeStampedModel):
    """Bir yapay zekâ sohbet oturumu."""

    title = models.CharField(_("Başlık"), max_length=200, blank=True)
    feature = models.CharField(
        _("İşlev"), max_length=30, choices=AIFeature.choices, default=AIFeature.SOMMELIER
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Kullanıcı"),
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )
    provider = models.CharField(_("Sağlayıcı"), max_length=30, blank=True)
    model = models.CharField(_("Model"), max_length=120, blank=True)
    is_archived = models.BooleanField(_("Arşivlendi"), default=False)

    class Meta:
        verbose_name = _("Yapay zekâ sohbeti")
        verbose_name_plural = _("Yapay zekâ sohbetleri")
        ordering = ["-updated_at"]
        permissions = [
            ("can_use_cloud_ai", _("Bulut yapay zekâ sağlayıcısı kullanabilir")),
            ("can_configure_ai", _("Yapay zekâ ayarlarını değiştirebilir")),
            ("can_apply_ai_suggestion", _("Yapay zekâ önerisini uygulayabilir")),
            ("can_view_ai_costs", _("Yapay zekâ maliyetlerini görebilir")),
        ]

    def __str__(self) -> str:
        return self.title or f"{self.get_feature_display()} · {self.created_at:%d.%m.%Y %H:%M}"

    @property
    def total_tokens(self) -> int:
        return sum(call.total_tokens for call in self.calls.all())

    @property
    def total_cost_usd(self) -> Decimal:
        return sum((call.estimated_cost_usd for call in self.calls.all()), Decimal("0.000000"))


class AIMessage(TimeStampedModel):
    """Sohbetteki tek bir mesaj."""

    class Role(models.TextChoices):
        SYSTEM = "system", _("Sistem")
        USER = "user", _("Kullanıcı")
        ASSISTANT = "assistant", _("Asistan")

    conversation = models.ForeignKey(
        AIConversation, verbose_name=_("Sohbet"), on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(_("Rol"), max_length=20, choices=Role.choices)
    content = models.TextField(_("İçerik"))
    #: Buluta gönderilmeden önce maskelenmiş hâli (kullanıcı görebilir)
    masked_content = models.TextField(
        _("Maskelenmiş içerik"),
        blank=True,
        help_text=_("Bulut sağlayıcıya fiilen gönderilen metin."),
    )
    masking_summary = models.CharField(_("Maskeleme özeti"), max_length=250, blank=True)
    sequence = models.PositiveIntegerField(_("Sıra"), default=0)

    class Meta:
        verbose_name = _("Yapay zekâ mesajı")
        verbose_name_plural = _("Yapay zekâ mesajları")
        ordering = ["conversation", "sequence", "id"]

    def __str__(self) -> str:
        return f"{self.get_role_display()}: {self.content[:60]}"

    @property
    def was_masked(self) -> bool:
        return bool(self.masked_content) and self.masked_content != self.content


class AICallLog(TimeStampedModel):
    """Tek bir sağlayıcı çağrısının kaydı.

    Bu tablo hem maliyet raporlaması hem de sorun giderme için kullanılır.
    İstem ve yanıt metinleri saklanmaz — yalnızca üstveri tutulur (veri
    minimizasyonu). Ayrıntılı içerik ``AIMessage`` içindedir ve saklama
    süresi dolduğunda temizlenir.
    """

    class Outcome(models.TextChoices):
        SUCCESS = "success", _("Başarılı")
        FAILED = "failed", _("Başarısız")
        FALLBACK = "fallback", _("Yedek sağlayıcıya geçildi")
        CANCELLED = "cancelled", _("İptal edildi")
        BLOCKED = "blocked", _("Politika gereği engellendi")

    conversation = models.ForeignKey(
        AIConversation,
        verbose_name=_("Sohbet"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="calls",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Kullanıcı"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_calls",
    )
    feature = models.CharField(
        _("İşlev"), max_length=30, choices=AIFeature.choices, default=AIFeature.OTHER, db_index=True
    )
    provider = models.CharField(_("Sağlayıcı"), max_length=30, db_index=True)
    model = models.CharField(_("Model"), max_length=120, blank=True)
    is_local_provider = models.BooleanField(_("Yerel sağlayıcı"), default=True)

    prompt_tokens = models.PositiveIntegerField(_("İstem belirteci"), default=0)
    completion_tokens = models.PositiveIntegerField(_("Yanıt belirteci"), default=0)
    estimated_cost_usd = models.DecimalField(
        _("Tahmini maliyet (USD)"), max_digits=12, decimal_places=6, default=Decimal("0.000000")
    )
    latency_ms = models.PositiveIntegerField(_("Gecikme (ms)"), default=0)

    outcome = models.CharField(
        _("Sonuç"), max_length=20, choices=Outcome.choices, default=Outcome.SUCCESS, db_index=True
    )
    error_type = models.CharField(_("Hata türü"), max_length=80, blank=True)
    error_message = models.TextField(_("Hata mesajı"), blank=True)
    fallback_from = models.CharField(_("Yedeklenen sağlayıcı"), max_length=30, blank=True)

    pii_masked = models.BooleanField(_("Kişisel veri maskelendi"), default=False)
    masking_summary = models.CharField(_("Maskeleme özeti"), max_length=250, blank=True)
    occurred_at = models.DateTimeField(_("Zaman"), default=timezone.now, db_index=True)

    class Meta:
        verbose_name = _("Yapay zekâ çağrı kaydı")
        verbose_name_plural = _("Yapay zekâ çağrı kayıtları")
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["provider", "-occurred_at"], name="aicall_provider_ts_idx"),
            models.Index(fields=["feature", "-occurred_at"], name="aicall_feature_ts_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.provider} · {self.get_feature_display()} · {self.get_outcome_display()}"

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class ProviderPricing(TimeStampedModel):
    """Sağlayıcı/model fiyatlandırması (maliyet tahmini için).

    Fiyatlar **kullanıcı tarafından girilir**; uygulama hiçbir fiyatı
    varsaymaz. Fiyat girilmemişse maliyet 0 olarak raporlanır ve arayüzde
    "fiyat tanımlı değil" uyarısı gösterilir.
    """

    provider = models.CharField(_("Sağlayıcı"), max_length=30, db_index=True)
    model = models.CharField(_("Model"), max_length=120)
    input_usd_per_million = models.DecimalField(
        _("Girdi (USD / 1M belirteç)"), max_digits=12, decimal_places=4, default=Decimal("0.0000")
    )
    output_usd_per_million = models.DecimalField(
        _("Çıktı (USD / 1M belirteç)"), max_digits=12, decimal_places=4, default=Decimal("0.0000")
    )
    effective_from = models.DateField(_("Geçerlilik başlangıcı"), default=timezone.localdate)
    source_note = models.CharField(
        _("Kaynak notu"),
        max_length=250,
        blank=True,
        help_text=_("Fiyatın alındığı resmî sayfa ve tarih."),
    )
    is_active = models.BooleanField(_("Etkin"), default=True)

    class Meta:
        verbose_name = _("Sağlayıcı fiyatı")
        verbose_name_plural = _("Sağlayıcı fiyatları")
        ordering = ["provider", "model", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "model", "effective_from"], name="uniq_pricing_period"
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider}/{self.model}"


class AIBudget(TimeStampedModel):
    """Aylık yapay zekâ maliyet bütçesi ve harcama takibi."""

    period_year = models.PositiveSmallIntegerField(_("Yıl"))
    period_month = models.PositiveSmallIntegerField(_("Ay"))
    limit_usd = models.DecimalField(
        _("Üst sınır (USD)"), max_digits=12, decimal_places=2, default=Decimal("10.00")
    )
    spent_usd = models.DecimalField(
        _("Harcanan (USD)"), max_digits=12, decimal_places=6, default=Decimal("0.000000")
    )
    warn_at_percent = models.PositiveSmallIntegerField(_("Uyarı eşiği (%)"), default=80)
    is_hard_limit = models.BooleanField(
        _("Kesin sınır"),
        default=True,
        help_text=_("Açıkken sınır aşıldığında bulut çağrıları engellenir."),
    )

    class Meta:
        verbose_name = _("Yapay zekâ bütçesi")
        verbose_name_plural = _("Yapay zekâ bütçeleri")
        ordering = ["-period_year", "-period_month"]
        constraints = [
            models.UniqueConstraint(
                fields=["period_year", "period_month"], name="uniq_ai_budget_period"
            )
        ]

    def __str__(self) -> str:
        return f"{self.period_year}-{self.period_month:02d} · {self.spent_usd}/{self.limit_usd} USD"

    @property
    def usage_percent(self) -> Decimal:
        if not self.limit_usd:
            return Decimal("0.00")
        return (self.spent_usd / self.limit_usd * 100).quantize(Decimal("0.01"))

    @property
    def is_exceeded(self) -> bool:
        return bool(self.limit_usd) and self.spent_usd >= self.limit_usd

    @property
    def should_warn(self) -> bool:
        return self.usage_percent >= self.warn_at_percent


class AISuggestion(TimeStampedModel):
    """Yapay zekânın ürettiği ve **insan onayı bekleyen** öneri.

    TEMEL GÜVENLİK KURALI: Yapay zekâ hiçbir koşulda veritabanında doğrudan
    kritik değişiklik yapmaz. Her öneri önce bu tabloya yazılır, kullanıcıya
    gösterilir ve yalnızca açık onaydan sonra uygulanır.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Onay bekliyor")
        APPROVED = "approved", _("Onaylandı")
        APPLIED = "applied", _("Uygulandı")
        REJECTED = "rejected", _("Reddedildi")
        EXPIRED = "expired", _("Süresi doldu")
        FAILED = "failed", _("Uygulama başarısız")

    class Kind(models.TextChoices):
        WINE_PAIRING = "wine_pairing", _("Şarap eşleştirmesi")
        MENU_DESCRIPTION = "menu_description", _("Menü açıklaması")
        TASTING_NOTE = "tasting_note", _("Tadım notu")
        PURCHASE_ORDER = "purchase_order", _("Satın alma önerisi")
        PRICE_CHANGE = "price_change", _("Fiyat değişikliği")
        STOCK_ADJUSTMENT = "stock_adjustment", _("Stok düzeltmesi")
        TRANSLATION = "translation", _("Çeviri")
        REPORT_INSIGHT = "report_insight", _("Rapor içgörüsü")
        CODE_CHANGE = "code_change", _("Kod değişikliği")
        OTHER = "other", _("Diğer")

    kind = models.CharField(_("Tür"), max_length=30, choices=Kind.choices, db_index=True)
    title = models.CharField(_("Başlık"), max_length=250)
    summary = models.TextField(_("Özet"), blank=True)
    #: Uygulanacak yapılandırılmış veri (alan → yeni değer)
    payload = models.JSONField(_("Öneri verisi"), default=dict, blank=True)
    #: Değişimden önceki hâl (geri alma için)
    previous_state = models.JSONField(_("Önceki durum"), default=dict, blank=True)

    target_type = models.CharField(_("Hedef türü"), max_length=100, blank=True)
    target_id = models.CharField(_("Hedef kimliği"), max_length=64, blank=True)

    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    confidence = models.DecimalField(
        _("Güven"), max_digits=5, decimal_places=2, default=Decimal("0.00")
    )

    call_log = models.ForeignKey(
        AICallLog,
        verbose_name=_("Çağrı kaydı"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suggestions",
    )
    created_for = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Öneri sahibi"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_suggestions",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Onaylayan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_suggestions_reviewed",
    )
    reviewed_at = models.DateTimeField(_("Onay zamanı"), null=True, blank=True)
    applied_at = models.DateTimeField(_("Uygulama zamanı"), null=True, blank=True)
    review_note = models.TextField(_("Karar notu"), blank=True)
    error_message = models.TextField(_("Hata"), blank=True)

    class Meta:
        verbose_name = _("Yapay zekâ önerisi")
        verbose_name_plural = _("Yapay zekâ önerileri")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="aisuggestion_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · {self.title[:60]}"

    @property
    def is_actionable(self) -> bool:
        return self.status == self.Status.PENDING


class AIQualityFeedback(TimeStampedModel):
    """Yapay zekâ yanıtına verilen kalite geri bildirimi.

    CAIO ajanı bu kayıtları izleyerek zayıf yanıtları ve tekrar eden
    sorunları raporlar.
    """

    class Rating(models.IntegerChoices):
        BAD = 1, _("Kötü")
        POOR = 2, _("Zayıf")
        OK = 3, _("İdare eder")
        GOOD = 4, _("İyi")
        EXCELLENT = 5, _("Mükemmel")

    call_log = models.ForeignKey(
        AICallLog, verbose_name=_("Çağrı"), on_delete=models.CASCADE, related_name="feedback"
    )
    message = models.ForeignKey(
        AIMessage,
        verbose_name=_("Mesaj"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="feedback",
    )
    rating = models.PositiveSmallIntegerField(_("Puan"), choices=Rating.choices)
    issue_tags = models.JSONField(
        _("Sorun etiketleri"),
        default=list,
        blank=True,
        help_text=_("Örn: ['yanlış_bilgi', 'alakasız', 'çok_uzun', 'dil_hatası']"),
    )
    comment = models.TextField(_("Yorum"), blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Bildiren"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_feedback",
    )

    class Meta:
        verbose_name = _("Yapay zekâ geri bildirimi")
        verbose_name_plural = _("Yapay zekâ geri bildirimleri")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_rating_display()} · {self.call_log.provider}"
