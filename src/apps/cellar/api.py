"""Şarap kavı REST API'si."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.cellar import services
from apps.cellar.models import (
    BottleLot,
    BottleOpening,
    GrapeVariety,
    PouringRecord,
    StorageReading,
    TastingNote,
    Wine,
    WineFault,
    WinePairing,
    WineProducer,
    WineRegion,
    WineStorageLocation,
)


class WineRegionSerializer(serializers.ModelSerializer):
    full_path = serializers.CharField(read_only=True)

    class Meta:
        model = WineRegion
        fields = ["id", "name", "name_en", "level", "parent", "country_code", "full_path"]


class GrapeVarietySerializer(serializers.ModelSerializer):
    class Meta:
        model = GrapeVariety
        fields = ["id", "name", "name_en", "color", "synonyms", "is_indigenous_turkish"]


class WineProducerSerializer(serializers.ModelSerializer):
    class Meta:
        model = WineProducer
        fields = ["id", "name", "region", "website", "founded_year", "is_organic", "is_biodynamic"]


class WineSerializer(serializers.ModelSerializer):
    producer_name = serializers.CharField(source="producer.name", read_only=True)
    region_path = serializers.CharField(source="region.full_path", read_only=True)
    grape_summary = serializers.CharField(read_only=True)
    bottles_on_hand = serializers.IntegerField(read_only=True)
    glasses_available = serializers.IntegerField(read_only=True)
    stock_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    drink_window = serializers.SerializerMethodField()
    serving_temp_display = serializers.CharField(read_only=True)

    class Meta:
        model = Wine
        fields = [
            "id",
            "sku",
            "name",
            "producer",
            "producer_name",
            "vineyard",
            "region",
            "region_path",
            "vintage",
            "wine_type",
            "sweetness",
            "alcohol_percent",
            "bottle_size_ml",
            "is_organic",
            "is_vegan",
            "serving_temp_min_c",
            "serving_temp_max_c",
            "serving_temp_display",
            "decant_minutes",
            "glass_type",
            "body",
            "acidity",
            "tannin",
            "sweetness_level",
            "aroma_profile",
            "drink_from_year",
            "drink_until_year",
            "peak_year",
            "drink_window",
            "purchase_price",
            "bottle_price",
            "glass_price",
            "glass_pour_ml",
            "sold_by_glass",
            "barcode",
            "is_active",
            "is_on_wine_list",
            "minimum_bottles",
            "grape_summary",
            "bottles_on_hand",
            "glasses_available",
            "stock_value",
            "tasting_notes_house",
        ]

    def get_drink_window(self, obj: Wine) -> dict[str, str]:
        return {"status": obj.drink_window_status(), "label": str(obj.drink_window_label())}


class BottleLotSerializer(serializers.ModelSerializer):
    wine_name = serializers.CharField(source="wine.name", read_only=True)
    total_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = BottleLot
        fields = [
            "id",
            "wine",
            "wine_name",
            "lot_code",
            "supplier",
            "location",
            "received_on",
            "best_before",
            "bottles_received",
            "bottles_remaining",
            "unit_cost",
            "total_value",
            "invoice_reference",
        ]


class BottleOpeningSerializer(serializers.ModelSerializer):
    wine_name = serializers.CharField(source="wine.name", read_only=True)
    glasses_remaining = serializers.IntegerField(read_only=True)
    glasses_poured = serializers.IntegerField(read_only=True)
    yield_percent = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    is_past_freshness = serializers.BooleanField(read_only=True)

    class Meta:
        model = BottleOpening
        fields = [
            "id",
            "wine",
            "wine_name",
            "lot",
            "opened_at",
            "opened_by",
            "service_method",
            "initial_ml",
            "remaining_ml",
            "status",
            "freshness_hours",
            "closed_at",
            "glasses_remaining",
            "glasses_poured",
            "yield_percent",
            "is_past_freshness",
        ]
        read_only_fields = ["remaining_ml", "status", "closed_at"]


class PouringRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PouringRecord
        fields = [
            "id",
            "opening",
            "pour_type",
            "volume_ml",
            "poured_at",
            "poured_by",
            "order_line",
            "note",
        ]


class TastingNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TastingNote
        fields = [
            "id",
            "wine",
            "author_type",
            "author_user",
            "author_name",
            "tasted_on",
            "appearance",
            "nose",
            "palate",
            "finish",
            "conclusion",
            "body",
            "acidity",
            "tannin",
            "sweetness",
            "is_ai_generated",
            "is_published",
        ]


class WinePairingSerializer(serializers.ModelSerializer):
    target_label = serializers.CharField(read_only=True)

    class Meta:
        model = WinePairing
        fields = [
            "id",
            "wine",
            "pairing_type",
            "menu_item",
            "free_text",
            "target_label",
            "strength",
            "rationale",
            "is_ai_suggested",
            "is_approved",
        ]


class StorageLocationSerializer(serializers.ModelSerializer):
    full_path = serializers.CharField(read_only=True)
    bottles_stored = serializers.IntegerField(read_only=True)
    occupancy_percent = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = WineStorageLocation
        fields = [
            "id",
            "code",
            "name",
            "location_type",
            "parent",
            "full_path",
            "capacity_bottles",
            "bottles_stored",
            "occupancy_percent",
            "target_temp_c",
            "temp_tolerance_c",
            "target_humidity_percent",
            "is_active",
        ]


class StorageReadingSerializer(serializers.ModelSerializer):
    has_alert = serializers.BooleanField(read_only=True)

    class Meta:
        model = StorageReading
        fields = [
            "id",
            "location",
            "recorded_at",
            "temperature_c",
            "humidity_percent",
            "source",
            "recorded_by",
            "note",
            "has_alert",
        ]


class WineFaultSerializer(serializers.ModelSerializer):
    class Meta:
        model = WineFault
        fields = [
            "id",
            "wine",
            "lot",
            "opening",
            "fault_type",
            "detected_at",
            "detected_by",
            "bottles_affected",
            "volume_lost_ml",
            "estimated_loss",
            "resolution",
            "description",
        ]


# ---------------------------------------------------------------------------
# Görünüm kümeleri
# ---------------------------------------------------------------------------
class WineViewSet(viewsets.ModelViewSet):
    queryset = (
        Wine.objects.filter(is_deleted=False)
        .select_related("producer", "region")
        .prefetch_related("grape_compositions__grape", "lots")
    )
    serializer_class = WineSerializer
    search_fields = ["sku", "name", "producer__name", "barcode"]
    ordering_fields = ["name", "vintage", "bottle_price"]

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        wine_type = self.request.query_params.get("type")
        if wine_type:
            queryset = queryset.filter(wine_type=wine_type)
        if self.request.query_params.get("by_glass") == "1":
            queryset = queryset.filter(sold_by_glass=True)
        return queryset

    @action(detail=True, methods=["post"])
    def open_bottle(self, request: Request, pk: str | None = None) -> Response:
        """Şişe açar ve stoktan düşer."""
        wine = self.get_object()
        try:
            opening = services.open_bottle(
                wine=wine,
                user=request.user,
                service_method=request.data.get(
                    "service_method", BottleOpening.ServiceMethod.STANDARD
                ),
                note=request.data.get("note", ""),
            )
        except services.CellarError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BottleOpeningSerializer(opening).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def pour(self, request: Request, pk: str | None = None) -> Response:
        """Kadeh servis eder; gerekirse yeni şişe açar."""
        wine = self.get_object()
        try:
            result = services.pour_glass(
                wine=wine,
                user=request.user,
                volume_ml=request.data.get("volume_ml"),
                pour_type=request.data.get("pour_type", PouringRecord.PourType.GLASS_SALE),
                note=request.data.get("note", ""),
            )
        except services.CellarError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "pour": PouringRecordSerializer(result.pour).data,
                "opening": BottleOpeningSerializer(result.opening).data,
                "opened_new_bottle": result.opened_new_bottle,
                "remaining_glasses": result.remaining_glasses,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def valuation(self, request: Request) -> Response:
        """Kav değerlemesi."""
        if not request.user.has_perm("cellar.can_view_cellar_valuation"):
            return Response({"detail": "Yetkiniz yok."}, status=status.HTTP_403_FORBIDDEN)
        data = services.cellar_valuation()
        return Response({key: str(value) for key, value in data.items()})

    @action(detail=False, methods=["get"])
    def drink_window_alerts(self, request: Request) -> Response:
        """İçim aralığı uyarıları."""
        alerts = services.drink_window_alerts()
        return Response(
            [
                {
                    "wine_id": item["wine"].pk,
                    "wine": str(item["wine"]),
                    "status": item["status"],
                    "label": str(item["label"]),
                    "bottles": item["bottles"],
                    "value": str(item["value"]),
                }
                for item in alerts
            ]
        )

    @action(detail=False, methods=["post"])
    def detect_duplicates(self, request: Request) -> Response:
        """Mükerrer kayıt taraması yapar (hiçbir kayıt silinmez)."""
        alerts = services.detect_duplicates()
        return Response(
            {
                "found": len(alerts),
                "alerts": [
                    {
                        "id": alert.pk,
                        "wine": str(alert.wine),
                        "reason": alert.get_reason_display(),
                        "detail": alert.detail,
                        "confidence": str(alert.confidence),
                    }
                    for alert in alerts
                ],
            }
        )


class BottleLotViewSet(viewsets.ModelViewSet):
    queryset = BottleLot.objects.filter(is_deleted=False).select_related("wine", "location")
    serializer_class = BottleLotSerializer
    search_fields = ["lot_code", "wine__name", "wine__sku"]


class BottleOpeningViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BottleOpening.objects.select_related("wine", "lot").prefetch_related("pours")
    serializer_class = BottleOpeningSerializer

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        if self.request.query_params.get("open") == "1":
            queryset = queryset.filter(status=BottleOpening.Status.OPEN)
        return queryset

    @action(detail=True, methods=["post"])
    def finish(self, request: Request, pk: str | None = None) -> Response:
        """Açık şişeyi kapatır."""
        opening = self.get_object()
        try:
            closed = services.finish_bottle(
                opening=opening,
                user=request.user,
                as_waste=bool(request.data.get("as_waste", True)),
                note=request.data.get("note", ""),
            )
        except services.CellarError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BottleOpeningSerializer(closed).data)


class TastingNoteViewSet(viewsets.ModelViewSet):
    queryset = TastingNote.objects.select_related("wine")
    serializer_class = TastingNoteSerializer


class WinePairingViewSet(viewsets.ModelViewSet):
    queryset = WinePairing.objects.select_related("wine", "menu_item")
    serializer_class = WinePairingSerializer


class StorageLocationViewSet(viewsets.ModelViewSet):
    queryset = WineStorageLocation.objects.select_related("parent")
    serializer_class = StorageLocationSerializer


class StorageReadingViewSet(viewsets.ModelViewSet):
    queryset = StorageReading.objects.select_related("location")
    serializer_class = StorageReadingSerializer

    def perform_create(self, serializer: Any) -> None:
        serializer.save(recorded_by=self.request.user)


class WineFaultViewSet(viewsets.ModelViewSet):
    queryset = WineFault.objects.select_related("wine", "lot")
    serializer_class = WineFaultSerializer


class WineRegionViewSet(viewsets.ModelViewSet):
    queryset = WineRegion.objects.select_related("parent")
    serializer_class = WineRegionSerializer
    search_fields = ["name", "name_en"]


class GrapeVarietyViewSet(viewsets.ModelViewSet):
    queryset = GrapeVariety.objects.all()
    serializer_class = GrapeVarietySerializer
    search_fields = ["name", "synonyms"]


class WineProducerViewSet(viewsets.ModelViewSet):
    queryset = WineProducer.objects.select_related("region")
    serializer_class = WineProducerSerializer
    search_fields = ["name"]
