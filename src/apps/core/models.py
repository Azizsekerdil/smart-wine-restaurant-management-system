"""Çekirdek modeller: taban sınıflar, denetim kaydı, uygulama ayarları."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.fields import EncryptedTextField


# ---------------------------------------------------------------------------
# Taban sınıflar
# ---------------------------------------------------------------------------
class TimeStampedModel(models.Model):
    """Oluşturulma/güncellenme zamanı ve sorumlu kullanıcı taşıyan taban model."""

    created_at = models.DateTimeField(_("Oluşturulma"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("Güncellenme"), auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Oluşturan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Güncelleyen"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
    )

    class Meta:
        abstract = True


class ActiveQuerySet(models.QuerySet):
    """Yumuşak silme destekli sorgu kümesi."""

    def active(self) -> ActiveQuerySet:
        return self.filter(is_deleted=False)

    def deleted(self) -> ActiveQuerySet:
        return self.filter(is_deleted=True)


class SoftDeleteModel(TimeStampedModel):
    """Kaydı fiziksel olarak silmeyen, arşivleyen taban model.

    Mali ve denetim izlenebilirliği için sipariş, ödeme ve stok hareketi gibi
    kayıtlar asla fiziksel olarak silinmez.
    """

    is_deleted = models.BooleanField(_("Silindi"), default=False, db_index=True)
    deleted_at = models.DateTimeField(_("Silinme zamanı"), null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Silen"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_deleted",
    )

    objects = ActiveQuerySet.as_manager()

    class Meta:
        abstract = True

    def soft_delete(self, user: Any = None) -> None:
        """Kaydı arşivler (fiziksel silme yapılmaz)."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user is not None and getattr(user, "pk", None):
            self.deleted_by = user
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])

    def restore(self) -> None:
        """Arşivlenmiş kaydı geri getirir."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])


# ---------------------------------------------------------------------------
# Denetim kaydı
# ---------------------------------------------------------------------------
class AuditAction(models.TextChoices):
    """Denetim kaydına yazılan işlem türleri."""

    CREATE = "create", _("Oluşturma")
    UPDATE = "update", _("Güncelleme")
    DELETE = "delete", _("Silme")
    VIEW = "view", _("Görüntüleme")
    LOGIN = "login", _("Giriş")
    LOGIN_FAILED = "login_failed", _("Başarısız giriş")
    LOGOUT = "logout", _("Çıkış")
    PERMISSION_DENIED = "permission_denied", _("Yetki reddi")
    EXPORT = "export", _("Dışa aktarım")
    IMPORT = "import", _("İçe aktarım")
    BACKUP = "backup", _("Yedekleme")
    RESTORE = "restore", _("Geri yükleme")
    PAYMENT = "payment", _("Ödeme")
    REFUND = "refund", _("İade")
    VOID = "void", _("İptal")
    DISCOUNT = "discount", _("İndirim")
    STOCK_ADJUST = "stock_adjust", _("Stok düzeltme")
    WASTE = "waste", _("Fire kaydı")
    AI_REQUEST = "ai_request", _("Yapay zekâ isteği")
    AI_APPLY = "ai_apply", _("Yapay zekâ önerisi uygulama")
    DEVSTUDIO = "devstudio", _("Geliştirici stüdyosu işlemi")
    SETTINGS = "settings", _("Ayar değişikliği")
    CONSENT = "consent", _("Rıza kaydı")
    DATA_ERASURE = "data_erasure", _("Veri silme talebi")


class AuditSeverity(models.TextChoices):
    INFO = "info", _("Bilgi")
    NOTICE = "notice", _("Dikkat")
    WARNING = "warning", _("Uyarı")
    CRITICAL = "critical", _("Kritik")


class AuditLog(models.Model):
    """Değiştirilemez denetim kaydı.

    Bu tablo yalnızca *eklenir*; uygulama içinden güncelleme ve silme
    yapılmaz. Saklama süresi ``DATA_RETENTION_DAYS['audit_log']`` ile
    yönetilir ve süresi dolan kayıtlar ayrı bir yönetim komutuyla arşivlenir.
    """

    timestamp = models.DateTimeField(_("Zaman"), default=timezone.now, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Kullanıcı"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    actor_label = models.CharField(
        _("Kullanıcı etiketi"),
        max_length=150,
        blank=True,
        help_text=_("Kullanıcı silinse bile iz kalması için kopyalanan kullanıcı adı."),
    )
    action = models.CharField(_("İşlem"), max_length=32, choices=AuditAction.choices, db_index=True)
    severity = models.CharField(
        _("Önem"), max_length=16, choices=AuditSeverity.choices, default=AuditSeverity.INFO
    )
    object_type = models.CharField(_("Nesne türü"), max_length=100, blank=True, db_index=True)
    object_id = models.CharField(_("Nesne kimliği"), max_length=64, blank=True, db_index=True)
    object_repr = models.CharField(_("Nesne özeti"), max_length=255, blank=True)
    changes = models.JSONField(_("Değişiklikler"), default=dict, blank=True)
    message = models.TextField(_("Açıklama"), blank=True)
    ip_address = models.GenericIPAddressField(_("IP adresi"), null=True, blank=True)
    user_agent = models.CharField(_("İstemci"), max_length=255, blank=True)
    success = models.BooleanField(_("Başarılı"), default=True)
    # Bütünlük zinciri (bkz. apps.core.integrity). Boş değer = zincirsiz
    # (eski kayıt veya zincirleme sırasında hata) — doğrulamada raporlanır.
    prev_hash = models.CharField(_("Önceki hash"), max_length=64, blank=True, default="")
    integrity_hash = models.CharField(
        _("Bütünlük hash'i"), max_length=64, blank=True, default="", db_index=True
    )
    signature = models.CharField(_("İmza"), max_length=64, blank=True, default="")

    class Meta:
        verbose_name = _("Denetim kaydı")
        verbose_name_plural = _("Denetim kayıtları")
        ordering = ["-timestamp", "-id"]
        indexes = [
            models.Index(fields=["action", "-timestamp"], name="audit_action_ts_idx"),
            models.Index(fields=["object_type", "object_id"], name="audit_object_idx"),
            models.Index(fields=["actor", "-timestamp"], name="audit_actor_ts_idx"),
        ]

    def __str__(self) -> str:
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.actor_label or '-'} · {self.action}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Var olan bir denetim kaydının güncellenmesini engeller.

        Yeni kayıt, mümkünse hash zincirine bağlanır; zincirleme hatası
        denetim yazımını asla engellemez (kayıt zincirsiz düşer ve
        doğrulamada raporlanır).
        """
        if self.pk is not None:
            raise ValueError("Denetim kayıtları değiştirilemez (append-only).")
        if not self.integrity_hash:
            try:
                from apps.core import integrity

                last = AuditLog.objects.exclude(integrity_hash="").order_by("-id").first()
                self.prev_hash = last.integrity_hash if last else integrity.GENESIS
                self.integrity_hash = integrity.compute_hash(
                    self.prev_hash, integrity.audit_payload(self)
                )
                self.signature = integrity.sign(self.integrity_hash)
            except Exception:  # pragma: no cover - zincir hatası yazımı bozmamalı
                self.prev_hash = ""
                self.integrity_hash = ""
                self.signature = ""
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> None:
        """Denetim kaydının uygulama içinden silinmesini engeller."""
        raise ValueError(
            "Denetim kayıtları uygulama içinden silinemez. "
            "Saklama süresi dolan kayıtlar için 'purge_audit_log' komutunu kullanın."
        )


