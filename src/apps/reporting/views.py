"""Raporlama görünümleri ve dışa aktarım."""

from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.core.audit import record
from apps.core.models import AuditAction
from apps.reporting import reports
from apps.reporting.exporters import ExportError, export, safe_filename
from apps.reporting.models import ReportRun


def _parse_period(request: Any) -> tuple[date, date]:
    """İstek parametrelerinden dönem çıkarır (varsayılan: son 30 gün)."""
    today = timezone.localdate()
    default_start = today - timedelta(days=29)

    def _parse(name: str, fallback: date) -> date:
        raw = request.GET.get(name, "").strip()
        if not raw:
            return fallback
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return fallback

    start = _parse("start", default_start)
    end = _parse("end", today)
    if start > end:
        start, end = end, start
    return start, end


class ReportListView(AuditedPermissionMixin, TemplateView):
    """Kullanılabilir raporların listesi."""

    template_name = "reporting/report_list.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        specs = reports.available_reports(self.request.user)
        grouped: dict[str, list[Any]] = {}
        for spec in specs:
            grouped.setdefault(spec.category, []).append(spec)
        context["grouped_reports"] = grouped
        context["category_labels"] = {
            "sales": _("Satış"),
            "product": _("Ürün"),
            "wine": _("Şarap"),
            "inventory": _("Stok"),
            "purchasing": _("Satın alma"),
            "staff": _("Personel"),
            "customer": _("Müşteri"),
            "operations": _("Operasyon"),
            "ai": _("Yapay zekâ"),
            "finance": _("Mali"),
        }
        start, end = _parse_period(self.request)
        context["start"] = start
        context["end"] = end
        return context


class ReportDetailView(AuditedPermissionMixin, TemplateView):
    """Tek bir raporun ekran çıktısı."""

    template_name = "reporting/report_detail.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        code = self.kwargs["code"]

        try:
            spec = reports.get_report(code)
        except KeyError as exc:
            raise PermissionDenied(str(exc)) from exc

        if spec.permission and not (
            self.request.user.has_perm(spec.permission) or self.request.user.is_superuser
        ):
            record(
                action=AuditAction.PERMISSION_DENIED,
                message=f"Rapor erişimi reddedildi: {code}",
                success=False,
                request=self.request,
            )
            raise PermissionDenied(_("Bu raporu görüntüleme yetkiniz yok."))

        start, end = _parse_period(self.request)
        params = reports.ReportParams(
            start_date=start, end_date=end, language=get_language() or "tr"
        )

        started = time.monotonic()
        table = spec.generator(params)
        duration_ms = int((time.monotonic() - started) * 1000)

        ReportRun.objects.create(
            definition=self._ensure_definition(spec),
            run_by=self.request.user,
            parameters={"start": str(start), "end": str(end)},
            output_format=ReportRun.Format.HTML,
            status=ReportRun.Status.SUCCESS,
            row_count=len(table.rows),
            duration_ms=duration_ms,
        )

        context["spec"] = spec
        context["table"] = table
        context["start"] = start
        context["end"] = end
        context["duration_ms"] = duration_ms
        return context

    @staticmethod
    def _ensure_definition(spec: Any) -> Any:
        """Rapor tanımını veritabanında oluşturur/günceller."""
        from apps.reporting.models import ReportDefinition

        definition, _created = ReportDefinition.objects.get_or_create(
            code=spec.code,
            defaults={
                "name_tr": spec.name_tr,
                "name_en": spec.name_en,
                "category": spec.category,
                "description": spec.description,
                "is_experimental": spec.is_experimental,
            },
        )
        return definition


def export_report(request: Any, code: str, output_format: str) -> HttpResponse:
    """Raporu PDF / Excel / CSV olarak indirir."""
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    try:
        spec = reports.get_report(code)
    except KeyError as exc:
        messages.error(request, str(exc))
        return redirect("reporting:report-list")

    if spec.permission and not (
        request.user.has_perm(spec.permission) or request.user.is_superuser
    ):
        record(
            action=AuditAction.PERMISSION_DENIED,
            message=f"Rapor dışa aktarımı reddedildi: {code}.{output_format}",
            success=False,
            request=request,
        )
        raise PermissionDenied(_("Bu raporu dışa aktarma yetkiniz yok."))

    if not (request.user.has_perm("reporting.can_export_report") or request.user.is_superuser):
        raise PermissionDenied(_("Rapor dışa aktarma yetkiniz yok."))

    start, end = _parse_period(request)
    language = get_language() or "tr"
    params = reports.ReportParams(start_date=start, end_date=end, language=language)

    started = time.monotonic()
    table = spec.generator(params)
    table.metadata = {
        "Oluşturan": request.user.label,
        "Dönem": params.period_label,
    }

    try:
        content, content_type = export(table, output_format, language=language)
    except ExportError as exc:
        messages.error(request, str(exc))
        record(
            action=AuditAction.EXPORT,
            message=f"Rapor dışa aktarımı başarısız: {code}.{output_format} — {exc}",
            success=False,
            request=request,
        )
        return redirect("reporting:report-detail", code=code)

    duration_ms = int((time.monotonic() - started) * 1000)
    filename = safe_filename(spec.name_tr, output_format)

    ReportRun.objects.create(
        definition=ReportDetailView._ensure_definition(spec),
        run_by=request.user,
        parameters={"start": str(start), "end": str(end)},
        output_format=output_format if output_format in {"pdf", "csv"} else "xlsx",
        status=ReportRun.Status.SUCCESS,
        row_count=len(table.rows),
        duration_ms=duration_ms,
        file_path=filename,
    )

    record(
        action=AuditAction.EXPORT,
        message=(
            f"Rapor dışa aktarıldı: {spec.name_tr} ({output_format.upper()}) · "
            f"{len(table.rows)} satır · dönem {params.period_label}"
        ),
        request=request,
    )

    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = str(len(content))
    return response


class ForecastView(AuditedPermissionMixin, TemplateView):
    """Satış tahmini ekranı (Deneysel)."""

    template_name = "reporting/forecast.html"
    required_permissions = ["reporting.view_salesforecast"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        params = reports.ReportParams(
            start_date=today, end_date=today + timedelta(days=13), language=get_language() or "tr"
        )
        context["table"] = reports.sales_forecast_report(params)
        context["is_experimental"] = True
        context["method_note"] = (
            "Tahmin, son 8 haftanın aynı gün ortalamasına dayanır. Yapay zekâ "
            "yalnızca yorum ekler; sayısal tahmini değiştirmez."
        )
        return context
