"""AI Development Studio görünümleri.

ERİŞİM: Yalnızca ``sysadmin`` / ``owner`` rolleri veya süper kullanıcı.
Modül üretim modunda varsayılan olarak kapalıdır.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.utils.translation import gettext as _
from django.views.generic import DetailView, ListView, TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.devstudio import policy
from apps.devstudio.models import DevAction, DevAuditEntry, DevSession


class _StudioAccessMixin(AuditedPermissionMixin):
    """Stüdyo erişim denetimi: hem rol hem de etkinleştirme kontrolü."""

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if not getattr(request.user, "can_use_devstudio", False):
            from apps.core.audit import record_permission_denied

            record_permission_denied(
                request,
                f"AI Development Studio erişimi reddedildi: {request.user.username}",
            )
            raise PermissionDenied(
                _(
                    "AI Development Studio yalnızca sistem yöneticisi ve işletme "
                    "sahibi rollerine açıktır."
                )
            )

        if not policy.studio_enabled():
            raise PermissionDenied(
                _(
                    "AI Development Studio bu ortamda kapalıdır. Üretim modunda "
                    "varsayılan olarak devre dışıdır (WINEHOUSE_DEVSTUDIO_ENABLED)."
                )
            )
        return super().dispatch(request, *args, **kwargs)


class StudioHomeView(_StudioAccessMixin, ListView):
    """Geliştirme oturumları."""

    template_name = "devstudio/home.html"
    context_object_name = "sessions"
    paginate_by = 25

    def get_queryset(self) -> QuerySet[DevSession]:
        return DevSession.objects.select_related("requested_by", "approved_by").prefetch_related(
            "actions"
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["policy"] = policy.policy_summary()
        context["commands_allowed"] = policy.commands_allowed()
        context["safety_notes"] = [
            _("Yapay zekâ komutları doğrudan çalıştıramaz; yalnızca öneri üretir."),
            _("Her öneri politika motorundan geçirilir; yasak desenler reddedilir."),
            _("Yazma işlemi yalnızca yapılandırılmış çalışma alanında yapılabilir."),
            _("Her değişiklik ayrı bir Git dalında yapılır."),
            _("Testler geçmeden ve kullanıcı onayı olmadan ana dala birleştirilmez."),
            _("API anahtarları terminal çıktılarında otomatik maskelenir."),
            _("Tüm eylemler değiştirilemez denetim kaydına yazılır."),
        ]
        return context


class PolicyView(_StudioAccessMixin, TemplateView):
    """Politika motorunun kural dökümü ve deneme aracı."""

    template_name = "devstudio/policy.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["policy"] = policy.policy_summary()
        context["forbidden_patterns"] = [name for name, _p in policy.FORBIDDEN_PATTERNS]
        return context

    def post(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        """Bir komutun politikadan geçip geçmeyeceğini sınar (çalıştırmaz)."""
        context = self.get_context_data(**kwargs)
        candidate = (request.POST.get("command") or "").strip()
        target_path = (request.POST.get("path") or "").strip()

        if candidate:
            context["command_result"] = policy.evaluate_command(candidate)
            context["tested_command"] = candidate
        if target_path:
            context["path_result"] = policy.evaluate_file_write(target_path)
            context["tested_path"] = target_path

        context["dry_run_note"] = _(
            "Bu araç yalnızca değerlendirme yapar; hiçbir komut çalıştırılmaz "
            "ve hiçbir dosya değiştirilmez."
        )
        return self.render_to_response(context)


class SessionDetailView(_StudioAccessMixin, DetailView):
    """Oturum ayrıntısı: plan, eylemler, diff, test sonuçları."""

    template_name = "devstudio/session_detail.html"
    context_object_name = "session"

    def get_queryset(self) -> QuerySet[DevSession]:
        return DevSession.objects.select_related("requested_by", "approved_by")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        session: DevSession = self.object
        context["actions"] = session.actions.order_by("sequence")
        context["blocked_actions"] = session.actions.filter(status=DevAction.Status.BLOCKED)
        context["merge_blockers"] = session.merge_blockers
        context["can_merge"] = session.can_merge
        context["audit_entries"] = session.audit_entries.order_by("-timestamp")[:50]
        return context


class StudioAuditView(_StudioAccessMixin, ListView):
    """Stüdyo denetim kaydı."""

    template_name = "devstudio/audit.html"
    context_object_name = "entries"
    paginate_by = 100

    def get_queryset(self) -> QuerySet[DevAuditEntry]:
        queryset = DevAuditEntry.objects.select_related("actor", "session", "action")
        if self.request.GET.get("security") == "1":
            queryset = queryset.filter(is_security_relevant=True)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["security_only"] = self.request.GET.get("security") == "1"
        context["workspace"] = str(settings.DEVSTUDIO.get("WORKSPACE", ""))
        return context
