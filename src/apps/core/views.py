"""Çekirdek görünümler: ana panel, ayarlar, özellik durumu."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import redirect, render, resolve_url
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.core.models import AppSetting, FeatureFlag


class DashboardView(AuditedPermissionMixin, TemplateView):
    """Role göre uyarlanan ana panel."""

    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()

        context["today"] = today
        context["role_label"] = getattr(user, "role_label", "")
        context["cards"] = self._build_cards(user, today)
        context["alerts"] = self._build_alerts(user)
        context["experimental_features"] = FeatureFlag.objects.filter(
            status__in=[FeatureFlag.Status.EXPERIMENTAL, FeatureFlag.Status.PLANNED]
        ).order_by("module", "name")[:12]
        return context

    def _build_cards(self, user: Any, today: Any) -> list[dict[str, Any]]:
        """Kullanıcının yetkisine göre gösterilecek özet kartları."""
        cards: list[dict[str, Any]] = []

        if user.has_perm("operations.view_diningtable"):
            from apps.operations.models import DiningTable, Order

            free = DiningTable.objects.filter(
                is_active=True, status=DiningTable.Status.FREE
            ).count()
            total = DiningTable.objects.filter(is_active=True).count()
            open_orders = Order.objects.filter(status__in=Order.OPEN_STATUSES).count()
            cards.append(
                {
                    "title": _("Masa durumu"),
                    "value": f"{total - free}/{total}",
                    "subtitle": _("dolu masa"),
                    "icon": "🍽️",
                    "url": "operations:table-map",
                }
            )
            cards.append(
                {
                    "title": _("Açık adisyon"),
                    "value": open_orders,
                    "subtitle": _("servis devam ediyor"),
                    "icon": "🧾",
                    "url": "operations:order-list",
                }
            )

        if user.has_perm("operations.view_reservation"):
            from apps.operations.models import Reservation

            todays = Reservation.objects.filter(
                reserved_for__date=today,
                status__in=[Reservation.Status.CONFIRMED, Reservation.Status.PENDING],
            ).count()
            cards.append(
                {
                    "title": _("Bugünkü rezervasyon"),
                    "value": todays,
                    "subtitle": _("onaylı"),
                    "icon": "📅",
                    "url": "operations:reservation-list",
                }
            )

        if user.has_perm("cellar.view_wine"):
            from apps.cellar.models import BottleLot, BottleOpening

            bottles = (
                BottleLot.objects.filter(is_deleted=False).aggregate(
                    total=Sum("bottles_remaining")
                )["total"]
                or 0
            )
            open_bottles = BottleOpening.objects.filter(status=BottleOpening.Status.OPEN).count()
            cards.append(
                {
                    "title": _("Kavdaki şişe"),
                    "value": bottles,
                    "subtitle": _("kapalı şişe"),
                    "icon": "🍷",
                    "url": "cellar:wine-list",
                }
            )
            cards.append(
                {
                    "title": _("Açık şişe"),
                    "value": open_bottles,
                    "subtitle": _("kadeh servisinde"),
                    "icon": "🥂",
                    "url": "cellar:open-bottles",
                }
            )

        if user.has_perm("reporting.view_dailysalessnapshot"):
            from apps.reporting.models import DailySalesSnapshot

            snapshot = DailySalesSnapshot.objects.filter(
                business_date__gte=today - timedelta(days=7)
            ).aggregate(total=Sum("net_sales"))["total"] or Decimal("0.00")
            cards.append(
                {
                    "title": _("Son 7 gün net satış"),
                    "value": f"{snapshot:,.2f}",
                    "subtitle": _("₺"),
                    "icon": "📈",
                    "url": "reporting:report-list",
                }
            )

        return cards

    def _build_alerts(self, user: Any) -> list[dict[str, str]]:
        """Dikkat gerektiren durumlar."""
        alerts: list[dict[str, str]] = []

        if user.has_perm("cellar.view_wine"):
            from apps.cellar.models import BottleOpening, StorageReading

            stale = [
                opening
                for opening in BottleOpening.objects.filter(
                    status=BottleOpening.Status.OPEN
                ).select_related("wine")[:50]
                if opening.is_past_freshness
            ]
            if stale:
                alerts.append(
                    {
                        "level": "warning",
                        "message": _("%(count)s açık şişe tazelik süresini aştı; kontrol edilmeli.")
                        % {"count": len(stale)},
                        "url": "cellar:open-bottles",
                    }
                )

            recent_readings = StorageReading.objects.select_related("location").order_by(
                "-recorded_at"
            )[:20]
            out_of_range = [reading for reading in recent_readings if reading.has_alert]
            if out_of_range:
                alerts.append(
                    {
                        "level": "danger",
                        "message": _("%(count)s kav ölçümü hedef aralığın dışında.")
                        % {"count": len(out_of_range)},
                        "url": "cellar:storage-list",
                    }
                )

        if user.has_perm("inventory.view_stockitem"):
            from apps.inventory.models import StockItem

            low = [
                item
                for item in StockItem.objects.filter(is_active=True, is_deleted=False)[:200]
                if item.is_below_minimum
            ]
            if low:
                alerts.append(
                    {
                        "level": "warning",
                        "message": _("%(count)s stok kalemi minimum seviyenin altında.")
                        % {"count": len(low)},
                        "url": "inventory:stock-list",
                    }
                )

        from apps.accounts.models import ApprovalRequest

        pending = ApprovalRequest.objects.filter(status=ApprovalRequest.Status.PENDING).count()
        if pending and getattr(user, "can_approve", lambda _a: False)("void_order"):
            alerts.append(
                {
                    "level": "info",
                    "message": _("%(count)s işlem ikinci onay bekliyor.") % {"count": pending},
                    "url": "accounts:approval-queue",
                }
            )

        return alerts


class SettingsView(AuditedPermissionMixin, TemplateView):
    """Uygulama ayarları özeti."""

    template_name = "core/settings.html"
    required_permissions = ["core.view_appsetting"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        grouped: dict[str, list[AppSetting]] = {}
        for setting in AppSetting.objects.all():
            grouped.setdefault(setting.get_category_display(), []).append(setting)
        context["grouped_settings"] = grouped
        context["feature_flags"] = FeatureFlag.objects.all()
        return context


class FeatureStatusView(AuditedPermissionMixin, TemplateView):
    """Özellik durum tablosu.

    Hangi modülün hazır, hangisinin deneysel, hangisinin planlandığı
    açıkça listelenir. Amaç: tamamlanmamış bir özelliğin tamamlanmış gibi
    görünmesini önlemek.
    """

    template_name = "core/feature_status.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        flags = FeatureFlag.objects.all().order_by("module", "name")
        grouped: dict[str, list[FeatureFlag]] = {}
        for flag in flags:
            grouped.setdefault(flag.module or _("Genel"), []).append(flag)
        context["grouped_flags"] = grouped
        context["summary"] = flags.values("status").annotate(count=Count("id"))
        return context


def _safe_back_url(request: Any) -> str:
    """``Referer`` başlığını yalnızca aynı siteye işaret ediyorsa kullanır.

    ``Referer`` istemci tarafından belirlenir; doğrulanmadan yönlendirme
    hedefi yapılırsa kullanıcı dış bir siteye taşınabilir (açık yönlendirme).
    Güvenli değilse ana panele dönülür.
    """
    referer = request.META.get("HTTP_REFERER", "")
    if referer and url_has_allowed_host_and_scheme(
        url=referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return referer
    return resolve_url("core:dashboard")


def set_language_preference(request: Any) -> Any:
    """Kullanıcının dil tercihini kalıcı olarak kaydeder.

    Django'nun ``set_language`` görünümü yalnızca oturum/çerez günceller;
    bu görünüm ek olarak kullanıcı kaydına yazar.

    Yönlendirme hedefi her zaman aynı site içinde doğrulanır.
    """
    if request.method != "POST":
        return redirect("core:dashboard")

    back = _safe_back_url(request)

    language = request.POST.get("language", "").strip()
    if language not in {"tr", "en"}:
        messages.error(request, _("Desteklenmeyen dil."))
        return redirect(back)

    request.session["django_language"] = language
    if request.user.is_authenticated:
        request.user.preferred_language = language
        request.user.save(update_fields=["preferred_language"])

    from django.utils import translation

    translation.activate(language)
    return redirect(back)


def handler403(request: Any, exception: Any = None) -> Any:
    """Yetkisiz erişim sayfası."""
    return render(request, "errors/403.html", {"detail": str(exception or "")}, status=403)


def handler404(request: Any, exception: Any = None) -> Any:
    return render(request, "errors/404.html", status=404)


def handler500(request: Any) -> Any:
    return render(request, "errors/500.html", status=500)
