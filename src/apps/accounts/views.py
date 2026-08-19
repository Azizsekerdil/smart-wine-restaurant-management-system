"""Hesap görünümleri: giriş, PIN girişi, kullanıcı yönetimi, onay kuyruğu."""

from __future__ import annotations

from typing import Any, cast

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from apps.accounts.forms import (
    ApprovalDecisionForm,
    PinLoginForm,
    UserForm,
    WineHouseAuthenticationForm,
)
from apps.accounts.models import ApprovalRequest, LoginAttempt, RoleProfile, User
from apps.accounts.permissions import AuditedPermissionMixin
from apps.core.audit import record
from apps.core.middleware import AUTH_SCOPE_SESSION_KEY
from apps.core.models import AuditAction, AuditSeverity


class WineHouseLoginView(LoginView):
    """Giriş ekranı."""

    template_name = "accounts/login.html"
    form_class = WineHouseAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form: Any) -> Any:
        pending_user = form.get_user()
        remote_addr = self.request.META.get("REMOTE_ADDR", "")
        if getattr(pending_user, "must_change_password", False) and remote_addr not in {
            "127.0.0.1",
            "::1",
        }:
            form.add_error(None, _("İlk giriş yalnızca bu cihazdan yapılabilir."))
            return self.form_invalid(form)
        self.request._winehouse_login_method = "password"
        response = super().form_valid(form)
        user = self.request.user
        # Parola oturumu tam kapsamlıdır (PIN oturumundan ayrılır).
        self.request.session[AUTH_SCOPE_SESSION_KEY] = "password"
        # Kullanıcı dil tercihini oturuma uygula
        if getattr(user, "preferred_language", None):
            self.request.session["django_language"] = user.preferred_language
        if getattr(user, "must_change_password", False):
            messages.warning(
                self.request,
                _("Güvenlik gereği parolanızı değiştirmeniz gerekiyor."),
            )
        return response


class WineHouseLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class WineHousePasswordChangeView(PasswordChangeView):
    """Parola değiştirme — zorunlu değişim bayrağını burada düşürür.

    ``must_change_password`` yalnızca kullanıcı parolasını **gerçekten**
    değiştirdiğinde temizlenir. Yöneticinin parola sıfırlaması bayrağı
    kendiliğinden kaldırmaz; sıfırlanan hesap yine ilk girişte parola
    değiştirmek zorundadır.
    """

    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password-change-done")

    def form_valid(self, form: Any) -> Any:
        response = super().form_valid(form)
        # PasswordChangeView oturum açmayı zorunlu kılar; burada kullanıcı
        # her zaman gerçek bir User'dır (AnonymousUser olamaz).
        user = cast(User, self.request.user)
        user.must_change_password = False
        user.password_changed_at = timezone.now()
        user.save(update_fields=["must_change_password", "password_changed_at"])
        record(
            action=AuditAction.UPDATE,
            message=f"{user.get_username()} parolasını değiştirdi.",
            request=self.request,
            actor=user,
        )
        return response


def pin_login(request: Any) -> Any:
    """POS terminalinde personel kodu + PIN ile hızlı giriş.

    Parola girişinden ayrı tutulur. Açılan oturum ``pin`` kapsamıyla
    işaretlenir ve :class:`apps.core.middleware.PinSessionScopeMiddleware`
    tarafından salon / mutfak / bar ekranlarıyla sınırlandırılır; yönetim
    yüzeyi (kullanıcı ve rol yönetimi, denetim kaydı, onay kuyruğu, raporlar,
    İK, CRM, yedekleme, yapay zekâ ayarları, Django yönetim paneli) PIN
    oturumuna kapalıdır.
    """
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    form = PinLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["employee_code"]
        pin = form.cleaned_data["pin"]
        user = User.objects.filter(employee_code__iexact=code, is_active=True).first()

        if user is None or user.is_locked or not user.check_pin(pin):
            LoginAttempt.objects.create(
                username=code[:150],
                successful=False,
                method="pin",
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            )
            if user is not None:
                user.register_failed_login()
            record(
                action=AuditAction.LOGIN_FAILED,
                message=f"Başarısız PIN girişi: personel kodu={code}",
                severity=AuditSeverity.WARNING,
                success=False,
                request=request,
            )
            messages.error(request, _("Personel kodu veya PIN hatalı."))
        else:
            request._winehouse_login_method = "pin"
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            # Oturumu PIN kapsamıyla işaretle: yönetim yüzeyi kapalı kalır.
            request.session[AUTH_SCOPE_SESSION_KEY] = "pin"
            if user.preferred_language:
                request.session["django_language"] = user.preferred_language
            return redirect("core:dashboard")

    return render(request, "accounts/pin_login.html", {"form": form})


