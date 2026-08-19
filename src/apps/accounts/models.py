"""Kullanıcı, rol ve onay modelleri."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.roles import CRITICAL_ACTIONS, ROLES_BY_CODE, role_choices
from apps.core.fields import EncryptedCharField
from apps.core.models import TimeStampedModel


class User(AbstractUser):
    """Wine House kullanıcısı.

    Django'nun standart kullanıcı modelini restoran ortamına uyarlar:
      * **PIN girişi** — POS terminalinde hızlı kullanıcı değişimi için
      * **Birincil rol** — arayüz ve raporlarda gösterilen ana görev
      * **Hesap kilitleme** — art arda başarısız girişte geçici kilit
      * **Dil tercihi** — kullanıcı bazında TR/EN
    """

    class Language(models.TextChoices):
        TR = "tr", _("Türkçe")
        EN = "en", _("English")

    display_name = models.CharField(
        _("Görünen ad"),
        max_length=150,
        blank=True,
        help_text=_("Fişlerde ve ekranlarda gösterilecek ad."),
    )
    primary_role = models.CharField(
        _("Birincil rol"),
        max_length=40,
        choices=role_choices(),
        blank=True,
        db_index=True,
    )
    phone = EncryptedCharField(_("Telefon"), blank=True, default="")
    preferred_language = models.CharField(
        _("Tercih edilen dil"),
        max_length=5,
        choices=Language.choices,
        default=Language.TR,
    )

    # --- POS hızlı giriş ---
    pin_hash = models.CharField(_("PIN özeti"), max_length=255, blank=True, default="")
    pin_enabled = models.BooleanField(_("PIN girişi açık"), default=False)

    # --- Güvenlik ---
    must_change_password = models.BooleanField(_("Parola değiştirmeli"), default=False)
    password_changed_at = models.DateTimeField(_("Parola değişim zamanı"), null=True, blank=True)
    failed_login_count = models.PositiveSmallIntegerField(_("Başarısız giriş"), default=0)
    locked_until = models.DateTimeField(_("Kilit bitişi"), null=True, blank=True)

    # --- Yetki sınırları ---
    discount_limit_percent = models.DecimalField(
        _("İndirim yetkisi (%)"),
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text=_("Bu oranın üzerindeki indirimler ikinci onay gerektirir."),
    )

    employee_code = models.CharField(_("Personel kodu"), max_length=20, blank=True, db_index=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta(AbstractUser.Meta):
        verbose_name = _("Kullanıcı")
        verbose_name_plural = _("Kullanıcılar")
        permissions = [
            ("can_manage_roles", _("Rol ve yetki yönetebilir")),
            ("can_view_audit_log", _("Denetim kaydını görüntüleyebilir")),
            ("can_use_devstudio", _("AI Development Studio kullanabilir")),
            ("can_approve_critical", _("Kritik işlemleri onaylayabilir")),
        ]

    def __str__(self) -> str:
        return self.display_name or self.get_full_name() or self.username

    # -- Görüntüleme yardımcıları ------------------------------------------
    @property
    def label(self) -> str:
        return self.display_name or self.get_full_name() or self.username

    @property
    def role_label(self) -> str:
        spec = ROLES_BY_CODE.get(self.primary_role)
        return spec.name_tr if spec else _("Rol atanmamış")

    @property
    def role_codes(self) -> set[str]:
        """Kullanıcının sahip olduğu tüm rol kodları (grup adları)."""
        codes = {group.name for group in self.groups.all()}
        if self.primary_role:
            codes.add(self.primary_role)
        return codes

    @property
    def is_read_only(self) -> bool:
        """Salt okunur denetçi rolü."""
        from apps.accounts.roles import READ_ONLY_ROLES

        return bool(self.role_codes & READ_ONLY_ROLES) and not self.is_superuser

    @property
    def can_use_devstudio(self) -> bool:
        """AI Development Studio erişimi."""
        from apps.accounts.roles import DEVSTUDIO_ROLES

        return self.is_superuser or bool(self.role_codes & DEVSTUDIO_ROLES)

    # -- PIN yönetimi -------------------------------------------------------
    def set_pin(self, raw_pin: str) -> None:
        """POS hızlı giriş PIN'ini karma (hash) olarak saklar.

        PIN asla düz metin tutulmaz. En az 4, en çok 8 rakam olmalıdır.
        """
        cleaned = (raw_pin or "").strip()
        if not cleaned.isdigit() or not (4 <= len(cleaned) <= 8):
            raise ValueError("PIN 4-8 rakamdan oluşmalıdır.")
        self.pin_hash = make_password(cleaned)
        self.pin_enabled = True

    def check_pin(self, raw_pin: str) -> bool:
        """Verilen PIN'i doğrular."""
        if not self.pin_enabled or not self.pin_hash:
            return False
        return check_password((raw_pin or "").strip(), self.pin_hash)

    def clear_pin(self) -> None:
        self.pin_hash = ""
        self.pin_enabled = False

    # -- Hesap kilidi -------------------------------------------------------
    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    def register_failed_login(self, *, max_attempts: int = 5, lock_minutes: int = 15) -> None:
        """Başarısız giriş sayacını artırır; sınır aşılırsa hesabı kilitler."""
        self.failed_login_count += 1
        if self.failed_login_count >= max_attempts:
            self.locked_until = timezone.now() + timezone.timedelta(minutes=lock_minutes)
        self.save(update_fields=["failed_login_count", "locked_until"])

    def register_successful_login(self) -> None:
        """Başarılı girişte sayaçları sıfırlar."""
        self.failed_login_count = 0
        self.locked_until = None
        self.save(update_fields=["failed_login_count", "locked_until"])

    # -- Onay yetkisi -------------------------------------------------------
    def can_approve(self, action: str) -> bool:
        """Kullanıcının belirtilen kritik işlemi onaylayıp onaylayamayacağı."""
        from apps.accounts.roles import can_role_approve

        if self.is_superuser:
            return True
        return any(can_role_approve(code, action) for code in self.role_codes)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.display_name:
            self.display_name = self.get_full_name() or self.username
        super().save(*args, **kwargs)


