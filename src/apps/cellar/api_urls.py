"""Şarap kavı API yönlendirmeleri."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.cellar import api

router = DefaultRouter()
router.register("wines", api.WineViewSet, basename="api-wine")
router.register("lots", api.BottleLotViewSet, basename="api-bottlelot")
router.register("openings", api.BottleOpeningViewSet, basename="api-bottleopening")
router.register("tasting-notes", api.TastingNoteViewSet, basename="api-tastingnote")
router.register("pairings", api.WinePairingViewSet, basename="api-winepairing")
router.register("locations", api.StorageLocationViewSet, basename="api-storagelocation")
router.register("readings", api.StorageReadingViewSet, basename="api-storagereading")
router.register("faults", api.WineFaultViewSet, basename="api-winefault")
router.register("regions", api.WineRegionViewSet, basename="api-wineregion")
router.register("grapes", api.GrapeVarietyViewSet, basename="api-grapevariety")
router.register("producers", api.WineProducerViewSet, basename="api-wineproducer")

urlpatterns = router.urls