class ProfileView(AuditedPermissionMixin, TemplateView):
    """Kullanıcının kendi profili."""

    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["profile_user"] = user
        context["role_profile"] = RoleProfile.objects.filter(code=user.primary_role).first()
        context["recent_logins"] = LoginAttempt.objects.filter(username=user.username).order_by(
            "-timestamp"
        )[:10]
        context["pending_approvals"] = ApprovalRequest.objects.filter(
            requested_by=user, status=ApprovalRequest.Status.PENDING
        ).count()
        return context


class UserListView(AuditedPermissionMixin, ListView):
    """Kullanıcı listesi (İK / sistem yöneticisi)."""

    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 50
    required_permissions = ["accounts.view_user"]

    def get_queryset(self) -> QuerySet[User]:
        queryset = User.objects.all().order_by("primary_role", "username")
        query = self.request.GET.get("q", "").strip()
        if query:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(username__icontains=query)
                | Q(display_name__icontains=query)
                | Q(employee_code__icontains=query)
            )
        role = self.request.GET.get("role", "").strip()
        if role:
            queryset = queryset.filter(primary_role=role)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["roles"] = RoleProfile.objects.all().order_by("level", "name_tr")
        context["query"] = self.request.GET.get("q", "")
        context["selected_role"] = self.request.GET.get("role", "")
        return context


class UserCreateView(AuditedPermissionMixin, CreateView):
    """Yeni kullanıcı oluşturma."""

    model = User
    form_class = UserForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user-list")
    required_permissions = ["accounts.add_user"]

    def form_valid(self, form: UserForm) -> Any:
        response = super().form_valid(form)
        record(
            action=AuditAction.CREATE,
            obj=self.object,
            message=f"Kullanıcı oluşturuldu: {self.object.username} "
            f"(rol: {form.cleaned_data['role_code']})",
            request=self.request,
        )
        messages.success(self.request, _("Kullanıcı oluşturuldu."))
        return response


class UserUpdateView(AuditedPermissionMixin, UpdateView):
    """Kullanıcı düzenleme."""

    model = User
    form_class = UserForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user-list")
    required_permissions = ["accounts.change_user"]

    def form_valid(self, form: UserForm) -> Any:
        changed = {
            field: form.cleaned_data.get(field)
            for field in form.changed_data
            if field not in {"new_password", "new_pin"}
        }
        response = super().form_valid(form)
        record(
            action=AuditAction.UPDATE,
            obj=self.object,
            message=f"Kullanıcı güncellendi: {self.object.username}",
            changes=changed,
            request=self.request,
        )
        messages.success(self.request, _("Kullanıcı güncellendi."))
        return response


class RoleListView(AuditedPermissionMixin, ListView):
    """Rol kataloğu ve izin sayıları."""

    template_name = "accounts/role_list.html"
    context_object_name = "roles"
    required_permissions = ["auth.view_group"]

    def get_queryset(self) -> QuerySet[RoleProfile]:
        return RoleProfile.objects.select_related("group").order_by("level", "name_tr")


