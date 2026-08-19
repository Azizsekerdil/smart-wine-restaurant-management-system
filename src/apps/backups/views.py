"""Yedekleme ve geri yükleme görünümleri."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.generic import ListView, TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.backups import services
from apps.backups.models import BackupRecord, BackupSchedule, RestoreRecord


class BackupListView(AuditedPermissionMixin, ListView):
    """Yedek kayıtları."""

    template_name = "backups/backup_list.html"
    context_object_name = "backups"
    paginate_by = 50
    required_permissions = ["backups.view_backuprecord"]

    def get_queryset(self) -> QuerySet[BackupRecord]:
        return BackupRecord.objects.select_related("created_by")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["backup_dir"] = str(settings.BACKUP_DIR)
        context["encryption_enabled"] = settings.BACKUP_ENCRYPTION
        context["encryption_key_present"] = bool(settings.FIELD_ENCRYPTION_KEY)
        context["retention_days"] = settings.BACKUP_RETENTION_DAYS
        context["schedules"] = BackupSchedule.objects.filter(is_active=True)
        context["can_backup"] = self.request.user.has_perm("backups.can_run_backup")
        context["can_restore"] = self.request.user.has_perm("backups.can_restore_backup")
        context["restores"] = RestoreRecord.objects.select_related(
            "backup", "requested_by"
        ).order_by("-created_at")[:10]
        return context


def create_backup_view(request: Any) -> Any:
    """Arayüzden yedek alır."""
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.method != "POST":
        return redirect("backups:backup-list")
    if not (request.user.has_perm("backups.can_run_backup") or request.user.is_superuser):
        messages.error(request, _("Yedek alma yetkiniz yok."))
        return redirect("backups:backup-list")

    destination = (request.POST.get("destination") or "").strip()
    encrypt = request.POST.get("encrypt") == "1"

    try:
        backup = services.create_backup(
            user=request.user,
            destination=Path(destination) if destination else None,
            encrypt=encrypt,
            notes=request.POST.get("notes", ""),
        )
    except services.BackupError as exc:
        messages.error(request, str(exc))
        return redirect("backups:backup-list")

    verification = services.verify_backup(backup=backup, user=request.user)
    if verification.is_valid:
        messages.success(
            request,
            _("Yedek alındı ve doğrulandı: %(name)s (%(size)s MB). %(detail)s")
            % {
                "name": backup.file_name,
                "size": backup.size_mb,
                "detail": verification.message,
            },
        )
    else:
        messages.warning(
            request,
            _("Yedek alındı ancak doğrulama başarısız: %(msg)s") % {"msg": verification.message},
        )
    return redirect("backups:backup-list")


def verify_backup_view(request: Any, pk: int) -> Any:
    """Var olan bir yedeği doğrular."""
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.method != "POST":
        return redirect("backups:backup-list")

    backup = get_object_or_404(BackupRecord, pk=pk)
    result = services.verify_backup(backup=backup, user=request.user)

    if result.is_valid:
        messages.success(request, result.message)
    else:
        messages.error(request, result.message)
    return redirect("backups:backup-list")


class RestoreView(AuditedPermissionMixin, TemplateView):
    """Geri yükleme sihirbazı."""

    template_name = "backups/restore.html"
    required_permissions = ["backups.can_restore_backup"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["backups"] = BackupRecord.objects.filter(
            status__in=[BackupRecord.Status.SUCCESS, BackupRecord.Status.VERIFIED]
        ).order_by("-started_at")[:50]
        context["restores"] = RestoreRecord.objects.select_related(
            "backup", "approval", "requested_by"
        ).order_by("-created_at")[:20]
        context["target_choices"] = RestoreRecord.Target.choices
        context["safety_notes"] = [
            _("Geri yükleme ikinci onay gerektirir."),
            _("Yedek önce SHA-256 özetiyle doğrulanır; bozuksa işlem yapılmaz."),
            _("Canlı veritabanına yüklemeden önce otomatik güvenlik yedeği alınır."),
            _("Varsayılan hedef test veritabanıdır."),
        ]
        return context

    def post(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        """Geri yükleme talebi oluşturur (onay bekler)."""
        from django.utils import timezone

        from apps.accounts.models import ApprovalRequest

        backup = get_object_or_404(BackupRecord, pk=request.POST.get("backup"))
        target = request.POST.get("target", RestoreRecord.Target.TEST)

        approval = ApprovalRequest.objects.create(
            action="restore_backup",
            requested_by=request.user,
            reason=request.POST.get("reason", "") or "Yedekten geri yükleme talebi",
            payload={"backup_id": backup.pk, "target": target},
            object_type=backup._meta.label,
            object_id=str(backup.pk),
            expires_at=timezone.now() + timezone.timedelta(hours=24),
            created_by=request.user,
        )

        restore = RestoreRecord.objects.create(
            backup=backup,
            target=target,
            status=RestoreRecord.Status.PENDING,
            approval=approval,
            requested_by=request.user,
            created_by=request.user,
        )

        messages.info(
            request,
            _(
                "Geri yükleme talebi oluşturuldu (#%(id)s). Başka bir yetkilinin "
                "onaylaması gerekiyor; onaya kadar hiçbir veri değiştirilmez."
            )
            % {"id": restore.pk},
        )
        return redirect("backups:restore")
