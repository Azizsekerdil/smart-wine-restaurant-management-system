"""Hesap URL yapılandırması."""

from __future__ import annotations

from django.contrib.auth import views as auth_views
from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    # --- Oturum ---
    path("giris/", views.WineHouseLoginView.as_view(), name="login"),
    path("cikis/", views.WineHouseLogoutView.as_view(), name="logout"),
    path("pin/", views.pin_login, name="pin-login"),
    # --- Parola değiştirme ---
    path("parola/", views.WineHousePasswordChangeView.as_view(), name="password-change"),
    path(
        "parola/tamam/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html"
        ),
        name="password-change-done",
    ),
    # --- Profil ---
    path("profil/", views.ProfileView.as_view(), name="profile"),
    # --- Kullanıcı yönetimi ---
    path("kullanicilar/", views.UserListView.as_view(), name="user-list"),
    path("kullanicilar/yeni/", views.UserCreateView.as_view(), name="user-create"),
    path("kullanicilar/<int:pk>/", views.UserUpdateView.as_view(), name="user-update"),
    # --- Roller ---
    path("roller/", views.RoleListView.as_view(), name="role-list"),
    path("roller/<str:code>/", views.RoleDetailView.as_view(), name="role-detail"),
    # --- Onay kuyruğu ---
    path("onaylar/", views.ApprovalQueueView.as_view(), name="approval-queue"),
    path("onaylar/<int:pk>/karar/", views.approval_decide, name="approval-decide"),
    # --- Denetim kaydı ---
    path("denetim/", views.AuditLogView.as_view(), name="audit-log"),
]
