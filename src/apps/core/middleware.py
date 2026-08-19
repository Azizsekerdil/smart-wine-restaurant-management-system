"""Çekirdek ara katmanlar."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from apps.core.audit import (
    _client_ip,
    clear_audit_context,
    record_permission_denied,
    set_audit_context,
)

#: PIN oturumunun erişebildiği URL ad alanları (salon / mutfak / bar).
PIN_SCOPE_NAMESPACES = frozenset({"operations", "catalog", "cellar", "training", "core"})

#: PIN oturumunda ``core`` ad alanında yasaklanan görünümler (yönetim ekranları).
PIN_SCOPE_CORE_DENIED = frozenset({"settings", "feature-status"})

#: PIN oturumunun ``accounts`` ad alanında erişebildiği görünümler.
PIN_SCOPE_ACCOUNT_VIEWS = frozenset(
    {"logout", "profile", "password-change", "password-change-done"}
)

#: Parola değiştirmesi zorunlu kullanıcının erişebildiği görünümler.
PASSWORD_CHANGE_ALLOWED = frozenset(
    {
        "accounts:password-change",
        "accounts:password-change-done",
        "accounts:logout",
        "accounts:login",
        "accounts:pin-login",
        "core:set-language",
    }
)

#: Oturum anahtarı: girişin hangi yöntemle yapıldığı ("password" | "pin").
AUTH_SCOPE_SESSION_KEY = "winehouse_auth_scope"


class AuditContextMiddleware:
    """İstek bağlamını (kullanıcı, IP, istemci) denetim kaydına taşır.

    Servis katmanındaki fonksiyonlar ``request`` nesnesine erişemez; bu ara
    katman sayesinde ``apps.core.audit.record`` çağrıları kullanıcıyı ve IP'yi
    otomatik olarak bulur.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        set_audit_context(
            user=getattr(request, "user", None),
            ip=_client_ip(request),
            agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        try:
            response = self.get_response(request)
        finally:
            clear_audit_context()
        return response

    def process_exception(self, request: HttpRequest, exception: Exception) -> Any:
        clear_audit_context()
        return None


def _route_name(request: HttpRequest) -> tuple[str, str, str]:
    """(ad alanı, görünüm adı, tam ad) üçlüsünü döndürür."""
    match = getattr(request, "resolver_match", None)
    if match is None:
        return "", "", ""
    namespace = match.namespace or ""
    name = match.url_name or ""
    full = f"{namespace}:{name}" if namespace else name
    return namespace, name, full


class PasswordChangeRequiredMiddleware:
    """``must_change_password`` işaretli kullanıcıyı parola değiştirmeye zorlar.

    Bu ara katman olmadan bayrak yalnızca bir uyarı mesajıydı: kullanıcı
    parolasını değiştirmeden tüm ekranlara erişebiliyordu. Artık **parola
    değiştirilene kadar** yalnızca parola değiştirme, çıkış ve dil değiştirme
    görünümleri açıktır; diğer her istek parola ekranına yönlendirilir.

    Django yönetim paneli (``/django-admin/``) ve REST API dâhil tüm yollar
    kapsanır; API istekleri 403 alır (yönlendirme anlamlı olmaz).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_view(
        self, request: HttpRequest, view_func: Any, view_args: Any, view_kwargs: Any
    ) -> HttpResponse | None:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        if not getattr(user, "must_change_password", False):
            return None

        _namespace, _name, full = _route_name(request)
        if full in PASSWORD_CHANGE_ALLOWED:
            return None

        record_permission_denied(
            request,
            f"Parola değişimi zorunluyken erişim denendi: {request.path}",
        )
        if request.path.startswith("/api/"):
            raise PermissionDenied(_("Parolanızı değiştirmeden bu kaynağa erişemezsiniz."))
        return redirect("accounts:password-change")


class PinSessionScopeMiddleware:
    """PIN ile açılan oturumu salon/mutfak ekranlarıyla sınırlar.

    POS terminalinde PIN girişi 4–8 rakamdır; parola kadar güçlü değildir.
    Bu nedenle PIN oturumu **yönetim yüzeyine erişemez**: kullanıcı ve rol
    yönetimi, denetim kaydı, onay kuyruğu, raporlar, İK, CRM, yedekleme,
    yapay zekâ ayarları, AI Development Studio, CAIO ve Django yönetim paneli
    kapalıdır. Aynı kullanıcı bu ekranlar için parolayla giriş yapmalıdır.

    Kapsam, kullanıcının rollerini *daraltır*; hiçbir zaman genişletmez.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_view(
        self, request: HttpRequest, view_func: Any, view_args: Any, view_kwargs: Any
    ) -> HttpResponse | None:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        session = getattr(request, "session", None)
        if session is None or session.get(AUTH_SCOPE_SESSION_KEY) != "pin":
            return None

        namespace, name, _full = _route_name(request)

        allowed = False
        if namespace == "accounts":
            allowed = name in PIN_SCOPE_ACCOUNT_VIEWS
        elif namespace == "core":
            allowed = name not in PIN_SCOPE_CORE_DENIED
        elif namespace in PIN_SCOPE_NAMESPACES:
            allowed = True

        if allowed:
            return None

        record_permission_denied(
            request,
            f"PIN oturumu kapsam dışı ekrana erişmeye çalıştı: {request.path}",
        )
        raise PermissionDenied(
            _(
                "PIN girişi yalnızca salon, mutfak ve bar ekranları içindir. "
                "Bu ekran için parolanızla giriş yapın."
            )
        )
