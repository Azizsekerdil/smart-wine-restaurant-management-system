"""Yedekleme URL yapılandırması."""

from __future__ import annotations

from django.urls import path

from apps.backups import views

app_name = "backups"

urlpatterns = [
    path("", views.BackupListView.as_view(), name="backup-list"),
    path("al/", views.create_backup_view, name="backup-create"),
    path("<int:pk>/dogrula/", views.verify_backup_view, name="backup-verify"),
    path("geri-yukle/", views.RestoreView.as_view(), name="restore"),
]
