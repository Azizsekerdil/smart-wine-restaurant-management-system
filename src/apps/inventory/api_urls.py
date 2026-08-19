"""Stok API yönlendirmeleri."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.inventory import api

router = DefaultRouter()
router.register("items", api.StockItemViewSet, basename="api-stockitem")
router.register("lots", api.StockLotViewSet, basename="api-stocklot")
router.register("movements", api.StockMovementViewSet, basename="api-stockmovement")
router.register("wastage", api.WastageEntryViewSet, basename="api-wastage")
router.register("suppliers", api.SupplierViewSet, basename="api-supplier")
router.register("warehouses", api.WarehouseViewSet, basename="api-warehouse")
router.register("units", api.UnitOfMeasureViewSet, basename="api-unit")
router.register("requests", api.PurchaseRequestViewSet, basename="api-purchaserequest")
router.register("orders", api.PurchaseOrderViewSet, basename="api-purchaseorder")
router.register("receipts", api.GoodsReceiptViewSet, basename="api-goodsreceipt")
router.register("counts", api.StockCountViewSet, basename="api-stockcount")

urlpatterns = router.urls
