"""Çekirdek REST API uç noktaları: servis keşfi ve sağlık kontrolü."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.reverse import reverse

from winehouse import __version__


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_root(request: Request, format: str | None = None) -> Response:
    """API kök dizini: kullanılabilir modüllerin listesi."""
    return Response(
        {
            "name": "Wine House API",
            "version": __version__,
            "modules": {
                "catalog": reverse("api-menuitem-list", request=request, format=format),
                "cellar": reverse("api-wine-list", request=request, format=format),
                "inventory": reverse("api-stockitem-list", request=request, format=format),
                "operations": reverse("api-order-list", request=request, format=format),
                "crm": reverse("api-customer-list", request=request, format=format),
                "hr": reverse("api-employee-list", request=request, format=format),
                "reporting": reverse("api-report-list", request=request, format=format),
                "ai": reverse("api-aiprovider-list", request=request, format=format),
            },
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request: Request) -> Response:
    """Servis sağlık kontrolü.

    Başlatma betikleri (``CHECK_WINE_HOUSE.bat``) bu uç noktayı kullanır.
    Gizli hiçbir bilgi döndürmez.
    """
    database_ok = True
    database_error = ""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # pragma: no cover - veritabanı arızası yolu
        database_ok = False
        database_error = type(exc).__name__

    payload: dict[str, Any] = {
        "status": "ok" if database_ok else "degraded",
        "version": __version__,
        "database": {
            "engine": settings.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1],
            "reachable": database_ok,
        },
        "ai": {
            "default_provider": settings.AI_SETTINGS.get("DEFAULT_PROVIDER"),
            "local_only": settings.AI_SETTINGS.get("LOCAL_ONLY"),
            "privacy_mode": settings.AI_SETTINGS.get("PRIVACY_MODE"),
        },
        "payment_mode": settings.PAYMENT_MODE,
        "offline_capable": True,
    }
    if database_error:
        payload["database"]["error"] = database_error

    return Response(payload, status=200 if database_ok else 503)