class RoleDetailView(AuditedPermissionMixin, DetailView):
    """Tek bir rolün izin dökümü."""

    template_name = "accounts/role_detail.html"
    context_object_name = "role"
    required_permissions = ["auth.view_group"]
    slug_field = "code"
    slug_url_kwarg = "code"

    def get_queryset(self) -> QuerySet[RoleProfile]:
        return RoleProfile.objects.select_related("group")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        role: RoleProfile = self.object
        permissions = role.group.permissions.select_related("content_type").order_by(
            "content_type__app_label", "codename"
        )
        grouped: dict[str, list[Any]] = {}
        for permission in permissions:
            grouped.setdefault(permission.content_type.app_label, []).append(permission)
        context["grouped_permissions"] = grouped
        context["permission_count"] = permissions.count()
        context["members"] = User.objects.filter(groups=role.group).order_by("username")
        return context


class ApprovalQueueView(AuditedPermissionMixin, ListView):
    """İkinci onay bekleyen kritik işlemler."""

    template_name = "accounts/approval_queue.html"
    context_object_name = "requests"
    paginate_by = 30

    def get_queryset(self) -> QuerySet[ApprovalRequest]:
        queryset = ApprovalRequest.objects.select_related("requested_by", "reviewed_by")
        status = self.request.GET.get("status", ApprovalRequest.Status.PENDING)
        if status != "all":
            queryset = queryset.filter(status=status)
        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["status_choices"] = ApprovalRequest.Status.choices
        context["selected_status"] = self.request.GET.get("status", ApprovalRequest.Status.PENDING)
        context["decision_form"] = ApprovalDecisionForm()
        return context


def approval_decide(request: Any, pk: int) -> Any:
    """Onay talebini onaylar veya reddeder.

    Görevler ayrılığı ve rol yetkisi ``ApprovalRequest`` modeli içinde
    zorunlu kılınır; bu görünüm yalnızca hataları kullanıcıya iletir.
    """
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.method != "POST":
        return redirect("accounts:approval-queue")

    approval = get_object_or_404(ApprovalRequest, pk=pk)
    form = ApprovalDecisionForm(request.POST)

    if not form.is_valid():
        messages.error(request, _("Geçersiz karar formu."))
        return redirect("accounts:approval-queue")

    decision = form.cleaned_data["decision"]
    note = form.cleaned_data["note"]

    try:
        if decision == "approve":
            approval.approve(request.user, note)
            messages.success(request, _("Talep onaylandı."))
        else:
            approval.reject(request.user, note)
            messages.info(request, _("Talep reddedildi."))
    except (PermissionError, ValueError) as exc:
        record(
            action=AuditAction.PERMISSION_DENIED,
            obj=approval,
            message=f"Onay kararı reddedildi: {exc}",
            severity=AuditSeverity.WARNING,
            success=False,
            request=request,
        )
        messages.error(request, str(exc))
        return redirect("accounts:approval-queue")

    record(
        action=AuditAction.SETTINGS if decision == "approve" else AuditAction.PERMISSION_DENIED,
        obj=approval,
        message=(
            f"Onay talebi '{approval.get_action_display()}' "
            f"{'onaylandı' if decision == 'approve' else 'reddedildi'} — "
            f"talep eden: {approval.requested_by.username}"
        ),
        severity=AuditSeverity.NOTICE,
        request=request,
    )
    return redirect("accounts:approval-queue")


class AuditLogView(AuditedPermissionMixin, ListView):
    """Denetim kaydı görüntüleyici."""

    template_name = "accounts/audit_log.html"
    context_object_name = "entries"
    paginate_by = 100
    required_permissions = ["core.view_auditlog"]

    def get_queryset(self) -> QuerySet[Any]:
        from apps.core.models import AuditLog

        queryset = AuditLog.objects.select_related("actor")
        action = self.request.GET.get("action", "").strip()
        if action:
            queryset = queryset.filter(action=action)
        actor = self.request.GET.get("actor", "").strip()
        if actor:
            queryset = queryset.filter(actor_label__icontains=actor)
        only_failed = self.request.GET.get("failed") == "1"
        if only_failed:
            queryset = queryset.filter(success=False)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["action_choices"] = AuditAction.choices
        context["filters"] = {
            "action": self.request.GET.get("action", ""),
            "actor": self.request.GET.get("actor", ""),
            "failed": self.request.GET.get("failed", ""),
        }
        context["now"] = timezone.now()
        return context
