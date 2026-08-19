"""Eğitim merkezi URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.training import views

app_name = "training"

urlpatterns = [
    path("", views.TrainingHomeView.as_view(), name="home"),
    path("modul/<slug:code>/", views.ModuleDetailView.as_view(), name="module-detail"),
    path("ders/<int:pk>/", views.LessonDetailView.as_view(), name="lesson-detail"),
    path("ders/<int:pk>/tamamla/", views.complete_lesson, name="lesson-complete"),
]
