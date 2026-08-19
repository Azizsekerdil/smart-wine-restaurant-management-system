"""Menü görünümleri."""

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet
from django.shortcuts import render
from django.utils.translation import get_language
from django.views.generic import DetailView, ListView, TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.catalog.models import MenuCategory, MenuItem
from apps.operations.models import DiningTable


class MenuItemListView(AuditedPermissionMixin, ListView):
    """Menü ürünleri listesi."""

    template_name = "catalog/menuitem_list.html"
    context_object_name = "items"
    paginate_by = 50
    required_permissions = ["catalog.view_menuitem"]

    def get_queryset(self) -> QuerySet[MenuItem]:
        queryset = (
            MenuItem.objects.filter(is_deleted=False)
            .select_related("category", "wine")
            .prefetch_related("allergens", "dietary_tags")
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name_tr__icontains=query) | Q(name_en__icontains=query) | Q(code__icontains=query)
            )
        category = self.request.GET.get("category", "").strip()
        if category:
            queryset = queryset.filter(category__code=category)
        item_type = self.request.GET.get("type", "").strip()
        if item_type:
            queryset = queryset.filter(item_type=item_type)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["categories"] = MenuCategory.objects.filter(is_active=True)
        context["item_types"] = MenuItem.ItemType.choices
        context["filters"] = {
            "q": self.request.GET.get("q", ""),
            "category": self.request.GET.get("category", ""),
            "type": self.request.GET.get("type", ""),
        }
        return context


class MenuItemDetailView(AuditedPermissionMixin, DetailView):
    """Menü ürünü ayrıntısı, reçete ve maliyet dökümü."""

    template_name = "catalog/menuitem_detail.html"
    context_object_name = "item"
    required_permissions = ["catalog.view_menuitem"]

    def get_queryset(self) -> QuerySet[MenuItem]:
        return MenuItem.objects.filter(is_deleted=False).select_related("category", "wine")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        item: MenuItem = self.object
        recipe = getattr(item, "recipe", None)
        context["recipe"] = recipe
        context["recipe_lines"] = (
            recipe.lines.select_related("stock_item", "stock_item__unit").all() if recipe else []
        )
        context["can_view_cost"] = (
            self.request.user.has_perm("catalog.view_menu_engineering")
            or self.request.user.is_superuser
        )
        context["pairings"] = item.wine_pairings.select_related("wine").filter(is_approved=True)
        return context


class MenuEngineeringView(AuditedPermissionMixin, TemplateView):
    """Menü mühendisliği kadran analizi."""

    template_name = "catalog/menu_engineering.html"
    required_permissions = ["catalog.view_menu_engineering"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        from apps.catalog.models import MenuEngineeringSnapshot

        context = super().get_context_data(**kwargs)
        snapshots = MenuEngineeringSnapshot.objects.select_related("menu_item").order_by(
            "-period_end", "-contribution_margin"
        )[:200]
        quadrants: dict[str, list[Any]] = {
            value: [] for value, _label in MenuEngineeringSnapshot.Quadrant.choices
        }
        for snapshot in snapshots:
            quadrants.setdefault(snapshot.quadrant, []).append(snapshot)
        context["quadrants"] = quadrants
        context["quadrant_labels"] = dict(MenuEngineeringSnapshot.Quadrant.choices)
        context["has_data"] = bool(snapshots)
        return context


def qr_menu(request: Any, token: str = "") -> Any:
    """Misafire açık QR menü.

    Kimlik doğrulama gerektirmez; yalnızca ``show_on_qr_menu`` işaretli
    ürünler gösterilir. Hiçbir maliyet, stok veya kişisel veri sızdırmaz.
    """
    language = get_language() or "tr"
    table = None
    if token:
        table = DiningTable.objects.filter(qr_token=token, is_active=True).first()

    categories = (
        MenuCategory.objects.filter(is_active=True, show_on_qr_menu=True, parent__isnull=True)
        .prefetch_related("children")
        .order_by("sort_order")
    )

    menu: list[dict[str, Any]] = []
    for category in categories:
        category_ids = [category.pk] + list(
            category.children.filter(is_active=True, show_on_qr_menu=True).values_list(
                "pk", flat=True
            )
        )
        items = (
            MenuItem.objects.filter(
                is_deleted=False,
                is_active=True,
                is_available=True,
                show_on_qr_menu=True,
                category_id__in=category_ids,
            )
            .select_related("wine", "wine__producer")
            .prefetch_related("allergens", "dietary_tags")
            .order_by("sort_order", "name_tr")
        )
        if items:
            menu.append({"category": category, "items": items})

    from apps.cellar.models import (
        RESPONSIBLE_CONSUMPTION_NOTICE_EN,
        RESPONSIBLE_CONSUMPTION_NOTICE_TR,
    )

    return render(
        request,
        "catalog/qr_menu.html",
        {
            "menu": menu,
            "table": table,
            "language": language,
            "responsible_notice": (
                RESPONSIBLE_CONSUMPTION_NOTICE_TR
                if language == "tr"
                else RESPONSIBLE_CONSUMPTION_NOTICE_EN
            ),
        },
    )
