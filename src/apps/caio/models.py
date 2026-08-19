"""CAIO ajanı modelleri.

CAIO (Continuous AI Improvement Observer), sistemin kendi kendini
gözlemleyen katmanıdır. Yapay zekâ yanıt kalitesini, maliyeti, hataları ve
kullanım örüntülerini izler; **öneri** üretir.

KESİN SINIR: CAIO hiçbir koşulda
  * üretim kodunu kendiliğinden değiştiremez,
  * dal birleştiremez,
  * sürüm yayınlayamaz,
  * kullanıcı verisini buluta gönderemez.
Her çıktısı insan onayı bekleyen bir öneridir.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class ObservationRun(TimeStampedModel):
    """CAIO'nun tek bir gözlem koşumu."""

    class Trigger(models.TextChoices):
        MANUAL = "manual", _("El ile")
        SCHEDULED = "scheduled", _("Zamanlanmış")
        POST_DAY_END = "post_day_end", _("Gün sonu sonrası")

    class Status(models.TextChoices):
        RUNNING = "running", _("Çalışıyor")
        COMPLETED = "completed", _("Tamamlandı")
        FAILED = "failed", _("Başarısız")

    trigger = models.CharField(
        _("Tetikleyici"), max_length=20, choices=Trigger.choices, default=Trigger.MANUAL
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.RUNNING
    )
    period_start = models.DateTimeField(_("Dönem başı"))
    period_end = models.DateTimeField(_("Dönem sonu"))
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Başlatan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="caio_runs",
    )

    # --- Toplanan ölçümler ---
    ai_calls_examined = models.PositiveIntegerField(_("İncelenen çağrı"), default=0)
    failed_calls = models.PositiveIntegerField(_("Başarısız çağrı"), default=0)
    fallback_calls = models.PositiveIntegerField(_("Yedeğe düşen çağrı"), default=0)
    low_rated_responses = models.PositiveIntegerField(_("Düşük puanlı yanıt"), default=0)
    total_tokens = models.PositiveIntegerField(_("Toplam belirteç"), default=0)
    total_cost_usd = models.DecimalField(
        _("Toplam maliyet (USD)"), max_digits=12, decimal_places=6, default=Decimal("0")
    )
    average_latency_ms = models.PositiveIntegerField(_("Ortalama gecikme (ms)"), default=0)
    findings_count = models.PositiveIntegerField(_("Bulgu sayısı"), default=0)

    summary = models.TextField(_("Özet"), blank=True)
    error_message = models.TextField(_("Hata"), blank=True)
    finished_at = models.DateTimeField(_("Bitiş"), null=True, blank=True)

    class Meta:
        verbose_name = _("CAIO gözlem koşumu")
        verbose_name_plural = _("CAIO gözlem koşumları")
        ordering = ["-created_at"]
        permissions = [
            ("can_run_caio", _("CAIO gözlemi başlatabilir")),
            ("can_review_caio_findings", _("CAIO bulgularını inceleyebilir")),
        ]

    def __str__(self) -> str:
        return f"CAIO · {self.created_at:%d.%m.%Y %H:%M} · {self.findings_count} bulgu"

    @property
    def failure_rate(self) -> Decimal:
        if not self.ai_calls_examined:
            return Decimal("0.00")
        return (Decimal(self.failed_calls) / Decimal(self.ai_calls_examined) * 100).quantize(
            Decimal("0.01")
        )