class RoleProfile(TimeStampedModel):
    """Bir Django grubuna (role) ait ek üstveri.

    Grup adı rol koduyla aynıdır; bu model rolün Türkçe/İngilizce adını,
    açıklamasını ve kademesini taşır.
    """

    group = models.OneToOneField(
        Group,
        verbose_name=_("Grup"),
        on_delete=models.CASCADE,
        related_name="profile",
    )
    code = models.CharField(_("Rol kodu"), max_length=40, unique=True, db_index=True)
    name_tr = models.CharField(_("Ad (TR)"), max_length=100)
    name_en = models.CharField(_("Ad (EN)"), max_length=100)
    description = models.TextField(_("Açıklama"), blank=True)
    level = models.PositiveSmallIntegerField(_("Kademe"), default=5)
    is_system = models.BooleanField(
        _("Sistem rolü"),
        default=True,
        help_text=_("Sistem rolleri arayüzden silinemez."),
    )

    class Meta:
        verbose_name = _("Rol profili")
        verbose_name_plural = _("Rol profilleri")
        ordering = ["level", "code"]

    def __str__(self) -> str:
        return f"{self.name_tr} ({self.code})"


class ApprovalRequest(TimeStampedModel):
    """Kritik işlemler için ikinci onay talebi.

    İş akışı:
      1. Yetkili olmayan (veya limiti aşan) kullanıcı işlemi başlatır.
      2. ``ApprovalRequest`` ``PENDING`` durumda oluşturulur; işlem uygulanmaz.
      3. Onay yetkisi olan başka bir kullanıcı onaylar veya reddeder.
      4. Onaylandığında çağıran servis işlemi uygular ve denetime yazar.

    Kendi talebini onaylama engellenir (görevler ayrılığı).
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Onay bekliyor")
        APPROVED = "approved", _("Onaylandı")
        REJECTED = "rejected", _("Reddedildi")
        EXPIRED = "expired", _("Süresi doldu")
        APPLIED = "applied", _("Uygulandı")

    action = models.CharField(
        _("İşlem"),
        max_length=50,
        choices=[(key, value) for key, value in CRITICAL_ACTIONS.items()],
        db_index=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Talep eden"),
        on_delete=models.PROTECT,
        related_name="approval_requests",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Onaylayan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approvals_given",
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reason = models.TextField(_("Gerekçe"), blank=True)
    review_note = models.TextField(_("Onay notu"), blank=True)
    payload = models.JSONField(_("İşlem verisi"), default=dict, blank=True)
    object_type = models.CharField(_("Nesne türü"), max_length=100, blank=True)
    object_id = models.CharField(_("Nesne kimliği"), max_length=64, blank=True)
    reviewed_at = models.DateTimeField(_("Onay zamanı"), null=True, blank=True)
    expires_at = models.DateTimeField(_("Geçerlilik bitişi"), null=True, blank=True)

    class Meta:
        verbose_name = _("Onay talebi")
        verbose_name_plural = _("Onay talepleri")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="approval_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()} · {self.get_status_display()}"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at < timezone.now())

    def approve(self, reviewer: User, note: str = "") -> None:
        """Talebi onaylar.

        Raises:
            PermissionError: Onaylayan kendisi talep sahibiyse veya yetkisi yoksa.
            ValueError: Talep beklemede değilse veya süresi dolmuşsa.
        """
        self._guard_review(reviewer)
        self.status = self.Status.APPROVED
        self.reviewed_by = reviewer
        self.review_note = note
        self.reviewed_at = timezone.now()
        self.save(
            update_fields=["status", "reviewed_by", "review_note", "reviewed_at", "updated_at"]
        )

    def reject(self, reviewer: User, note: str = "") -> None:
        """Talebi reddeder."""
        self._guard_review(reviewer)
        self.status = self.Status.REJECTED
        self.reviewed_by = reviewer
        self.review_note = note
        self.reviewed_at = timezone.now()
        self.save(
            update_fields=["status", "reviewed_by", "review_note", "reviewed_at", "updated_at"]
        )

    def mark_applied(self) -> None:
        """Onaylanmış talebin uygulandığını işaretler (tekrar kullanımı önler)."""
        if self.status != self.Status.APPROVED:
            raise ValueError("Yalnızca onaylanmış talep uygulanmış olarak işaretlenebilir.")
        self.status = self.Status.APPLIED
        self.save(update_fields=["status", "updated_at"])

    def _guard_review(self, reviewer: User) -> None:
        if self.status != self.Status.PENDING:
            raise ValueError(f"Talep beklemede değil (durum: {self.get_status_display()}).")
        if self.is_expired:
            self.status = self.Status.EXPIRED
            self.save(update_fields=["status", "updated_at"])
            raise ValueError("Onay talebinin süresi doldu.")
        if reviewer.pk == self.requested_by_id:
            raise PermissionError("Görevler ayrılığı: kullanıcı kendi talebini onaylayamaz.")
        if not reviewer.can_approve(self.action):
            raise PermissionError(
                f"'{reviewer.label}' kullanıcısının '{self.get_action_display()}' "
                "işlemini onaylama yetkisi yok."
            )


class LoginAttempt(models.Model):
    """Giriş denemesi kaydı (kaba kuvvet saldırısı tespiti için)."""

    username = models.CharField(_("Kullanıcı adı"), max_length=150, db_index=True)
    successful = models.BooleanField(_("Başarılı"), default=False)
    ip_address = models.GenericIPAddressField(_("IP adresi"), null=True, blank=True)
    user_agent = models.CharField(_("İstemci"), max_length=255, blank=True)
    method = models.CharField(
        _("Yöntem"),
        max_length=20,
        default="password",
        choices=[("password", _("Parola")), ("pin", _("PIN"))],
    )
    timestamp = models.DateTimeField(_("Zaman"), default=timezone.now, db_index=True)

    class Meta:
        verbose_name = _("Giriş denemesi")
        verbose_name_plural = _("Giriş denemeleri")
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        state = "başarılı" if self.successful else "başarısız"
        return f"{self.username} · {state} · {self.timestamp:%Y-%m-%d %H:%M}"
