"""CAIO ajanı görünümleri."""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.db.models import Count, QuerySet
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views.generic import ListView, TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.caio import services
from apps.caio.models import Finding, ImprovementTask, ObservationRun


class CaioDashboardView(AuditedPermissionMixin, TemplateView):
    """CAIO panosu: son koşum, açık bulgular, sınırlar."""

    template_name = "caio/dashboard.html"
    required_permissions = ["caio.view_observationrun"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["latest_run"] = ObservationRun.objects.order_by("-created_at").first()
        context["runs"] = ObservationRun.objects.order_by("-created_at")[:10]
        context["open_findings"] = Finding.objects.filter(status=Finding.Status.OPEN).order_by(
            "-severity", "-last_seen_at"
        )[:20]
        context["severity_counts"] = (
            Finding.objects.filter(status=Finding.Status.OPEN)
            .values("severity")
            .annotate(count=Count("id"))
        )
        context["open_tasks"] = ImprovementTask.objects.filter(
            status__in=[ImprovementTask.Status.BACKLOG, ImprovementTask.Status.IN_PROGRESS]
        ).order_by("-priority")[:20]
        context["can_run"] = self.request.user.has_perm("caio.can_run_caio")
        context["boundaries"] = [
            _("CAIO üretim kodunu kendiliğinden değiştiremez."),
            _("Dal birleştiremez ve sürüm yayınlayamaz."),
            _("Kullanıcı verisini buluta gönderemez."),
            _("Her çıktısı insan onayı bekleyen bir öneridir."),
        ]
        return context


class FindingListView(AuditedPermissionMixin, ListView):
    """Bulgu listesi."""

    template_name = "caio/findings.html"
    context_object_name = "findings"
    paginate_by = 50
    required_permissions = ["caio.view_finding"]

    def get_queryset(self) -> QuerySet[Finding]:
        queryset = Finding.objects.select_related("run", "reviewed_by")
        status_filter = self.request.GET.get("status", Finding.Status.OPEN)
        if status_filter != "all":
            queryset = queryset.filter(status=status_filter)
        category = self.request.GET.get("category", "").strip()
        if category:
            queryset = queryset.filter(category=category)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["status_choices"] = Finding.Status.choices
        context["category_choices"] = Finding.Category.choices
        context["selected_status"] = self.request.GET.get("status", Finding.Status.OPEN)
        context["selected_category"] = self.request.GET.get("category", "")
        return context


class ImprovementTaskListView(AuditedPermissionMixin, ListView):
    """Geliştirme görevleri."""

    template_name = "caio/tasks.html"
    context_object_name = "tasks"
    paginate_by = 50
    required_permissions = ["caio.view_improvementtask"]

    def get_queryset(self) -> QuerySet[ImprovementTask]:
        return ImprovementTask.objects.prefetch_related("findings").order_by(
            "-priority", "-created_at"
        )


def run_observation(request: Any) -> Any:
    """CAIO gözlem koşumunu başlatır."""
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.method != "POST":
        return redirect("caio:dashboard")
    if not (request.user.has_perm("caio.can_run_caio") or request.user.is_superuser):
        messages.error(request, _("CAIO gözlemi başlatma yetkiniz yok."))
        return redirect("caio:dashboard")

    try:
        days = int(request.POST.get("days", 7))
    except ValueError:
        days = 7

    run = services.run_observation(user=request.user, days=max(1, min(90, days)))
    tasks = services.generate_improvement_tasks(run=run, user=request.user)

    messages.success(
        request,
        _("Gözlem tamamlandı: %(findings)s bulgu, %(tasks)s yeni görev taslağı.")
        % {"findings": run.findings_count, "tasks": len(tasks)},
    )
    return redirect("caio:dashboard")
