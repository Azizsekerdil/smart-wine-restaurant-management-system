"""Menü API yönlendirmeleri."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.catalog import api

router = DefaultRouter()
router.register("categories", api.MenuCategoryViewSet, basename="api-menucategory")
router.register("items", api.MenuItemViewSet, basename="api-menuitem")
router.register("recipes", api.RecipeViewSet, basename="api-recipe")
router.register("allergens", api.AllergenViewSet, basename="api-allergen")
router.register("price-rules", api.PriceRuleViewSet, basename="api-pricerule")

urlpatterns = router.urls
