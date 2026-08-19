"""AI Development Studio URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.devstudio import views

app_name = "devstudio"

urlpatterns = [
    path("", views.StudioHomeView.as_view(), name="home"),
    path("politika/", views.PolicyView.as_view(), name="policy"),
    path("oturum/<int:pk>/", views.SessionDetailView.as_view(), name="session-detail"),
    path("denetim/", views.StudioAuditView.as_view(), name="audit"),
]
