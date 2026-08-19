"""Salon operasyonu görünümleri."""

from __future__ import annotations

from typing import Any

from django.db.models import Prefetch, Q, QuerySet
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.operations.models import (
    BusinessDay,
    DiningTable,
    FloorSection,
    Order,
    PrepTicket,
    Reservation,
    WaitlistEntry,
)


class TableMapView(AuditedPermissionMixin, TemplateView):
    """Salon planı ve masa durumları."""

    template_name = "operations/table_map.html"
    required_permissions = ["operations.view_diningtable"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        sections = FloorSection.objects.filter(is_active=True).prefetch_related(
            Prefetch(
                "tables",
                queryset=DiningTable.objects.filter(is_active=True).order_by("number"),
            )
        )
        layout = []
        for section in sections:
            tables = list(section.tables.all())
            layout.append(
                {
                    "section": section,
                    "tables": [{"table": table, "order": table.active_order} for table in tables],
                    "free": sum(1 for table in tables if table.status == DiningTable.Status.FREE),
                    "total": len(tables),
                }
            )
        context["layout"] = layout
        context["status_choices"] = DiningTable.Status.choices
        return context


class OrderListView(AuditedPermissionMixin, ListView):
    """Adisyon listesi."""

    template_name = "operations/order_list.html"
    context_object_name = "orders"
    paginate_by = 50
    required_permissions = ["operations.view_order"]

    def get_queryset(self) -> QuerySet[Order]:
        queryset = (
            Order.objects.filter(is_deleted=False)
            .select_related("table", "table__section", "server", "customer")
            .order_by("-opened_at")
        )
        status_filter = self.request.GET.get("status", "open")
        if status_filter == "open":
            queryset = queryset.filter(status__in=Order.OPEN_STATUSES)
        elif status_filter and status_filter != "all":
            queryset = queryset.filter(status=status_filter)
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(number__icontains=query) | Q(table__number__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["status_choices"] = Order.Status.choices
        context["selected_status"] = self.request.GET.get("status", "open")
        context["query"] = self.request.GET.get("q", "")
        return context


class OrderDetailView(AuditedPermissionMixin, DetailView):
    """Adisyon ayrıntısı: satırlar, fişler, ödemeler."""

    template_name = "operations/order_detail.html"
    context_object_name = "order"
    required_permissions = ["operations.view_order"]

    def get_queryset(self) -> QuerySet[Order]:
        return Order.objects.filter(is_deleted=False).select_related(
            "table", "server", "customer", "reservation"
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        order: Order = self.object
        context["lines"] = order.lines.select_related("menu_item", "wine").order_by("course", "id")
        context["tickets"] = order.tickets.prefetch_related("lines").order_by("sent_at")
        context["payments"] = order.payments.select_related("method").order_by("received_at")
        context["can_pay"] = self.request.user.has_perm("operations.can_take_payment")
        context["can_void"] = self.request.user.has_perm("operations.can_void_order")
        context["can_discount"] = self.request.user.has_perm("operations.can_apply_discount")
        return context


class ReservationListView(AuditedPermissionMixin, ListView):
    """Rezervasyon listesi."""

    template_name = "operations/reservation_list.html"
    context_object_name = "reservations"
    paginate_by = 50
    required_permissions = ["operations.view_reservation"]

    def get_queryset(self) -> QuerySet[Reservation]:
        queryset = (
            Reservation.objects.filter(is_deleted=False)
            .select_related("customer", "section_preference")
            .prefetch_related("tables")
            .order_by("reserved_for")
        )
        scope = self.request.GET.get("scope", "today")
        today = timezone.localdate()
        if scope == "today":
            queryset = queryset.filter(reserved_for__date=today)
        elif scope == "upcoming":
            queryset = queryset.filter(reserved_for__gte=timezone.now())
        status_filter = self.request.GET.get("status", "").strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["status_choices"] = Reservation.Status.choices
        context["scope"] = self.request.GET.get("scope", "today")
        context["selected_status"] = self.request.GET.get("status", "")
        return context


class WaitlistView(AuditedPermissionMixin, ListView):
    """Bekleme listesi."""

    template_name = "operations/waitlist.html"
    context_object_name = "entries"
    required_permissions = ["operations.view_waitlistentry"]

    def get_queryset(self) -> QuerySet[WaitlistEntry]:
        return WaitlistEntry.objects.filter(
            status__in=[WaitlistEntry.Status.WAITING, WaitlistEntry.Status.NOTIFIED]
        ).select_related("customer")


class _StationDisplayView(AuditedPermissionMixin, TemplateView):
    """İstasyon ekranları için ortak taban (KDS)."""

    template_name = "operations/kds.html"
    station: str = PrepTicket.Station.KITCHEN
    station_title: str = "Mutfak"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        tickets = (
            PrepTicket.objects.filter(
                station=self.station,
                status__in=[
                    PrepTicket.Status.QUEUED,
                    PrepTicket.Status.PREPARING,
                    PrepTicket.Status.READY,
                ],
            )
            .select_related("order", "order__table")
            .prefetch_related("lines")
            .order_by("-priority", "sent_at")
        )
        context["tickets"] = tickets
        context["station"] = self.station
        context["station_title"] = self.station_title
        context["overdue_count"] = sum(1 for ticket in tickets if ticket.is_overdue)
        context["can_bump"] = self.request.user.has_perm("operations.can_bump_ticket")
        return context


class KitchenDisplayView(_StationDisplayView):
    """Mutfak ekranı (KDS)."""

    station = PrepTicket.Station.KITCHEN
    station_title = "Mutfak Ekranı"
    required_permissions = ["operations.can_view_kitchen_display"]


class BarDisplayView(_StationDisplayView):
    """Bar ekranı."""

    station = PrepTicket.Station.BAR
    station_title = "Bar Ekranı"
    required_permissions = ["operations.can_view_bar_display"]


class WineDisplayView(_StationDisplayView):
    """Sommelier / şarap servis ekranı."""

    station = PrepTicket.Station.WINE
    station_title = "Şarap Servis Ekranı"
    required_permissions = ["operations.can_view_wine_display"]


class BusinessDayView(AuditedPermissionMixin, ListView):
    """Gün sonu kayıtları."""

    template_name = "operations/business_day.html"
    context_object_name = "days"
    paginate_by = 30
    required_permissions = ["operations.view_businessday"]

    def get_queryset(self) -> QuerySet[BusinessDay]:
        return BusinessDay.objects.select_related("opened_by", "closed_by")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        context["today_record"] = BusinessDay.objects.filter(business_date=today).first()
        context["open_order_count"] = Order.objects.filter(
            status__in=Order.OPEN_STATUSES, opened_at__date=today, is_deleted=False
        ).count()
        context["can_close"] = self.request.user.has_perm("operations.can_close_day")
        return context
