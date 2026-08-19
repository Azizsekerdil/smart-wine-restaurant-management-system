"""Çekirdek URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("ayarlar/", views.SettingsView.as_view(), name="settings"),
    path("ozellik-durumu/", views.FeatureStatusView.as_view(), name="feature-status"),
    path("dil/", views.set_language_preference, name="set-language"),
]
