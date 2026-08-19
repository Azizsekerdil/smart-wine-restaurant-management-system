"""Menü URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.catalog import views

app_name = "catalog"

urlpatterns = [
    path("", views.MenuItemListView.as_view(), name="menuitem-list"),
    path("<int:pk>/", views.MenuItemDetailView.as_view(), name="menuitem-detail"),
    path("muhendislik/", views.MenuEngineeringView.as_view(), name="menu-engineering"),
    # QR menü — kimlik doğrulama gerektirmez
    path("qr/", views.qr_menu, name="qr-menu"),
    path("qr/<str:token>/", views.qr_menu, name="qr-menu-table"),
]
