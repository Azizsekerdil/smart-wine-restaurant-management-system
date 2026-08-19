"""Eğitim merkezi görünümleri."""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.generic import DetailView, TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.training.models import LessonProgress, TrainingLesson, TrainingModule


class TrainingHomeView(AuditedPermissionMixin, TemplateView):
    """Kullanıcının rolüne göre eğitim modülleri."""

    template_name = "training/home.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        language = get_language() or "tr"

        modules = [
            module
            for module in TrainingModule.objects.filter(is_published=True).prefetch_related(
                "lessons"
            )
            if module.is_visible_to(user)
        ]

        completed_ids = set(
            LessonProgress.objects.filter(user=user, is_completed=True).values_list(
                "lesson_id", flat=True
            )
        )

        rows = []
        for module in modules:
            lessons = list(module.lessons.all())
            done = sum(1 for lesson in lessons if lesson.pk in completed_ids)
            rows.append(
                {
                    "module": module,
                    "title": module.title_for(language),
                    "summary": module.summary_for(language),
                    "lesson_count": len(lessons),
                    "completed": done,
                    "percent": int(done / len(lessons) * 100) if lessons else 0,
                }
            )

        context["modules"] = rows
        context["language"] = language
        context["role_label"] = getattr(user, "role_label", "")
        context["mandatory_pending"] = [
            row for row in rows if row["module"].is_mandatory and row["percent"] < 100
        ]
        return context


class ModuleDetailView(AuditedPermissionMixin, DetailView):
    """Modül içindeki dersler."""

    template_name = "training/module_detail.html"
    context_object_name = "module"
    slug_field = "code"
    slug_url_kwarg = "code"

    def get_queryset(self) -> Any:
        return TrainingModule.objects.filter(is_published=True).prefetch_related("lessons")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        module: TrainingModule = self.object
        language = get_language() or "tr"

        if not module.is_visible_to(self.request.user):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied(_("Bu eğitim modülü rolünüze açık değil."))

        completed_ids = set(
            LessonProgress.objects.filter(user=self.request.user, is_completed=True).values_list(
                "lesson_id", flat=True
            )
        )

        context["title"] = module.title_for(language)
        context["summary"] = module.summary_for(language)
        context["lessons"] = [
            {
                "lesson": lesson,
                "title": lesson.title_for(language),
                "is_completed": lesson.pk in completed_ids,
            }
            for lesson in module.lessons.all()
        ]
        context["language"] = language
        return context


class LessonDetailView(AuditedPermissionMixin, DetailView):
    """Ders içeriği (Markdown)."""

    template_name = "training/lesson_detail.html"
    context_object_name = "lesson"

    def get_queryset(self) -> Any:
        return TrainingLesson.objects.select_related("module")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        lesson: TrainingLesson = self.object
        language = get_language() or "tr"

        if not lesson.module.is_visible_to(self.request.user):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied(_("Bu ders rolünüze açık değil."))

        context["title"] = lesson.title_for(language)
        context["content"] = lesson.content_for(language)
        context["language"] = language
        context["progress"] = LessonProgress.objects.filter(
            user=self.request.user, lesson=lesson
        ).first()

        siblings = list(lesson.module.lessons.order_by("sort_order", "id"))
        index = next(
            (position for position, item in enumerate(siblings) if item.pk == lesson.pk), 0
        )
        context["previous_lesson"] = siblings[index - 1] if index > 0 else None
        context["next_lesson"] = siblings[index + 1] if index + 1 < len(siblings) else None
        return context


def complete_lesson(request: Any, pk: int) -> Any:
    """Dersi tamamlandı olarak işaretler."""
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.method != "POST":
        return redirect("training:lesson-detail", pk=pk)

    lesson = get_object_or_404(TrainingLesson, pk=pk)
    progress, _created = LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)
    progress.is_completed = True
    progress.completed_at = timezone.now()
    progress.save(update_fields=["is_completed", "completed_at", "updated_at"])

    messages.success(request, _("Ders tamamlandı olarak işaretlendi."))

    siblings = list(lesson.module.lessons.order_by("sort_order", "id"))
    index = next((position for position, item in enumerate(siblings) if item.pk == lesson.pk), 0)
    if index + 1 < len(siblings):
        return redirect("training:lesson-detail", pk=siblings[index + 1].pk)
    return redirect("training:module-detail", code=lesson.module.code)
