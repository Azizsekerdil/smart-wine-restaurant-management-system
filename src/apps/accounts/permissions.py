"""Yetkilendirme yardımcıları: karışımlar (mixin) ve dekoratörler.

Django'nun standart yetki kontrollerine iki davranış ekler:

1. **Denetim kaydı** — her reddedilen erişim ``AuditLog``'a yazılır.
2. **Salt okunur koruma** — denetçi rolündeki kullanıcıların yazma isteği
   (POST/PUT/PATCH/DELETE) HTTP yönteminden bağımsız olarak reddedilir.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import wraps
from typing import Any

from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse

from apps.core.audit import record_permission_denied

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _deny(request: HttpRequest, message: str) -> None:
    """Erişimi reddeder ve denetim kaydı yazar."""
    record_permission_denied(request, message)
    raise PermissionDenied(message)


class AuditedPermissionMixin(LoginRequiredMixin, AccessMixin):
    """İzin denetimi yapan ve reddi kaydeden temel karışım.

    Kullanım::

        class WineListView(AuditedPermissionMixin, ListView):
            required_permissions = ["cellar.view_wine"]
    """

    #: Gerekli izinler (hepsi sağlanmalıdır)
    required_permissions: Iterable[str] = ()
    #: Gerekli rollerden en az biri (boşsa rol kontrolü yapılmaz)
    required_roles: Iterable[str] = ()
    #: True ise salt okunur kullanıcılar yazma isteği yapamaz
    block_read_only_writes: bool = True

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()

        view_name = self.__class__.__name__

        if (
            self.block_read_only_writes
            and request.method in WRITE_METHODS
            and getattr(user, "is_read_only", False)
        ):
            _deny(
                request,
                f"Salt okunur kullanıcı yazma işlemi denedi: {view_name} "
                f"({request.method} {request.path})",
            )

        missing = [perm for perm in self.required_permissions if not user.has_perm(perm)]
        if missing and not user.is_superuser:
            _deny(
                request,
                f"Yetersiz izin: {view_name} — eksik izinler: {', '.join(missing)} "
                f"({request.path})",
            )

        roles = set(self.required_roles)
        if roles and not user.is_superuser and not (roles & getattr(user, "role_codes", set())):
            _deny(
                request,
                f"Yetersiz rol: {view_name} — gereken rollerden biri: "
                f"{', '.join(sorted(roles))} ({request.path})",
            )

        return super().dispatch(request, *args, **kwargs)


def permission_required_audited(*permissions: str) -> Callable:
    """Fonksiyon tabanlı görünümler için izin dekoratörü."""

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            user = request.user
            if not user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())

            if request.method in WRITE_METHODS and getattr(user, "is_read_only", False):
                _deny(
                    request,
                    f"Salt okunur kullanıcı yazma işlemi denedi: {view_func.__name__}",
                )

            missing = [perm for perm in permissions if not user.has_perm(perm)]
            if missing and not user.is_superuser:
                _deny(
                    request,
                    f"Yetersiz izin: {view_func.__name__} — eksik: {', '.join(missing)}",
                )
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def role_required(*role_codes: str) -> Callable:
    """Fonksiyon tabanlı görünümler için rol dekoratörü."""

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            user = request.user
            if not user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())
            if not user.is_superuser and not (set(role_codes) & getattr(user, "role_codes", set())):
                _deny(
                    request,
                    f"Yetersiz rol: {view_func.__name__} — gereken: {', '.join(role_codes)}",
                )
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_approval_or_permission(
    user: Any,
    *,
    action: str,
    permission: str | None = None,
) -> bool:
    """İşlemin doğrudan yapılıp yapılamayacağını bildirir.

    ``False`` dönerse çağıran kod bir ``ApprovalRequest`` oluşturmalı ve
    işlemi uygulamamalıdır.
    """
    if user.is_superuser:
        return True
    if permission and user.has_perm(permission) and user.can_approve(action):
        return True
    return user.can_approve(action)
