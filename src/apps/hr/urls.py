"""İnsan kaynakları URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.hr import views

app_name = "hr"

urlpatterns = [
    path("", views.EmployeeListView.as_view(), name="employee-list"),
    path("<int:pk>/", views.EmployeeDetailView.as_view(), name="employee-detail"),
    path("vardiyalar/", views.ShiftListView.as_view(), name="shift-list"),
    path("izinler/", views.LeaveRequestListView.as_view(), name="leave-list"),
    path("performans/", views.PerformanceView.as_view(), name="performance"),
]
