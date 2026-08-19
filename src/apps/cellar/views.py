"""Şarap kavı görünümleri."""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.generic import DetailView, ListView, TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.cellar import services
from apps.cellar.models import (
    BottleOpening,
    StorageReading,
    Wine,
    WineDuplicateAlert,
    WineStorageLocation,
)


class WineListView(AuditedPermissionMixin, ListView):
    """Kavdaki şaraplar."""

    template_name = "cellar/wine_list.html"
    context_object_name = "wines"
    paginate_by = 50
    required_permissions = ["cellar.view_wine"]

    def get_queryset(self) -> QuerySet[Wine]:
        queryset = (
            Wine.objects.filter(is_deleted=False)
            .select_related("producer", "region")
            .prefetch_related("grape_compositions__grape", "lots")
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(sku__icontains=query)
                | Q(producer__name__icontains=query)
                | Q(barcode=query)
            )
        wine_type = self.request.GET.get("type", "").strip()
        if wine_type:
            queryset = queryset.filter(wine_type=wine_type)
        if self.request.GET.get("by_glass") == "1":
            queryset = queryset.filter(sold_by_glass=True)
        if self.request.GET.get("low_stock") == "1":
            queryset = [wine for wine in queryset if wine.is_below_minimum]  # type: ignore[assignment]
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["wine_types"] = Wine.WineType.choices
        context["filters"] = {
            "q": self.request.GET.get("q", ""),
            "type": self.request.GET.get("type", ""),
            "by_glass": self.request.GET.get("by_glass", ""),
            "low_stock": self.request.GET.get("low_stock", ""),
        }
        from apps.cellar.models import RESPONSIBLE_CONSUMPTION_NOTICE_TR

        context["responsible_notice"] = RESPONSIBLE_CONSUMPTION_NOTICE_TR
        return context


class WineDetailView(AuditedPermissionMixin, DetailView):
    """Şarap kartı: bileşim, stok, tadım notları, eşleştirmeler."""

    template_name = "cellar/wine_detail.html"
    context_object_name = "wine"
    required_permissions = ["cellar.view_wine"]

    def get_queryset(self) -> QuerySet[Wine]:
        return Wine.objects.filter(is_deleted=False).select_related("producer", "region")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        wine: Wine = self.object
        context["compositions"] = wine.grape_compositions.select_related("grape").all()
        context["lots"] = wine.lots.filter(is_deleted=False).select_related("location", "supplier")
        context["openings"] = wine.bottle_openings.order_by("-opened_at")[:10]
        context["tasting_notes"] = wine.tasting_notes.order_by("-tasted_on")[:10]
        context["ratings"] = wine.ratings.order_by("-rated_on")[:10]
        context["pairings"] = wine.pairings.select_related("menu_item").order_by("-strength")
        context["faults"] = wine.faults.order_by("-detected_at")[:10]
        context["duplicate_alerts"] = wine.duplicate_alerts.filter(
            status=WineDuplicateAlert.Status.OPEN
        )
        context["can_view_cost"] = (
            self.request.user.has_perm("cellar.can_view_cellar_valuation")
            or self.request.user.is_superuser
        )
        from apps.cellar.models import RESPONSIBLE_CONSUMPTION_NOTICE_TR

        context["responsible_notice"] = RESPONSIBLE_CONSUMPTION_NOTICE_TR
        return context


