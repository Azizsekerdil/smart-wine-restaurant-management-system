"""Şarap kavı URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.cellar import views

app_name = "cellar"

urlpatterns = [
    path("", views.WineListView.as_view(), name="wine-list"),
    path("<int:pk>/", views.WineDetailView.as_view(), name="wine-detail"),
    path("<int:pk>/sise-ac/", views.open_bottle_action, name="open-bottle"),
    path("<int:pk>/kadeh-servis/", views.pour_glass_action, name="pour-glass"),
    path("acik-siseler/", views.OpenBottleListView.as_view(), name="open-bottles"),
    path("konumlar/", views.StorageListView.as_view(), name="storage-list"),
    path("degerleme/", views.CellarValuationView.as_view(), name="valuation"),
    path("mukerrer/", views.DuplicateAlertListView.as_view(), name="duplicate-alerts"),
    path("mukerrer/tara/", views.run_duplicate_scan, name="duplicate-scan"),
]
