"""CRM API yönlendirmeleri."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.crm import api

router = DefaultRouter()
router.register("customers", api.CustomerViewSet, basename="api-customer")
router.register("consents", api.ConsentRecordViewSet, basename="api-consent")
router.register("loyalty-accounts", api.LoyaltyAccountViewSet, basename="api-loyaltyaccount")
router.register("loyalty-transactions", api.LoyaltyTransactionViewSet, basename="api-loyaltytx")
router.register("loyalty-programs", api.LoyaltyProgramViewSet, basename="api-loyaltyprogram")
router.register("campaigns", api.CampaignViewSet, basename="api-campaign")
router.register("visit-notes", api.VisitNoteViewSet, basename="api-visitnote")

urlpatterns = router.urls
