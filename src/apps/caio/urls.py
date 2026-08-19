"""CAIO ajanı URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.caio import views

app_name = "caio"

urlpatterns = [
    path("", views.CaioDashboardView.as_view(), name="dashboard"),
    path("bulgular/", views.FindingListView.as_view(), name="findings"),
    path("gorevler/", views.ImprovementTaskListView.as_view(), name="tasks"),
    path("calistir/", views.run_observation, name="run"),
]
