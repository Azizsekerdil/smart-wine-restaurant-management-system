"""Stok ve satın alma görünümleri."""

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet
from django.views.generic import DetailView, ListView, TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.inventory import services
from apps.inventory.models import (
    PurchaseOrder,
    StockItem,
    StockItemCategory,
    StockLot,
    Supplier,
    WastageEntry,
)


class StockItemListView(AuditedPermissionMixin, ListView):
    """Stok kalemleri."""

    template_name = "inventory/stock_list.html"
    context_object_name = "items"
    paginate_by = 50
    required_permissions = ["inventory.view_stockitem"]

    def get_queryset(self) -> QuerySet[StockItem]:
        queryset = (
            StockItem.objects.filter(is_deleted=False)
            .select_related("category", "unit", "default_supplier")
            .prefetch_related("lots")
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(code__icontains=query) | Q(barcode=query)
            )
        category = self.request.GET.get("category", "").strip()
        if category:
            queryset = queryset.filter(category__code=category)
        if self.request.GET.get("low_stock") == "1":
            ids = [item.pk for item in queryset if item.is_below_minimum]
            queryset = queryset.filter(pk__in=ids)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["categories"] = StockItemCategory.objects.all()
        context["filters"] = {
            "q": self.request.GET.get("q", ""),
            "category": self.request.GET.get("category", ""),
            "low_stock": self.request.GET.get("low_stock", ""),
        }
        context["can_view_valuation"] = self.request.user.has_perm("inventory.view_stock_valuation")
        return context


class StockItemDetailView(AuditedPermissionMixin, DetailView):
    """Stok kalemi ayrıntısı ve hareketleri."""

    template_name = "inventory/stock_detail.html"
    context_object_name = "item"
    required_permissions = ["inventory.view_stockitem"]

    def get_queryset(self) -> QuerySet[StockItem]:
        return StockItem.objects.filter(is_deleted=False).select_related("category", "unit")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        item: StockItem = self.object
        context["lots"] = item.lots.filter(is_deleted=False).select_related("warehouse")
        context["movements"] = item.movements.select_related("warehouse", "lot")[:50]
        context["wastages"] = item.wastages.select_related("warehouse")[:20]
        context["recipe_usage"] = item.recipe_lines.select_related("recipe__menu_item")[:20]
        return context


class LotListView(AuditedPermissionMixin, ListView):
    """Partiler ve son kullanma uyarıları (FEFO)."""

    template_name = "inventory/lot_list.html"
    context_object_name = "lots"
    paginate_by = 100
    required_permissions = ["inventory.view_stocklot"]

    def get_queryset(self) -> QuerySet[StockLot]:
        queryset = (
            StockLot.objects.filter(is_deleted=False, quantity_remaining__gt=0)
            .select_related("stock_item", "warehouse", "supplier")
            .order_by("expires_on", "received_on")
        )
        if self.request.GET.get("expiring") == "1":
            ids = [lot.pk for lot in services.expiring_lots(days=14, limit=500)]
            queryset = queryset.filter(pk__in=ids)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["expiring_only"] = self.request.GET.get("expiring") == "1"
        return context


class WastageListView(AuditedPermissionMixin, ListView):
    """Fire kayıtları."""

    template_name = "inventory/wastage_list.html"
    context_object_name = "entries"
    paginate_by = 50
    required_permissions = ["inventory.view_wastageentry"]

    def get_queryset(self) -> QuerySet[WastageEntry]:
        queryset = WastageEntry.objects.select_related("stock_item", "warehouse", "recorded_by")
        reason = self.request.GET.get("reason", "").strip()
        if reason:
            queryset = queryset.filter(reason=reason)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        from decimal import Decimal

        context = super().get_context_data(**kwargs)
        entries = WastageEntry.objects.all()
        context["reason_choices"] = WastageEntry.Reason.choices
        context["selected_reason"] = self.request.GET.get("reason", "")
        context["total_cost"] = sum((entry.estimated_cost for entry in entries), Decimal("0.00"))
        return context


class SupplierListView(AuditedPermissionMixin, ListView):
    """Tedarikçiler."""

    template_name = "inventory/supplier_list.html"
    context_object_name = "suppliers"
    paginate_by = 50
    required_permissions = ["inventory.view_supplier"]

    def get_queryset(self) -> QuerySet[Supplier]:
        queryset = Supplier.objects.filter(is_deleted=False)
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(code__icontains=query))
        return queryset


class PurchaseOrderListView(AuditedPermissionMixin, ListView):
    """Satın alma siparişleri."""

    template_name = "inventory/purchaseorder_list.html"
    context_object_name = "orders"
    paginate_by = 50
    required_permissions = ["inventory.view_purchaseorder"]

    def get_queryset(self) -> QuerySet[PurchaseOrder]:
        return (
            PurchaseOrder.objects.filter(is_deleted=False)
            .select_related("supplier", "warehouse")
            .prefetch_related("lines")
        )


class ReorderSuggestionView(AuditedPermissionMixin, TemplateView):
    """Otomatik sipariş önerileri (yalnızca öneri; sipariş oluşturmaz)."""

    template_name = "inventory/reorder_suggestions.html"
    required_permissions = ["inventory.view_stockitem"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["suggestions"] = services.build_reorder_suggestions()
        context["expiring"] = services.expiring_lots(days=14)
        return context


class StockValuationView(AuditedPermissionMixin, TemplateView):
    """Stok değerlemesi."""

    template_name = "inventory/valuation.html"
    required_permissions = ["inventory.view_stock_valuation"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["valuation"] = services.stock_valuation()
        return context
