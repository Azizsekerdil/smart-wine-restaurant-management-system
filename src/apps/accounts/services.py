"""Rol eşitleme ve kullanıcı yönetimi servisleri."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from fnmatch import fnmatch

from django.contrib.auth.models import Group, Permission
from django.db import transaction

from apps.accounts.roles import ROLES, RoleSpec

logger = logging.getLogger("winehouse.security")


@dataclass
class RoleSyncReport:
    """``sync_roles`` sonucunun özeti."""

    created_groups: list[str]
    updated_groups: list[str]
    unmatched_patterns: dict[str, list[str]]
    total_permissions: dict[str, int]

    def as_text(self) -> str:
        lines = [
            f"Oluşturulan rol: {len(self.created_groups)}",
            f"Güncellenen rol: {len(self.updated_groups)}",
        ]
        for code, count in sorted(self.total_permissions.items()):
            lines.append(f"  · {code}: {count} izin")
        if self.unmatched_patterns:
            lines.append("Eşleşmeyen izin desenleri (ilgili modül henüz yok):")
            for code, patterns in sorted(self.unmatched_patterns.items()):
                lines.append(f"  · {code}: {', '.join(patterns)}")
        return "\n".join(lines)


def _match_permissions(patterns: list[str]) -> tuple[set[Permission], list[str]]:
    """Desen listesini gerçek ``Permission`` nesnelerine çözer.

    Returns:
        (eşleşen izinler, hiçbir izinle eşleşmeyen desenler)
    """
    all_permissions = list(Permission.objects.select_related("content_type").all())
    index = [(f"{perm.content_type.app_label}.{perm.codename}", perm) for perm in all_permissions]

    matched: set[Permission] = set()
    unmatched: list[str] = []

    for pattern in patterns:
        hits = {perm for key, perm in index if fnmatch(key, pattern)}
        if hits:
            matched |= hits
        else:
            unmatched.append(pattern)
    return matched, unmatched


@transaction.atomic
def sync_roles(*, verbose: bool = False) -> RoleSyncReport:
    """Rol kataloğunu (``roles.ROLES``) veritabanındaki gruplarla eşitler.

    Bu işlem *idempotent*'tir: birden çok kez çalıştırılabilir. Var olan
    kullanıcı-rol atamaları korunur; yalnızca rolün izin kümesi güncellenir.
    """
    from apps.accounts.models import RoleProfile

    created: list[str] = []
    updated: list[str] = []
    unmatched_map: dict[str, list[str]] = {}
    totals: dict[str, int] = {}

    for spec in ROLES:
        group, was_created = Group.objects.get_or_create(name=spec.code)
        permissions, unmatched = _match_permissions(spec.permissions)

        group.permissions.set(permissions)
        totals[spec.code] = len(permissions)
        if unmatched:
            unmatched_map[spec.code] = unmatched

        RoleProfile.objects.update_or_create(
            group=group,
            defaults={
                "code": spec.code,
                "name_tr": spec.name_tr,
                "name_en": spec.name_en,
                "description": spec.description_tr,
                "level": spec.level,
                "is_system": True,
            },
        )

        (created if was_created else updated).append(spec.code)

    report = RoleSyncReport(
        created_groups=created,
        updated_groups=updated,
        unmatched_patterns=unmatched_map,
        total_permissions=totals,
    )
    if verbose:
        logger.info("Rol eşitleme tamamlandı:\n%s", report.as_text())
    return report


def assign_role(user, role_code: str, *, primary: bool = True, replace: bool = False) -> None:
    """Kullanıcıya rol atar.

    Args:
        user: Hedef kullanıcı.
        role_code: ``roles.ROLES`` içindeki rol kodu.
        primary: Rolü kullanıcının birincil rolü yapar.
        replace: True ise kullanıcının diğer tüm rolleri kaldırılır.
    """
    from apps.accounts.roles import ROLES_BY_CODE

    spec: RoleSpec | None = ROLES_BY_CODE.get(role_code)
    if spec is None:
        raise ValueError(f"Bilinmeyen rol kodu: {role_code}")

    group, _ = Group.objects.get_or_create(name=role_code)

    if replace:
        user.groups.clear()
    user.groups.add(group)

    fields: list[str] = []
    if primary:
        user.primary_role = role_code
        fields.append("primary_role")
    if spec.django_staff and not user.is_staff:
        user.is_staff = True
        fields.append("is_staff")
    if fields:
        user.save(update_fields=fields)


def remove_role(user, role_code: str) -> None:
    """Kullanıcıdan rolü kaldırır."""
    group = Group.objects.filter(name=role_code).first()
    if group:
        user.groups.remove(group)
    if user.primary_role == role_code:
        remaining = user.groups.values_list("name", flat=True).first() or ""
        user.primary_role = remaining
        user.save(update_fields=["primary_role"])


def create_user_with_role(
    *,
    username: str,
    password: str,
    role_code: str,
    display_name: str = "",
    email: str = "",
    is_superuser: bool = False,
) -> object:
    """Rolüyle birlikte kullanıcı oluşturur (kurulum sihirbazı kullanır).

    Parola, kaydedilmeden önce ``AUTH_PASSWORD_VALIDATORS`` politikasından
    geçirilir; zayıf bir parola sessizce kabul edilmez.

    Raises:
        django.core.exceptions.ValidationError: Parola politikayı
            karşılamıyorsa.
    """
    from django.contrib.auth.password_validation import validate_password
    from django.utils import timezone

    from apps.accounts.models import User

    user = User(
        username=username,
        email=email,
        display_name=display_name or username,
        is_superuser=is_superuser,
        is_staff=is_superuser,
        password_changed_at=timezone.now(),
    )
    validate_password(password, user)
    user.set_password(password)
    user.full_clean(exclude=["password"])
    user.save()
    assign_role(user, role_code, primary=True)
    return user
