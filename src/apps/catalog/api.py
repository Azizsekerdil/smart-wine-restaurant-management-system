"""Menü REST API'si."""

from __future__ import annotations

from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.catalog.models import (
    Allergen,
    DietaryTag,
    MenuCategory,
    MenuItem,
    PriceRule,
    Recipe,
    RecipeLine,
)


class AllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergen
        fields = ["id", "code", "name_tr", "name_en", "description", "icon"]


class DietaryTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = DietaryTag
        fields = ["id", "code", "name_tr", "name_en", "badge_class"]


class MenuCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuCategory
        fields = [
            "id",
            "code",
            "name_tr",
            "name_en",
            "parent",
            "channel",
            "preparation_station",
            "sort_order",
            "is_active",
            "show_on_qr_menu",
        ]


class MenuItemSerializer(serializers.ModelSerializer):
    allergens = AllergenSerializer(many=True, read_only=True)
    dietary_tags = DietaryTagSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source="category.name_tr", read_only=True)
    price_with_tax = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    margin_percent = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    food_cost_percent = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = MenuItem
        fields = [
            "id",
            "code",
            "name_tr",
            "name_en",
            "description_tr",
            "description_en",
            "category",
            "category_name",
            "item_type",
            "wine",
            "base_price",
            "tax_rate",
            "cost_price",
            "price_with_tax",
            "effective_price",
            "margin_percent",
            "food_cost_percent",
            "portion_size",
            "preparation_minutes",
            "calories",
            "allergens",
            "dietary_tags",
            "is_active",
            "is_available",
            "show_on_qr_menu",
            "is_chef_recommendation",
            "is_sommelier_recommendation",
            "tracks_stock",
        ]
        read_only_fields = ["cost_price"]


class RecipeLineSerializer(serializers.ModelSerializer):
    stock_item_name = serializers.CharField(source="stock_item.name", read_only=True)
    unit = serializers.CharField(source="stock_item.unit.code", read_only=True)

    class Meta:
        model = RecipeLine
        fields = [
            "id",
            "recipe",
            "stock_item",
            "stock_item_name",
            "unit",
            "quantity",
            "note",
            "is_optional",
        ]


class RecipeSerializer(serializers.ModelSerializer):
    lines = RecipeLineSerializer(many=True, read_only=True)
    total_cost = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = [
            "id",
            "menu_item",
            "yield_portions",
            "instructions",
            "plating_notes",
            "waste_allowance_percent",
            "lines",
            "total_cost",
        ]

    def get_total_cost(self, obj: Recipe) -> str:
        return str(obj.total_cost())


class PriceRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceRule
        fields = [
            "id",
            "name",
            "rule_type",
            "value",
            "starts_on",
            "ends_on",
            "starts_at",
            "ends_at",
            "weekdays",
            "is_active",
            "requires_approval",
        ]


# ---------------------------------------------------------------------------
# Görünüm kümeleri
# ---------------------------------------------------------------------------
class MenuCategoryViewSet(viewsets.ModelViewSet):
    queryset = MenuCategory.objects.select_related("parent").all()
    serializer_class = MenuCategorySerializer
    search_fields = ["code", "name_tr", "name_en"]
    ordering_fields = ["sort_order", "name_tr"]


class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = (
        MenuItem.objects.filter(is_deleted=False)
        .select_related("category", "wine")
        .prefetch_related("allergens", "dietary_tags", "price_rules")
    )
    serializer_class = MenuItemSerializer
    search_fields = ["code", "name_tr", "name_en"]
    ordering_fields = ["name_tr", "base_price", "sort_order"]

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        item_type = self.request.query_params.get("item_type")
        if item_type:
            queryset = queryset.filter(item_type=item_type)
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category_id=category)
        if self.request.query_params.get("available") == "1":
            queryset = queryset.filter(is_active=True, is_available=True)
        return queryset

    @action(detail=True, methods=["post"])
    def recalculate_cost(self, request: Request, pk: str | None = None) -> Response:
        """Reçeteden porsiyon maliyetini yeniden hesaplar."""
        item = self.get_object()
        cost = item.recalculate_cost()
        return Response({"id": item.pk, "cost_price": str(cost)})


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.select_related("menu_item").prefetch_related("lines__stock_item")
    serializer_class = RecipeSerializer


class AllergenViewSet(viewsets.ModelViewSet):
    queryset = Allergen.objects.all()
    serializer_class = AllergenSerializer
    search_fields = ["code", "name_tr", "name_en"]


class PriceRuleViewSet(viewsets.ModelViewSet):
    queryset = PriceRule.objects.all()
    serializer_class = PriceRuleSerializer
