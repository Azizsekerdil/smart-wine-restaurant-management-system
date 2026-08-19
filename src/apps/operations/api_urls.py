"""Operasyon API yönlendirmeleri."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.operations import api

router = DefaultRouter()
router.register("sections", api.FloorSectionViewSet, basename="api-floorsection")
router.register("tables", api.DiningTableViewSet, basename="api-diningtable")
router.register("orders", api.OrderViewSet, basename="api-order")
router.register("tickets", api.PrepTicketViewSet, basename="api-prepticket")
router.register("reservations", api.ReservationViewSet, basename="api-reservation")
router.register("waitlist", api.WaitlistEntryViewSet, basename="api-waitlist")
router.register("payment-methods", api.PaymentMethodViewSet, basename="api-paymentmethod")
router.register("business-days", api.BusinessDayViewSet, basename="api-businessday")

urlpatterns = router.urls