class OpenBottleListView(AuditedPermissionMixin, ListView):
    """Açık şişeler ve kadeh verimi."""

    template_name = "cellar/open_bottles.html"
    context_object_name = "openings"
    required_permissions = ["cellar.view_bottleopening"]

    def get_queryset(self) -> QuerySet[BottleOpening]:
        return (
            BottleOpening.objects.filter(status=BottleOpening.Status.OPEN)
            .select_related("wine", "wine__producer", "lot", "opened_by")
            .order_by("opened_at")
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        openings = list(context["openings"])
        context["stale_count"] = sum(1 for opening in openings if opening.is_past_freshness)
        context["total_glasses"] = sum(opening.glasses_remaining for opening in openings)
        return context


class StorageListView(AuditedPermissionMixin, ListView):
    """Kav konumları ve son sıcaklık/nem ölçümleri."""

    template_name = "cellar/storage_list.html"
    context_object_name = "locations"
    required_permissions = ["cellar.view_winestoragelocation"]

    def get_queryset(self) -> QuerySet[WineStorageLocation]:
        return WineStorageLocation.objects.filter(is_active=True).select_related("parent")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        rows = []
        for location in context["locations"]:
            reading = location.latest_reading()
            rows.append(
                {
                    "location": location,
                    "reading": reading,
                    "has_alert": reading.has_alert if reading else False,
                }
            )
        context["rows"] = rows
        context["recent_readings"] = StorageReading.objects.select_related("location").order_by(
            "-recorded_at"
        )[:20]
        return context


class CellarValuationView(AuditedPermissionMixin, TemplateView):
    """Kav değerlemesi ve içim aralığı uyarıları."""

    template_name = "cellar/valuation.html"
    required_permissions = ["cellar.can_view_cellar_valuation"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["valuation"] = services.cellar_valuation()
        context["drink_alerts"] = services.drink_window_alerts()
        return context


class DuplicateAlertListView(AuditedPermissionMixin, ListView):
    """Mükerrer / şüpheli kayıt uyarıları."""

    template_name = "cellar/duplicate_alerts.html"
    context_object_name = "alerts"
    required_permissions = ["cellar.view_wineduplicatealert"]

    def get_queryset(self) -> QuerySet[WineDuplicateAlert]:
        return WineDuplicateAlert.objects.filter(
            status=WineDuplicateAlert.Status.OPEN
        ).select_related("wine", "other_wine")


def run_duplicate_scan(request: Any) -> Any:
    """Mükerrer kayıt taramasını başlatır. Hiçbir kayıt silinmez."""
    if request.method != "POST":
        return redirect("cellar:duplicate-alerts")
    if not request.user.has_perm("cellar.view_wineduplicatealert"):
        messages.error(request, _("Bu işlem için yetkiniz yok."))
        return redirect("cellar:wine-list")

    alerts = services.detect_duplicates()
    messages.info(
        request,
        _("Tarama tamamlandı: %(count)s uyarı. Hiçbir kayıt silinmedi; inceleme sizde.")
        % {"count": len(alerts)},
    )
    return redirect("cellar:duplicate-alerts")


def open_bottle_action(request: Any, pk: int) -> Any:
    """Arayüzden şişe açma."""
    if request.method != "POST":
        return redirect("cellar:wine-detail", pk=pk)
    if not request.user.has_perm("cellar.can_open_bottle"):
        messages.error(request, _("Şişe açma yetkiniz yok."))
        return redirect("cellar:wine-detail", pk=pk)

    wine = get_object_or_404(Wine, pk=pk, is_deleted=False)
    try:
        opening = services.open_bottle(
            wine=wine,
            user=request.user,
            service_method=request.POST.get("service_method", BottleOpening.ServiceMethod.STANDARD),
            note=request.POST.get("note", ""),
        )
    except services.CellarError as exc:
        messages.error(request, str(exc))
        return redirect("cellar:wine-detail", pk=pk)

    messages.success(
        request,
        _("Şişe açıldı. Servis edilebilir kadeh: %(count)s") % {"count": opening.glasses_remaining},
    )
    return redirect("cellar:wine-detail", pk=pk)


def pour_glass_action(request: Any, pk: int) -> Any:
    """Arayüzden kadeh servisi."""
    if request.method != "POST":
        return redirect("cellar:wine-detail", pk=pk)
    if not request.user.has_perm("cellar.can_pour_glass"):
        messages.error(request, _("Kadeh servis yetkiniz yok."))
        return redirect("cellar:wine-detail", pk=pk)

    wine = get_object_or_404(Wine, pk=pk, is_deleted=False)
    raw_volume = request.POST.get("volume_ml", "").strip()
    try:
        result = services.pour_glass(
            wine=wine,
            user=request.user,
            volume_ml=int(raw_volume) if raw_volume else None,
            pour_type=request.POST.get("pour_type", "glass_sale"),
            note=request.POST.get("note", ""),
        )
    except (services.CellarError, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect("cellar:wine-detail", pk=pk)

    if result.opened_new_bottle:
        messages.info(request, _("Yeni şişe açıldı ve stoktan düşüldü."))
    messages.success(
        request,
        _("Servis kaydedildi. Şişede kalan kadeh: %(count)s") % {"count": result.remaining_glasses},
    )
    return redirect("cellar:wine-detail", pk=pk)
