"""Yedekleme ve geri yükleme modelleri."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class BackupRecord(TimeStampedModel):
    """Alınan yedeğin kaydı ve bütünlük özeti."""

    class Kind(models.TextChoices):
        MANUAL = "manual", _("El ile")
        SCHEDULED = "scheduled", _("Zamanlanmış")
        PRE_RESTORE = "pre_restore", _("Geri yükleme öncesi")
        PRE_UPGRADE = "pre_upgrade", _("Güncelleme öncesi")

    class Status(models.TextChoices):
        RUNNING = "running", _("Alınıyor")
        SUCCESS = "success", _("Başarılı")
        FAILED = "failed", _("Başarısız")
        VERIFIED = "verified", _("Doğrulandı")
        CORRUPT = "corrupt", _("Bozuk")

    file_name = models.CharField(_("Dosya adı"), max_length=255)
    file_path = models.CharField(_("Dosya yolu"), max_length=500)
    kind = models.CharField(_("Tür"), max_length=20, choices=Kind.choices, default=Kind.MANUAL)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.RUNNING, db_index=True
    )
    size_bytes = models.BigIntegerField(_("Boyut (bayt)"), default=0)
    is_encrypted = models.BooleanField(_("Şifreli"), default=True)
    #: SHA-256 özeti — geri yüklemeden önce bütünlük doğrulaması için
    checksum_sha256 = models.CharField(_("SHA-256 özeti"), max_length=64, blank=True)
    started_at = models.DateTimeField(_("Başlangıç"), default=timezone.now)
    finished_at = models.DateTimeField(_("Bitiş"), null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Alan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backups_created",
    )
    app_version = models.CharField(_("Uygulama sürümü"), max_length=20, blank=True)
    database_engine = models.CharField(_("Veritabanı"), max_length=40, blank=True)
    record_counts = models.JSONField(_("Kayıt sayıları"), default=dict, blank=True)
    error_message = models.TextField(_("Hata"), blank=True)
    verified_at = models.DateTimeField(_("Doğrulama zamanı"), null=True, blank=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Yedek kaydı")
        verbose_name_plural = _("Yedek kayıtları")
        ordering = ["-started_at"]
        permissions = [
            ("can_run_backup", _("Yedek alabilir")),
            ("can_restore_backup", _("Yedekten geri yükleyebilir")),
            ("can_configure_backup", _("Yedekleme ayarlarını değiştirebilir")),
        ]

    def __str__(self) -> str:
        return f"{self.file_name} · {self.get_status_display()}"

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 2)

    @property
    def duration_seconds(self) -> int:
        if not self.finished_at:
            return 0
        return int((self.finished_at - self.started_at).total_seconds())

    @property
    def age_days(self) -> int:
        return (timezone.now() - self.started_at).days


class RestoreRecord(TimeStampedModel):
    """Geri yükleme işlemi kaydı.

    Geri yükleme kritik bir işlemdir ve her zaman bir ``ApprovalRequest``
    gerektirir. İşlemden önce otomatik olarak güvenlik yedeği alınır.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Onay bekliyor")
        RUNNING = "running", _("Yükleniyor")
        SUCCESS = "success", _("Başarılı")
        FAILED = "failed", _("Başarısız")
        ROLLED_BACK = "rolled_back", _("Geri alındı")

    class Target(models.TextChoices):
        PRODUCTION = "production", _("Canlı veritabanı")
        TEST = "test", _("Test veritabanı")

    backup = models.ForeignKey(
        BackupRecord, verbose_name=_("Yedek"), on_delete=models.PROTECT, related_name="restores"
    )
    target = models.CharField(
        _("Hedef"), max_length=20, choices=Target.choices, default=Target.TEST
    )
    target_path = models.CharField(_("Hedef yol"), max_length=500, blank=True)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.PENDING
    )
    safety_backup = models.ForeignKey(
        BackupRecord,
        verbose_name=_("Güvenlik yedeği"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="safety_for_restores",
    )
    approval = models.ForeignKey(
        "accounts.ApprovalRequest",
        verbose_name=_("Onay"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restores",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Talep eden"),
        on_delete=models.PROTECT,
        related_name="restores_requested",
    )
    started_at = models.DateTimeField(_("Başlangıç"), null=True, blank=True)
    finished_at = models.DateTimeField(_("Bitiş"), null=True, blank=True)
    verification_report = models.JSONField(_("Doğrulama raporu"), default=dict, blank=True)
    error_message = models.TextField(_("Hata"), blank=True)

    class Meta:
        verbose_name = _("Geri yükleme kaydı")
        verbose_name_plural = _("Geri yükleme kayıtları")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.backup.file_name} → {self.get_target_display()}"


class BackupSchedule(TimeStampedModel):
    """Zamanlanmış yedekleme yapılandırması.

    Windows Görev Zamanlayıcı (Task Scheduler) veya ``BACKUP_WINE_HOUSE.bat``
    tarafından tetiklenir; uygulama içinde ayrı bir arka plan servisi
    çalıştırılmaz (yerel-öncelikli mimari).
    """

    class Frequency(models.TextChoices):
        HOURLY = "hourly", _("Saatlik")
        DAILY = "daily", _("Günlük")
        WEEKLY = "weekly", _("Haftalık")

    name = models.CharField(_("Ad"), max_length=120, unique=True)
    frequency = models.CharField(
        _("Sıklık"), max_length=20, choices=Frequency.choices, default=Frequency.DAILY
    )
    run_at = models.TimeField(_("Çalışma saati"), null=True, blank=True)
    destination_dir = models.CharField(_("Hedef klasör"), max_length=500)
    retention_days = models.PositiveSmallIntegerField(_("Saklama süresi (gün)"), default=30)
    encrypt = models.BooleanField(_("Şifrele"), default=True)
    verify_after_backup = models.BooleanField(_("Yedek sonrası doğrula"), default=True)
    is_active = models.BooleanField(_("Etkin"), default=True)
    last_run_at = models.DateTimeField(_("Son çalışma"), null=True, blank=True)
    last_status = models.CharField(_("Son durum"), max_length=40, blank=True)

    class Meta:
        verbose_name = _("Yedekleme planı")
        verbose_name_plural = _("Yedekleme planları")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} · {self.get_frequency_display()}"
