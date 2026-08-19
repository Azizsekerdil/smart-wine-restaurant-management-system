"""İnsan kaynakları API yönlendirmeleri."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.hr import api

router = DefaultRouter()
router.register("employees", api.EmployeeViewSet, basename="api-employee")
router.register("shifts", api.ShiftViewSet, basename="api-shift")
router.register("assignments", api.ShiftAssignmentViewSet, basename="api-shiftassignment")
router.register("leaves", api.LeaveRequestViewSet, basename="api-leaverequest")
router.register("performance", api.PerformanceMetricViewSet, basename="api-performance")

urlpatterns = router.urls