# ---------------------------------------------------------------------------
# Uygulama ayarları (veritabanında saklanan, arayüzden düzenlenebilir)
# ---------------------------------------------------------------------------
class AppSetting(TimeStampedModel):
    """Arayüzden düzenlenebilen uygulama ayarı.

    ``is_secret`` işaretli ayarların değeri şifreli saklanır ve arayüzde
    yalnızca kısaltılmış biçimde (``sk-a…9f2c``) gösterilir.
    """

    class Category(models.TextChoices):
        GENERAL = "general", _("Genel")
        AI = "ai", _("Yapay zekâ")
        PAYMENT = "payment", _("Ödeme")
        BACKUP = "backup", _("Yedekleme")
        PRIVACY = "privacy", _("Gizlilik")
        PRINTING = "printing", _("Yazdırma")
        DEVSTUDIO = "devstudio", _("Geliştirici stüdyosu")

    key = models.CharField(_("Anahtar"), max_length=120, unique=True, db_index=True)
    category = models.CharField(
        _("Kategori"), max_length=20, choices=Category.choices, default=Category.GENERAL
    )
    label = models.CharField(_("Etiket"), max_length=200, blank=True)
    help_text = models.TextField(_("Açıklama"), blank=True)
    value = models.JSONField(_("Değer"), default=dict, blank=True)
    secret_value = EncryptedTextField(_("Gizli değer"), blank=True, default="")
    is_secret = models.BooleanField(_("Gizli"), default=False)
    is_experimental = models.BooleanField(
        _("Deneysel"),
        default=False,
        help_text=_("Arayüzde 'Deneysel' rozetiyle gösterilir."),
    )

    class Meta:
        verbose_name = _("Uygulama ayarı")
        verbose_name_plural = _("Uygulama ayarları")
        ordering = ["category", "key"]

    def __str__(self) -> str:
        return f"{self.get_category_display()} · {self.key}"

    @property
    def display_value(self) -> str:
        """Arayüzde güvenle gösterilebilecek değer."""
        if self.is_secret:
            from apps.core.security import redact_key

            return redact_key(self.secret_value)
        return str(self.value)


class FeatureFlag(TimeStampedModel):
    """Özellik bayrağı: tamamlanmamış özellikler açıkça işaretlenir.

    Arayüz, ``status`` alanına göre "Deneysel" veya "Planlandı" rozeti
    gösterir; böylece çalışmayan bir özellik tamamlanmış gibi sunulmaz.
    """

    class Status(models.TextChoices):
        READY = "ready", _("Hazır")
        EXPERIMENTAL = "experimental", _("Deneysel")
        PLANNED = "planned", _("Planlandı")
        DISABLED = "disabled", _("Devre dışı")

    code = models.SlugField(_("Kod"), max_length=100, unique=True)
    name = models.CharField(_("Ad"), max_length=200)
    description = models.TextField(_("Açıklama"), blank=True)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.PLANNED
    )
    module = models.CharField(_("Modül"), max_length=80, blank=True)

    class Meta:
        verbose_name = _("Özellik bayrağı")
        verbose_name_plural = _("Özellik bayrakları")
        ordering = ["module", "code"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"

    @property
    def is_enabled(self) -> bool:
        return self.status in {self.Status.READY, self.Status.EXPERIMENTAL}

    @property
    def badge_class(self) -> str:
        """Bootstrap rozet sınıfı."""
        return {
            self.Status.READY: "bg-success",
            self.Status.EXPERIMENTAL: "bg-warning text-dark",
            self.Status.PLANNED: "bg-secondary",
            self.Status.DISABLED: "bg-dark",
        }.get(self.Status(self.status), "bg-secondary")
