"""Raporlama API yönlendirmeleri."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.reporting import api

router = DefaultRouter()
router.register("reports", api.ReportViewSet, basename="api-report")
router.register("runs", api.ReportRunViewSet, basename="api-reportrun")
router.register("daily-sales", api.DailySalesSnapshotViewSet, basename="api-dailysales")
router.register("forecasts", api.SalesForecastViewSet, basename="api-forecast")

urlpatterns = router.urls