class Finding(TimeStampedModel):
    """CAIO'nun tespit ettiği tek bir bulgu ve önerisi."""

    class Category(models.TextChoices):
        AI_QUALITY = "ai_quality", _("Yapay zekâ yanıt kalitesi")
        AI_COST = "ai_cost", _("Yapay zekâ maliyeti")
        AI_RELIABILITY = "ai_reliability", _("Sağlayıcı güvenilirliği")
        PERFORMANCE = "performance", _("Başarım")
        ERROR_PATTERN = "error_pattern", _("Tekrar eden hata")
        UX = "ux", _("Kullanıcı deneyimi")
        DATA_QUALITY = "data_quality", _("Veri kalitesi")
        REPORT_ACCURACY = "report_accuracy", _("Rapor doğruluğu")
        FEATURE_IDEA = "feature_idea", _("Yeni özellik önerisi")
        SECURITY = "security", _("Güvenlik")

    class Severity(models.TextChoices):
        INFO = "info", _("Bilgi")
        LOW = "low", _("Düşük")
        MEDIUM = "medium", _("Orta")
        HIGH = "high", _("Yüksek")
        CRITICAL = "critical", _("Kritik")

    class Status(models.TextChoices):
        OPEN = "open", _("Açık")
        ACKNOWLEDGED = "acknowledged", _("Görüldü")
        PLANNED = "planned", _("Planlandı")
        IN_PROGRESS = "in_progress", _("Üzerinde çalışılıyor")
        RESOLVED = "resolved", _("Çözüldü")
        DISMISSED = "dismissed", _("Kapatıldı")

    run = models.ForeignKey(
        ObservationRun,
        verbose_name=_("Koşum"),
        on_delete=models.CASCADE,
        related_name="findings",
        null=True,
        blank=True,
    )
    category = models.CharField(
        _("Kategori"), max_length=30, choices=Category.choices, db_index=True
    )
    severity = models.CharField(
        _("Önem"), max_length=20, choices=Severity.choices, default=Severity.LOW, db_index=True
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    title = models.CharField(_("Başlık"), max_length=250)
    description = models.TextField(_("Açıklama"))
    evidence = models.JSONField(_("Kanıt"), default=dict, blank=True)
    recommendation = models.TextField(_("Öneri"), blank=True)
    #: Aynı bulgunun tekrar üretilmesini önleyen kararlı anahtar
    fingerprint = models.CharField(_("Parmak izi"), max_length=64, db_index=True)
    occurrence_count = models.PositiveIntegerField(_("Tekrar sayısı"), default=1)
    first_seen_at = models.DateTimeField(_("İlk görülme"), default=timezone.now)
    last_seen_at = models.DateTimeField(_("Son görülme"), default=timezone.now)

    #: Bulgudan üretilen yama önerisi (varsa)
    dev_session = models.ForeignKey(
        "devstudio.DevSession",
        verbose_name=_("Geliştirme oturumu"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="caio_findings",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("İnceleyen"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="caio_findings_reviewed",
    )
    review_note = models.TextField(_("İnceleme notu"), blank=True)

    class Meta:
        verbose_name = _("CAIO bulgusu")
        verbose_name_plural = _("CAIO bulguları")
        ordering = ["-severity", "-last_seen_at"]
        constraints = [
            models.UniqueConstraint(fields=["fingerprint"], name="uniq_finding_fingerprint")
        ]

    def __str__(self) -> str:
        return f"[{self.get_severity_display()}] {self.title}"

    @property
    def severity_badge_class(self) -> str:
        return {
            self.Severity.INFO: "bg-secondary",
            self.Severity.LOW: "bg-info text-dark",
            self.Severity.MEDIUM: "bg-warning text-dark",
            self.Severity.HIGH: "bg-danger",
            self.Severity.CRITICAL: "bg-dark",
        }.get(self.Severity(self.severity), "bg-secondary")


class ImprovementTask(TimeStampedModel):
    """CAIO'nun ürettiği geliştirme görevi (yol haritası maddesi)."""

    class Priority(models.IntegerChoices):
        LOW = 1, _("Düşük")
        NORMAL = 2, _("Normal")
        HIGH = 3, _("Yüksek")
        URGENT = 4, _("Acil")

    class Status(models.TextChoices):
        BACKLOG = "backlog", _("Bekleyen")
        APPROVED = "approved", _("Onaylandı")
        IN_PROGRESS = "in_progress", _("Devam ediyor")
        DONE = "done", _("Tamamlandı")
        CANCELLED = "cancelled", _("İptal")

    title = models.CharField(_("Başlık"), max_length=250)
    description = models.TextField(_("Açıklama"), blank=True)
    priority = models.PositiveSmallIntegerField(
        _("Öncelik"), choices=Priority.choices, default=Priority.NORMAL
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.BACKLOG, db_index=True
    )
    findings = models.ManyToManyField(
        Finding, verbose_name=_("İlgili bulgular"), blank=True, related_name="tasks"
    )
    target_release = models.CharField(_("Hedef sürüm"), max_length=20, blank=True)
    estimated_effort_hours = models.PositiveSmallIntegerField(_("Tahmini efor (saat)"), default=0)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Onaylayan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="caio_tasks_approved",
    )

    class Meta:
        verbose_name = _("Geliştirme görevi")
        verbose_name_plural = _("Geliştirme görevleri")
        ordering = ["-priority", "-created_at"]

    def __str__(self) -> str:
        return f"[{self.get_priority_display()}] {self.title}"


class ReleaseNoteDraft(TimeStampedModel):
    """CAIO'nun hazırladığı sürüm notu taslağı.

    Taslak, insan onayı olmadan yayınlanmaz.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Taslak")
        REVIEWED = "reviewed", _("İncelendi")
        PUBLISHED = "published", _("Yayınlandı")

    version = models.CharField(_("Sürüm"), max_length=20)
    period_start = models.DateField(_("Dönem başı"))
    period_end = models.DateField(_("Dönem sonu"))
    content_tr = models.TextField(_("İçerik (TR)"))
    content_en = models.TextField(_("İçerik (EN)"), blank=True)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Onaylayan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="release_notes_approved",
    )

    class Meta:
        verbose_name = _("Sürüm notu taslağı")
        verbose_name_plural = _("Sürüm notu taslakları")
        ordering = ["-period_end"]

    def __str__(self) -> str:
        return f"{self.version} · {self.get_status_display()}"


class ExportValidationResult(TimeStampedModel):
    """PDF/Excel/CSV dışa aktarımlarının doğruluk denetimi sonucu.

    CAIO, üretilen dosyaları yeniden okuyup kaynak veriyle karşılaştırır;
    böylece Türkçe karakter, sayı biçimi veya toplam hataları yakalanır.
    """

    class Result(models.TextChoices):
        PASSED = "passed", _("Geçti")
        FAILED = "failed", _("Başarısız")
        SKIPPED = "skipped", _("Atlandı")

    run = models.ForeignKey(
        ObservationRun,
        verbose_name=_("Koşum"),
        on_delete=models.CASCADE,
        related_name="export_validations",
        null=True,
        blank=True,
    )
    report_code = models.CharField(_("Rapor kodu"), max_length=80)
    output_format = models.CharField(_("Biçim"), max_length=10)
    result = models.CharField(_("Sonuç"), max_length=20, choices=Result.choices)
    checked_rows = models.PositiveIntegerField(_("Denetlenen satır"), default=0)
    mismatches = models.JSONField(_("Uyuşmazlıklar"), default=list, blank=True)
    turkish_characters_ok = models.BooleanField(_("Türkçe karakterler doğru"), default=True)
    totals_ok = models.BooleanField(_("Toplamlar doğru"), default=True)
    detail = models.TextField(_("Ayrıntı"), blank=True)

    class Meta:
        verbose_name = _("Dışa aktarım doğrulaması")
        verbose_name_plural = _("Dışa aktarım doğrulamaları")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.report_code}.{self.output_format} · {self.get_result_display()}"
