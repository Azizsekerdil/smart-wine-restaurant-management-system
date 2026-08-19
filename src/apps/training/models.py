"""Eğitim merkezi modelleri.

Eğitim içerikleri role göre filtrelenir; her personel yalnızca kendi
görevine ait dersleri görür. İçerikler Markdown olarak saklanır ve
uygulama içinde gösterilir (internet bağlantısı gerektirmez).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class TrainingModule(TimeStampedModel):
    """Rol bazlı eğitim modülü."""

    class Level(models.TextChoices):
        BASIC = "basic", _("Temel")
        INTERMEDIATE = "intermediate", _("Orta")
        ADVANCED = "advanced", _("İleri")

    code = models.SlugField(_("Kod"), max_length=60, unique=True)
    title_tr = models.CharField(_("Başlık (TR)"), max_length=200)
    title_en = models.CharField(_("Başlık (EN)"), max_length=200, blank=True)
    summary_tr = models.TextField(_("Özet (TR)"), blank=True)
    summary_en = models.TextField(_("Özet (EN)"), blank=True)
    #: Bu modülü görebilecek rol kodları. Boş liste = herkes görebilir.
    target_roles = models.JSONField(_("Hedef roller"), default=list, blank=True)
    level = models.CharField(_("Seviye"), max_length=20, choices=Level.choices, default=Level.BASIC)
    estimated_minutes = models.PositiveSmallIntegerField(_("Tahmini süre (dk)"), default=15)
    sort_order = models.PositiveSmallIntegerField(_("Sıra"), default=100)
    is_mandatory = models.BooleanField(_("Zorunlu"), default=False)
    is_published = models.BooleanField(_("Yayında"), default=True)
    icon = models.CharField(_("Simge"), max_length=40, blank=True, default="📘")

    class Meta:
        verbose_name = _("Eğitim modülü")
        verbose_name_plural = _("Eğitim modülleri")
        ordering = ["sort_order", "title_tr"]

    def __str__(self) -> str:
        return self.title_tr

    def title_for(self, language: str) -> str:
        return self.title_en if language == "en" and self.title_en else self.title_tr

    def summary_for(self, language: str) -> str:
        if language == "en" and self.summary_en:
            return self.summary_en
        return self.summary_tr

    def is_visible_to(self, user) -> bool:
        """Kullanıcının bu modülü görüp göremeyeceğini bildirir."""
        if not self.is_published:
            return False
        if not self.target_roles:
            return True
        if getattr(user, "is_superuser", False):
            return True
        return bool(set(self.target_roles) & getattr(user, "role_codes", set()))


class TrainingLesson(TimeStampedModel):
    """Eğitim modülü içindeki tek bir ders."""

    module = models.ForeignKey(
        TrainingModule, verbose_name=_("Modül"), on_delete=models.CASCADE, related_name="lessons"
    )
    code = models.SlugField(_("Kod"), max_length=60)
    title_tr = models.CharField(_("Başlık (TR)"), max_length=200)
    title_en = models.CharField(_("Başlık (EN)"), max_length=200, blank=True)
    #: Markdown biçiminde ders içeriği
    content_tr = models.TextField(_("İçerik (TR)"))
    content_en = models.TextField(_("İçerik (EN)"), blank=True)
    sort_order = models.PositiveSmallIntegerField(_("Sıra"), default=100)
    #: Uygulama içi ilgili ekrana bağlantı (ör. "operations:table-map")
    related_url_name = models.CharField(_("İlgili ekran"), max_length=100, blank=True)

    class Meta:
        verbose_name = _("Eğitim dersi")
        verbose_name_plural = _("Eğitim dersleri")
        ordering = ["module__sort_order", "sort_order"]
        constraints = [
            models.UniqueConstraint(fields=["module", "code"], name="uniq_module_lesson_code")
        ]

    def __str__(self) -> str:
        return f"{self.module.title_tr} › {self.title_tr}"

    def title_for(self, language: str) -> str:
        return self.title_en if language == "en" and self.title_en else self.title_tr

    def content_for(self, language: str) -> str:
        if language == "en" and self.content_en:
            return self.content_en
        return self.content_tr


class LessonProgress(TimeStampedModel):
    """Kullanıcının ders ilerlemesi."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Kullanıcı"),
        on_delete=models.CASCADE,
        related_name="lesson_progress",
    )
    lesson = models.ForeignKey(
        TrainingLesson, verbose_name=_("Ders"), on_delete=models.CASCADE, related_name="progress"
    )
    is_completed = models.BooleanField(_("Tamamlandı"), default=False)
    completed_at = models.DateTimeField(_("Tamamlanma"), null=True, blank=True)

    class Meta:
        verbose_name = _("Ders ilerlemesi")
        verbose_name_plural = _("Ders ilerlemeleri")
        constraints = [
            models.UniqueConstraint(fields=["user", "lesson"], name="uniq_user_lesson_progress")
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.lesson.title_tr}"
