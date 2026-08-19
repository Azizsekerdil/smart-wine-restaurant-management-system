"""Sürümlü hukuki kural paketi modelleri (prompt §6).

Hukuki hükümler koda gömülmez; imzalanabilir ve **insan onaylı**
``LegalRulePack`` kayıtlarında yaşar. Temel ilkeler:

* Paket, insan onayı olmadan ``ACTIVE`` olamaz; onay checksum + imza üretir.
* Onaydan sonra kural içeriği değişirse imza geçersizleşir ve motor paketi
  kullanmaz (fail-closed).
* Her kural resmî kaynağa (``LegalSource``) bağlanır; kaynak yoksa kural
  uydurulmaz.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class Jurisdiction(models.TextChoices):
    TR = "TR", _("Türkiye")
    EU = "EU", _("AB/AEA")


class LegalSource(TimeStampedModel):
    """Resmî hukuki kaynak kaydı (seed registry, prompt §34)."""

    jurisdiction = models.CharField(
        _("Hukuk bölgesi"), max_length=8, choices=Jurisdiction.choices, db_index=True
    )
    title = models.CharField(_("Başlık"), max_length=255)
    url = models.URLField(_("Resmî kaynak URL"), max_length=500)
    authority = models.CharField(_("Otorite"), max_length=120)
    article = models.CharField(_("Madde/karar"), max_length=120, blank=True)
    retrieved_on = models.DateField(
        _("Erişim tarihi"),
        null=True,
        blank=True,
        help_text=_("Kaynağın son doğrulandığı tarih; boşsa güncellik doğrulanmamıştır."),
    )
    content_hash = models.CharField(
        _("İçerik hash'i"),
        max_length=64,
        blank=True,
        help_text=_("Kaynak metnin SHA-256 özeti; boşsa metin henüz arşivlenmemiştir."),
    )
    note = models.CharField(_("Not"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("Hukuki kaynak")
        verbose_name_plural = _("Hukuki kaynaklar")
        ordering = ["jurisdiction", "title"]

    def __str__(self) -> str:
        return f"[{self.jurisdiction}] {self.title}"


class LegalRulePack(TimeStampedModel):
    """Sürümlü, imzalı kural paketi."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Taslak")
        ACTIVE = "active", _("Yürürlükte")
        RETIRED = "retired", _("Emekli")

    jurisdiction = models.CharField(
        _("Hukuk bölgesi"), max_length=8, choices=Jurisdiction.choices, db_index=True
    )
    regulation_code = models.CharField(_("Mevzuat kodu"), max_length=30, db_index=True)
    version = models.PositiveIntegerField(_("Sürüm"), default=1)
    status = models.CharField(
        _("Durum"), max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    checksum = models.CharField(_("Checksum"), max_length=64, blank=True)
    signature = models.CharField(_("İmza"), max_length=64, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Onaylayan"),
        related_name="approved_rulepacks",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(_("Onay zamanı"), null=True, blank=True)
    release_note = models.CharField(_("Sürüm notu"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("Hukuki kural paketi")
        verbose_name_plural = _("Hukuki kural paketleri")
        ordering = ["jurisdiction", "regulation_code", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["jurisdiction", "regulation_code", "version"],
                name="uniq_rulepack_version",
            )
        ]

    def __str__(self) -> str:
        return f"{self.regulation_code} v{self.version} ({self.status})"


class DeadlineUnit(models.TextChoices):
    HOURS = "hours", _("Saat")
    DAYS = "days", _("Takvim günü")
    BUSINESS_DAYS = "business_days", _("İş günü")
    MONTHS = "months", _("Ay")


class LegalRule(TimeStampedModel):
    """Tek hukuki kural kaydı.

    ``deadline_value``/``deadline_unit`` doluysa kural bir süre hesabı tanımlar
    (ör. ihlal bildirimi 72 saat, DSR yanıtı 30 gün).
    """

    class Severity(models.TextChoices):
        INFO = "info", _("Bilgi")
        MEDIUM = "medium", _("Orta")
        HIGH = "high", _("Yüksek")
        CRITICAL = "critical", _("Kritik")

    pack = models.ForeignKey(
        LegalRulePack, verbose_name=_("Paket"), related_name="rules", on_delete=models.CASCADE
    )
    rule_code = models.CharField(_("Kural kodu"), max_length=60, db_index=True)
    title_tr = models.CharField(_("Başlık (TR)"), max_length=255)
    title_en = models.CharField(_("Başlık (EN)"), max_length=255)
    description = models.TextField(_("Açıklama"), blank=True)
    source = models.ForeignKey(
        LegalSource,
        verbose_name=_("Resmî kaynak"),
        related_name="rules",
        on_delete=models.PROTECT,
    )
    article = models.CharField(_("Madde"), max_length=120, blank=True)
    severity = models.CharField(
        _("Önem"), max_length=10, choices=Severity.choices, default=Severity.HIGH
    )
    deadline_value = models.PositiveIntegerField(_("Süre değeri"), null=True, blank=True)
    deadline_unit = models.CharField(
        _("Süre birimi"), max_length=16, choices=DeadlineUnit.choices, blank=True
    )
    requires_human_review = models.BooleanField(_("İnsan incelemesi gerekli"), default=True)
    evidence_requirements = models.JSONField(_("Kanıt gereksinimleri"), default=list, blank=True)

    class Meta:
        verbose_name = _("Hukuki kural")
        verbose_name_plural = _("Hukuki kurallar")
        ordering = ["pack", "rule_code"]
        constraints = [
            models.UniqueConstraint(fields=["pack", "rule_code"], name="uniq_rule_per_pack")
        ]

    def __str__(self) -> str:
        return f"{self.rule_code} ({self.pack.regulation_code} v{self.pack.version})"
