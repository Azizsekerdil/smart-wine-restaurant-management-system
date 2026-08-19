"""Yapay zekâ URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.aiservices import views

app_name = "aiservices"

urlpatterns = [
    path("", views.AIConsoleView.as_view(), name="console"),
    path("saglayicilar/", views.ProviderSettingsView.as_view(), name="providers"),
    path("saglayicilar/test/", views.provider_health_check, name="provider-test"),
    path("sommelier/", views.SommelierAssistantView.as_view(), name="sommelier"),
    path("oneriler/", views.SuggestionQueueView.as_view(), name="suggestions"),
    path("maliyet/", views.CostDashboardView.as_view(), name="costs"),
]
