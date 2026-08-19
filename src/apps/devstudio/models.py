"""AI Development Studio veri modelleri.

Her geliştirme oturumu ve önerilen her eylem izlenebilir biçimde kaydedilir.
Hiçbir eylem denetim kaydı olmadan uygulanmaz.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class DevSession(TimeStampedModel):
    """Bir geliştirme oturumu (tek bir görev/istek)."""

    class Status(models.TextChoices):
        PLANNING = "planning", _("Plan hazırlanıyor")
        PROPOSED = "proposed", _("Öneri hazır")
        APPROVED = "approved", _("Onaylandı")
        APPLIED = "applied", _("Uygulandı")
        TESTING = "testing", _("Test ediliyor")
        TESTS_PASSED = "tests_passed", _("Testler geçti")
        TESTS_FAILED = "tests_failed", _("Testler başarısız")
        MERGED = "merged", _("Ana dala birleştirildi")
        REVERTED = "reverted", _("Geri alındı")
        REJECTED = "rejected", _("Reddedildi")
        FAILED = "failed", _("Başarısız")

    title = models.CharField(_("Başlık"), max_length=250)
    request_text = models.TextField(_("İstek"), help_text=_("Kullanıcının doğal dilde tarifi."))
    plan_text = models.TextField(_("Plan"), blank=True)
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.PLANNING, db_index=True
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Talep eden"),
        on_delete=models.PROTECT,
        related_name="dev_sessions",
    )
    provider = models.CharField(_("Sağlayıcı"), max_length=30, blank=True)
    model = models.CharField(_("Model"), max_length=120, blank=True)

    # --- Git ---
    base_branch = models.CharField(_("Kaynak dal"), max_length=120, blank=True)
    work_branch = models.CharField(_("Çalışma dalı"), max_length=120, blank=True)
    commit_sha = models.CharField(_("Commit"), max_length=40, blank=True)
    #: Geri alma noktası — uygulamadan önceki commit
    rollback_sha = models.CharField(_("Geri alma noktası"), max_length=40, blank=True)

    # --- Test ---
    tests_run = models.BooleanField(_("Test çalıştırıldı"), default=False)
    tests_passed = models.BooleanField(_("Testler geçti"), default=False)
    test_output = models.TextField(_("Test çıktısı"), blank=True)
    lint_passed = models.BooleanField(_("Kod kalitesi geçti"), default=False)
    lint_output = models.TextField(_("Kalite çıktısı"), blank=True)

    # --- Maliyet ---
    total_prompt_tokens = models.PositiveIntegerField(_("İstem belirteci"), default=0)
    total_completion_tokens = models.PositiveIntegerField(_("Yanıt belirteci"), default=0)
    estimated_cost_usd = models.DecimalField(
        _("Tahmini maliyet (USD)"), max_digits=12, decimal_places=6, default=0
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Onaylayan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dev_sessions_approved",
    )
    approved_at = models.DateTimeField(_("Onay zamanı"), null=True, blank=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Geliştirme oturumu")
        verbose_name_plural = _("Geliştirme oturumları")
        ordering = ["-created_at"]
        permissions = [
            ("can_open_devstudio", _("AI Development Studio açabilir")),
            ("can_apply_dev_change", _("Kod değişikliği uygulayabilir")),
            ("can_merge_dev_branch", _("Çalışma dalını birleştirebilir")),
            ("can_run_dev_commands", _("Denetlenmiş komut çalıştırabilir")),
        ]

    def __str__(self) -> str:
        return f"{self.title} · {self.get_status_display()}"

    @property
    def can_merge(self) -> bool:
        """Birleştirme koşulları: onaylı **ve** testler geçmiş olmalı."""
        return (
            self.status in {self.Status.APPLIED, self.Status.TESTS_PASSED}
            and self.tests_run
            and self.tests_passed
            and self.approved_by_id is not None
        )

    @property
    def merge_blockers(self) -> list[str]:
        """Birleştirmeyi engelleyen nedenler (arayüzde gösterilir)."""
        blockers: list[str] = []
        if self.approved_by_id is None:
            blockers.append("Kullanıcı onayı yok.")
        if not self.tests_run:
            blockers.append("Testler henüz çalıştırılmadı.")
        elif not self.tests_passed:
            blockers.append("Testler başarısız.")
        if not self.work_branch:
            blockers.append("Çalışma dalı oluşturulmadı.")
        return blockers


class DevAction(TimeStampedModel):
    """Oturum içinde önerilen tek bir eylem.

    Eylemler yapay zekâ tarafından *yapılandırılmış* olarak üretilir
    (serbest metin komut değil) ve politika motorundan geçirilir.
    """

    class ActionType(models.TextChoices):
        FILE_CREATE = "file_create", _("Dosya oluştur")
        FILE_EDIT = "file_edit", _("Dosya düzenle")
        FILE_DELETE = "file_delete", _("Dosya sil")
        RUN_COMMAND = "run_command", _("Komut çalıştır")
        RUN_TESTS = "run_tests", _("Test çalıştır")
        RUN_LINT = "run_lint", _("Kod kalitesi denetimi")
        GIT_BRANCH = "git_branch", _("Dal oluştur")
        GIT_COMMIT = "git_commit", _("Commit oluştur")
        GIT_REVERT = "git_revert", _("Değişikliği geri al")

    class Status(models.TextChoices):
        PROPOSED = "proposed", _("Önerildi")
        BLOCKED = "blocked", _("Politika engelledi")
        AWAITING = "awaiting", _("Onay bekliyor")
        APPROVED = "approved", _("Onaylandı")
        EXECUTED = "executed", _("Uygulandı")
        REJECTED = "rejected", _("Reddedildi")
        FAILED = "failed", _("Başarısız")
        REVERTED = "reverted", _("Geri alındı")

    session = models.ForeignKey(
        DevSession, verbose_name=_("Oturum"), on_delete=models.CASCADE, related_name="actions"
    )
    sequence = models.PositiveSmallIntegerField(_("Sıra"), default=1)
    action_type = models.CharField(_("Eylem türü"), max_length=20, choices=ActionType.choices)
    description = models.CharField(_("Açıklama"), max_length=300, blank=True)

    target_path = models.CharField(_("Hedef dosya"), max_length=500, blank=True)
    command = models.TextField(_("Komut"), blank=True)
    #: Önerilen yeni içerik (dosya eylemlerinde)
    proposed_content = models.TextField(_("Önerilen içerik"), blank=True)
    #: Uygulamadan önceki içerik (geri alma için)
    previous_content = models.TextField(_("Önceki içerik"), blank=True)
    diff_text = models.TextField(_("Fark (diff)"), blank=True)

    # --- Politika ---
    policy_decision = models.CharField(_("Politika kararı"), max_length=20, blank=True)
    policy_reason = models.TextField(_("Politika gerekçesi"), blank=True)
    policy_rule = models.CharField(_("Eşleşen kural"), max_length=60, blank=True)

    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.PROPOSED, db_index=True
    )
    executed_at = models.DateTimeField(_("Uygulama zamanı"), null=True, blank=True)
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Uygulayan"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dev_actions_executed",
    )
    exit_code = models.IntegerField(_("Çıkış kodu"), null=True, blank=True)
    output = models.TextField(_("Çıktı"), blank=True)
    error_output = models.TextField(_("Hata çıktısı"), blank=True)

    class Meta:
        verbose_name = _("Geliştirme eylemi")
        verbose_name_plural = _("Geliştirme eylemleri")
        ordering = ["session", "sequence"]

    def __str__(self) -> str:
        return f"{self.get_action_type_display()} · {self.target_path or self.command[:40]}"

    @property
    def is_blocked(self) -> bool:
        return self.status == self.Status.BLOCKED

    def masked_output(self) -> str:
        """Çıktıyı gizli değerler maskelenmiş olarak döndürür.

        Terminal çıktısı arayüzde **yalnızca** bu yöntemle gösterilir.
        """
        from apps.core.security import mask_secrets

        return mask_secrets(self.output)

    def masked_error_output(self) -> str:
        from apps.core.security import mask_secrets

        return mask_secrets(self.error_output)


class DevAuditEntry(models.Model):
    """AI Development Studio'ya özel, değiştirilemez denetim kaydı.

    Genel ``core.AuditLog``'a ek olarak tutulur; güvenlik incelemesinde
    stüdyo etkinliğinin tek bir yerden okunabilmesini sağlar.
    """

    session = models.ForeignKey(
        DevSession,
        verbose_name=_("Oturum"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    action = models.ForeignKey(
        DevAction,
        verbose_name=_("Eylem"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    timestamp = models.DateTimeField(_("Zaman"), default=timezone.now, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Kullanıcı"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="devstudio_audit",
    )
    event = models.CharField(_("Olay"), max_length=80, db_index=True)
    detail = models.TextField(_("Ayrıntı"), blank=True)
    is_security_relevant = models.BooleanField(_("Güvenlikle ilgili"), default=False)

    class Meta:
        verbose_name = _("Stüdyo denetim kaydı")
        verbose_name_plural = _("Stüdyo denetim kayıtları")
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.event}"

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk is not None:
            raise ValueError("Stüdyo denetim kayıtları değiştirilemez.")
        from apps.core.security import mask_secrets

        self.detail = mask_secrets(self.detail)
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValueError("Stüdyo denetim kayıtları silinemez.")
