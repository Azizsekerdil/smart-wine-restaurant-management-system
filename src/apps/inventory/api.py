"""Stok ve satın alma REST API'si."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.inventory import services
from apps.inventory.models import (
    GoodsReceipt,
    PurchaseOrder,
    PurchaseRequest,
    StockCount,
    StockItem,
    StockLot,
    StockMovement,
    Supplier,
    UnitOfMeasure,
    Warehouse,
    WastageEntry,
)


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = ["id", "code", "name", "dimension", "factor_to_base"]


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "code",
            "name",
            "contact_person",
            "payment_terms_days",
            "lead_time_days",
            "minimum_order_amount",
            "supplies_wine",
            "rating",
            "is_active",
        ]


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "code", "name", "is_default", "is_active", "responsible"]


class StockItemSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    quantity_on_hand = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)
    average_unit_cost = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)
    stock_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_below_minimum = serializers.BooleanField(read_only=True)

    class Meta:
        model = StockItem
        fields = [
            "id",
            "code",
            "name",
            "name_en",
            "category",
            "category_name",
            "unit",
            "unit_code",
            "tracking_mode",
            "linked_wine",
            "minimum_quantity",
            "reorder_quantity",
            "shelf_life_days",
            "default_supplier",
            "barcode",
            "is_active",
            "quantity_on_hand",
            "average_unit_cost",
            "stock_value",
            "is_below_minimum",
        ]


class StockLotSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="stock_item.name", read_only=True)
    days_to_expiry = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = StockLot
        fields = [
            "id",
            "stock_item",
            "item_name",
            "warehouse",
            "lot_code",
            "supplier",
            "received_on",
            "expires_on",
            "quantity_received",
            "quantity_remaining",
            "unit_cost",
            "days_to_expiry",
            "is_expired",
        ]


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="stock_item.name", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "stock_item",
            "item_name",
            "lot",
            "warehouse",
            "movement_type",
            "quantity",
            "unit_cost",
            "occurred_at",
            "performed_by",
            "reference_type",
            "reference_id",
            "note",
        ]
        read_only_fields = fields


class WastageEntrySerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="stock_item.name", read_only=True)

    class Meta:
        model = WastageEntry
        fields = [
            "id",
            "stock_item",
            "item_name",
            "lot",
            "warehouse",
            "quantity",
            "reason",
            "occurred_at",
            "recorded_by",
            "estimated_cost",
            "description",
        ]
        read_only_fields = ["recorded_by", "estimated_cost"]


class PurchaseRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseRequest
        fields = [
            "id",
            "number",
            "requested_by",
            "warehouse",
            "needed_by",
            "status",
            "justification",
            "is_ai_suggested",
        ]
        read_only_fields = ["number", "requested_by"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "number",
            "supplier",
            "supplier_name",
            "warehouse",
            "request",
            "ordered_on",
            "expected_on",
            "status",
            "currency",
            "notes",
            "total_amount",
        ]
        read_only_fields = ["number"]


class GoodsReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoodsReceipt
        fields = [
            "id",
            "number",
            "order",
            "supplier",
            "warehouse",
            "received_on",
            "received_by",
            "invoice_number",
            "temperature_check_ok",
            "notes",
        ]
        read_only_fields = ["number", "received_by"]


class StockCountSerializer(serializers.ModelSerializer):
    total_variance_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = StockCount
        fields = [
            "id",
            "number",
            "warehouse",
            "counted_on",
            "status",
            "counted_by",
            "notes",
            "total_variance_value",
        ]
        read_only_fields = ["number", "counted_by"]


# ---------------------------------------------------------------------------
# Görünüm kümeleri
# ---------------------------------------------------------------------------
class StockItemViewSet(viewsets.ModelViewSet):
    queryset = (
        StockItem.objects.filter(is_deleted=False)
        .select_related("category", "unit", "default_supplier")
        .prefetch_related("lots")
    )
    serializer_class = StockItemSerializer
    search_fields = ["code", "name", "barcode"]
    ordering_fields = ["name", "code"]

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        if self.request.query_params.get("low_stock") == "1":
            ids = [item.pk for item in queryset if item.is_below_minimum]
            queryset = queryset.filter(pk__in=ids)
        return queryset

    @action(detail=False, methods=["get"])
    def reorder_suggestions(self, request: Request) -> Response:
        """Minimum seviyenin altındaki kalemler için sipariş önerisi.

        Öneridir; hiçbir sipariş otomatik oluşturulmaz.
        """
        suggestions = services.build_reorder_suggestions()
        return Response(
            {
                "count": len(suggestions),
                "note": "Bu bir öneridir; sipariş oluşturmak için kullanıcı onayı gerekir.",
                "items": suggestions,
            }
        )

    @action(detail=False, methods=["get"])
    def expiring(self, request: Request) -> Response:
        """Son kullanma tarihi yaklaşan partiler (FEFO uyarısı)."""
        days = int(request.query_params.get("days", 7))
        lots = services.expiring_lots(days=days)
        return Response(StockLotSerializer(lots, many=True).data)


class StockLotViewSet(viewsets.ModelViewSet):
    queryset = StockLot.objects.filter(is_deleted=False).select_related(
        "stock_item", "warehouse", "supplier"
    )
    serializer_class = StockLotSerializer
    search_fields = ["lot_code", "stock_item__name"]


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """Stok hareketleri salt okunurdur (değiştirilemez denetim izi)."""

    queryset = StockMovement.objects.select_related("stock_item", "warehouse", "lot")
    serializer_class = StockMovementSerializer


class WastageEntryViewSet(viewsets.ModelViewSet):
    queryset = WastageEntry.objects.select_related("stock_item", "warehouse", "lot")
    serializer_class = WastageEntrySerializer

    def perform_create(self, serializer: Any) -> None:
        item = serializer.validated_data["stock_item"]
        quantity = serializer.validated_data["quantity"]
        serializer.save(
            recorded_by=self.request.user,
            estimated_cost=(item.average_unit_cost * Decimal(str(quantity))).quantize(
                Decimal("0.01")
            ),
        )


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.filter(is_deleted=False)
    serializer_class = SupplierSerializer
    search_fields = ["code", "name", "contact_person"]


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.filter(is_active=True)
    serializer_class = WarehouseSerializer


class UnitOfMeasureViewSet(viewsets.ModelViewSet):
    queryset = UnitOfMeasure.objects.all()
    serializer_class = UnitOfMeasureSerializer


class PurchaseRequestViewSet(viewsets.ModelViewSet):
    queryset = PurchaseRequest.objects.filter(is_deleted=False).select_related(
        "warehouse", "requested_by"
    )
    serializer_class = PurchaseRequestSerializer

    def perform_create(self, serializer: Any) -> None:
        serializer.save(
            number=services.next_document_number(PurchaseRequest, "number", "STL"),
            requested_by=self.request.user,
            created_by=self.request.user,
        )


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseOrder.objects.filter(is_deleted=False)
        .select_related("supplier", "warehouse")
        .prefetch_related("lines")
    )
    serializer_class = PurchaseOrderSerializer

    def perform_create(self, serializer: Any) -> None:
        serializer.save(
            number=services.next_document_number(PurchaseOrder, "number", "SAS"),
            created_by=self.request.user,
        )

    @action(detail=True, methods=["get"])
    def quotation_comparison(self, request: Request, pk: str | None = None) -> Response:
        """Bağlı talebin tekliflerini karşılaştırır."""
        order = self.get_object()
        if order.request_id is None:
            return Response(
                {"detail": "Siparişe bağlı talep yok."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(services.compare_quotations(order.request))


class GoodsReceiptViewSet(viewsets.ModelViewSet):
    queryset = GoodsReceipt.objects.filter(is_deleted=False).select_related(
        "supplier", "warehouse", "order"
    )
    serializer_class = GoodsReceiptSerializer

    def perform_create(self, serializer: Any) -> None:
        serializer.save(
            number=services.next_document_number(GoodsReceipt, "number", "MKB"),
            received_by=self.request.user,
            created_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def post_to_stock(self, request: Request, pk: str | None = None) -> Response:
        """Mal kabul satırlarını stoğa işler (parti oluşturur)."""
        receipt = self.get_object()
        try:
            lots = services.post_goods_receipt(receipt=receipt, user=request.user)
        except services.InventoryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"created_lots": len(lots), "lots": StockLotSerializer(lots, many=True).data}
        )


class StockCountViewSet(viewsets.ModelViewSet):
    queryset = StockCount.objects.select_related("warehouse", "counted_by")
    serializer_class = StockCountSerializer

    def perform_create(self, serializer: Any) -> None:
        serializer.save(
            number=services.next_document_number(StockCount, "number", "SAY"),
            counted_by=self.request.user,
            created_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def post_variances(self, request: Request, pk: str | None = None) -> Response:
        """Sayım farklarını stok hareketi olarak işler."""
        count = self.get_object()
        if not request.user.has_perm("inventory.can_adjust_stock"):
            return Response({"detail": "Yetkiniz yok."}, status=status.HTTP_403_FORBIDDEN)
        try:
            movements = services.post_stock_count(count=count, user=request.user)
        except services.InventoryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"movements": len(movements)})
