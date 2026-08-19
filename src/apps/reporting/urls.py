"""Raporlama URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.reporting import views

app_name = "reporting"

urlpatterns = [
    path("", views.ReportListView.as_view(), name="report-list"),
    path("tahmin/", views.ForecastView.as_view(), name="forecast"),
    path("<slug:code>/", views.ReportDetailView.as_view(), name="report-detail"),
    path("<slug:code>/disa-aktar/<str:output_format>/", views.export_report, name="report-export"),
]
