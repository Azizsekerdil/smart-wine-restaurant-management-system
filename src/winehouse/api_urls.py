"""Wine House — REST API v1 kök yönlendirmesi.

Tüm uygulama API'leri burada tek bir yönlendirici altında toplanır.
Ayrıntılı uç nokta dökümü: ``docs/API.md``
"""

from __future__ import annotations

from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

from apps.core.api import api_root, health_check

urlpatterns = [
    # --- Servis durumu ve keşif ---
    path("", api_root, name="api-root"),
    path("health/", health_check, name="api-health"),
    # --- Belirteç (token) alma ---
    path("auth/token/", obtain_auth_token, name="api-token"),
    # --- Uygulama API'leri ---
    path("catalog/", include("apps.catalog.api_urls")),
    path("cellar/", include("apps.cellar.api_urls")),
    path("inventory/", include("apps.inventory.api_urls")),
    path("operations/", include("apps.operations.api_urls")),
    path("crm/", include("apps.crm.api_urls")),
    path("hr/", include("apps.hr.api_urls")),
    path("reporting/", include("apps.reporting.api_urls")),
    path("ai/", include("apps.aiservices.api_urls")),
]
