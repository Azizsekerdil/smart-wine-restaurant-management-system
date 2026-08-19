"""Operasyon URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.operations import views

app_name = "operations"

urlpatterns = [
    path("", views.TableMapView.as_view(), name="table-map"),
    path("adisyonlar/", views.OrderListView.as_view(), name="order-list"),
    path("adisyon/<int:pk>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("rezervasyonlar/", views.ReservationListView.as_view(), name="reservation-list"),
    path("bekleme-listesi/", views.WaitlistView.as_view(), name="waitlist"),
    path("mutfak/", views.KitchenDisplayView.as_view(), name="kds-kitchen"),
    path("bar/", views.BarDisplayView.as_view(), name="kds-bar"),
    path("sarap-ekrani/", views.WineDisplayView.as_view(), name="kds-wine"),
    path("gun-sonu/", views.BusinessDayView.as_view(), name="business-day"),
]
