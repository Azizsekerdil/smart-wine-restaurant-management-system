"""CRM URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.crm import views

app_name = "crm"

urlpatterns = [
    path("", views.CustomerListView.as_view(), name="customer-list"),
    path("<int:pk>/", views.CustomerDetailView.as_view(), name="customer-detail"),
    path("kampanyalar/", views.CampaignListView.as_view(), name="campaign-list"),
    path("kvkk/", views.PrivacyCenterView.as_view(), name="privacy-center"),
]
