"""Stok URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.inventory import views

app_name = "inventory"

urlpatterns = [
    path("", views.StockItemListView.as_view(), name="stock-list"),
    path("<int:pk>/", views.StockItemDetailView.as_view(), name="stock-detail"),
    path("partiler/", views.LotListView.as_view(), name="lot-list"),
    path("fire/", views.WastageListView.as_view(), name="wastage-list"),
    path("tedarikciler/", views.SupplierListView.as_view(), name="supplier-list"),
    path("siparisler/", views.PurchaseOrderListView.as_view(), name="purchaseorder-list"),
    path("oneriler/", views.ReorderSuggestionView.as_view(), name="reorder-suggestions"),
    path("degerleme/", views.StockValuationView.as_view(), name="valuation"),
]
