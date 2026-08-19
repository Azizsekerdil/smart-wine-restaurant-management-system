"""Yapay zekâ görünümleri."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views.generic import ListView, TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.aiservices import registry, services
from apps.aiservices.models import AICallLog, AIFeature, AISuggestion


class AIConsoleView(AuditedPermissionMixin, TemplateView):
    """Yapay zekâ konsolu: soru sor, yanıtı ve gizlilik bildirimini gör."""

    template_name = "aiservices/console.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        ai_settings = settings.AI_SETTINGS
        context["features"] = AIFeature.choices
        context["providers"] = [
            {
                "code": code,
                "label": registry.PROVIDER_LABELS.get(code, code),
                "is_local": ai_settings["PROVIDERS"][code].get("is_local", False),
            }
            for code in registry.available_provider_codes()
        ]
        context["default_provider"] = ai_settings.get("DEFAULT_PROVIDER")
        context["privacy_mode"] = ai_settings.get("PRIVACY_MODE")
        context["local_only"] = ai_settings.get("LOCAL_ONLY")
        context["fallback_chain"] = registry.build_fallback_chain()
        context["can_use_cloud"] = self.request.user.has_perm("aiservices.can_use_cloud_ai")
        context["recent_calls"] = AICallLog.objects.filter(user=self.request.user)[:10]
        return context

    def post(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        """Soruyu sağlayıcıya iletir."""
        prompt = (request.POST.get("prompt") or "").strip()
        context = self.get_context_data(**kwargs)
        context["prompt"] = prompt

        if not prompt:
            messages.error(request, _("Lütfen bir soru yazın."))
            return self.render_to_response(context)

        provider_code = request.POST.get("provider", "")
        is_cloud = provider_code and not settings.AI_SETTINGS["PROVIDERS"].get(
            provider_code, {}
        ).get("is_local")
        may_use_cloud = (
            request.user.has_perm("aiservices.can_use_cloud_ai") or request.user.is_superuser
        )
        if is_cloud and not may_use_cloud:
            messages.error(request, _("Bulut yapay zekâ kullanma yetkiniz yok."))
            return self.render_to_response(context)

        try:
            result = services.ask(
                user=request.user,
                feature=request.POST.get("feature", AIFeature.SOMMELIER),
                prompt=prompt,
                provider_code=provider_code,
            )
        except services.AIUnavailableError as exc:
            messages.error(request, str(exc))
            return self.render_to_response(context)

        context["result"] = result
        if result.is_mock:
            messages.warning(
                request,
                _(
                    "Yanıt Mock sağlayıcıdan geldi; gerçek bir dil modeli "
                    "çalıştırılmadı. Ayarlar ekranından LM Studio'yu başlatın."
                ),
            )
        elif result.used_fallback:
            messages.info(
                request,
                _("Birincil sağlayıcı yanıt vermedi; yedek sağlayıcı kullanıldı: %(p)s")
                % {"p": result.response.provider},
            )
        return self.render_to_response(context)


class ProviderSettingsView(AuditedPermissionMixin, TemplateView):
    """Sağlayıcı ayarları ve sağlık durumu."""

    template_name = "aiservices/providers.html"
    required_permissions = ["aiservices.can_configure_ai"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        ai_settings = settings.AI_SETTINGS

        rows = []
        for code in registry.available_provider_codes():
            config = ai_settings["PROVIDERS"][code]
            try:
                provider = registry.get_provider(code)
                api_key_configured = provider.has_api_key
                api_key_preview = provider.redacted_api_key
            except Exception:
                api_key_configured = False
                api_key_preview = ""
            rows.append(
                {
                    "code": code,
                    "label": registry.PROVIDER_LABELS.get(code, code),
                    "base_url": config.get("base_url", ""),
                    "model": config.get("model") or _("(otomatik seçilecek)"),
                    "timeout": config.get("timeout"),
                    "is_local": config.get("is_local", False),
                    "api_key_env": config.get("api_key_env", ""),
                    "api_key_configured": api_key_configured,
                    "api_key_preview": api_key_preview,
                }
            )

        context["providers"] = rows
        context["settings_summary"] = {
            "default_provider": ai_settings.get("DEFAULT_PROVIDER"),
            "prefer_local": ai_settings.get("PREFER_LOCAL"),
            "local_only": ai_settings.get("LOCAL_ONLY"),
            "privacy_mode": ai_settings.get("PRIVACY_MODE"),
            "monthly_limit_usd": ai_settings.get("MONTHLY_COST_LIMIT_USD"),
            "fallback_chain": registry.build_fallback_chain(),
        }
        context["budget"] = services.current_budget()
        context["key_entry_note"] = _(
            "API anahtarları bu ekrandan girilmez. Güvenlik gereği anahtarlar "
            "yalnızca .env dosyasında veya işletim sistemi kimlik deposunda "
            "tutulur; uygulama bunları yalnızca okur ve asla kaydetmez."
        )
        return context


def provider_health_check(request: Any) -> Any:
    """Tüm sağlayıcılara canlı sağlık kontrolü yapar."""
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if not (request.user.has_perm("aiservices.can_configure_ai") or request.user.is_superuser):
        messages.error(request, _("Bu işlem için yetkiniz yok."))
        return redirect("aiservices:console")

    report = registry.health_report()
    for health in report:
        label = registry.PROVIDER_LABELS.get(health.provider, health.provider)
        if health.reachable:
            messages.success(
                request,
                f"{label}: {health.message} ({health.models_available} model, "
                f"{health.latency_ms} ms)",
            )
        else:
            messages.warning(request, f"{label}: {health.message}")
    return redirect("aiservices:providers")


class SommelierAssistantView(AuditedPermissionMixin, TemplateView):
    """Sommelier asistanı: yemek–şarap eşleştirmesi."""

    template_name = "aiservices/sommelier.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        from apps.catalog.models import MenuItem
        from apps.cellar.models import RESPONSIBLE_CONSUMPTION_NOTICE_TR

        context = super().get_context_data(**kwargs)
        context["dishes"] = MenuItem.objects.filter(
            is_deleted=False, is_active=True, item_type__in=["food", "set_menu"]
        ).order_by("name_tr")[:200]
        context["responsible_notice"] = RESPONSIBLE_CONSUMPTION_NOTICE_TR
        return context

    def post(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        from apps.cellar.models import Wine

        context = self.get_context_data(**kwargs)
        dish = (request.POST.get("dish") or "").strip()
        context["dish"] = dish

        if not dish:
            messages.error(request, _("Lütfen bir yemek tarif edin veya seçin."))
            return self.render_to_response(context)

        wines = [
            wine
            for wine in Wine.objects.filter(
                is_deleted=False, is_active=True, is_on_wine_list=True
            ).select_related("producer")[:80]
            if wine.bottles_on_hand > 0 or wine.glasses_available > 0
        ]
        if not wines:
            messages.warning(request, _("Kavda stokta şarap bulunamadı; öneri üretilemedi."))
            return self.render_to_response(context)

        available = [
            f"{wine.producer.name} {wine.name} {wine.display_vintage} "
            f"({wine.get_wine_type_display()})"
            for wine in wines
        ]

        try:
            result = services.suggest_wine_pairing(
                user=request.user,
                dish_description=dish,
                available_wines=available,
                language=request.LANGUAGE_CODE if hasattr(request, "LANGUAGE_CODE") else "tr",
            )
        except services.AIUnavailableError as exc:
            messages.error(request, str(exc))
            return self.render_to_response(context)

        context["result"] = result
        context["wines_considered"] = len(available)
        if result.is_mock:
            messages.warning(
                request, _("Öneri Mock sağlayıcıdan geldi; gerçek model çalıştırılmadı.")
            )
        return self.render_to_response(context)


class SuggestionQueueView(AuditedPermissionMixin, ListView):
    """İnsan onayı bekleyen yapay zekâ önerileri."""

    template_name = "aiservices/suggestions.html"
    context_object_name = "suggestions"
    paginate_by = 50

    def get_queryset(self) -> Any:
        queryset = AISuggestion.objects.select_related("created_for", "reviewed_by")
        status_filter = self.request.GET.get("status", AISuggestion.Status.PENDING)
        if status_filter != "all":
            queryset = queryset.filter(status=status_filter)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["status_choices"] = AISuggestion.Status.choices
        context["selected_status"] = self.request.GET.get("status", AISuggestion.Status.PENDING)
        context["can_apply"] = self.request.user.has_perm("aiservices.can_apply_ai_suggestion")
        context["policy_note"] = _(
            "Yapay zekâ veritabanında doğrudan değişiklik yapmaz. Her öneri "
            "burada listelenir ve yalnızca açık onaydan sonra uygulanır."
        )
        return context


class CostDashboardView(AuditedPermissionMixin, TemplateView):
    """Yapay zekâ maliyet ve belirteç kullanımı panosu."""

    template_name = "aiservices/costs.html"
    required_permissions = ["aiservices.can_view_ai_costs"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        budget = services.current_budget()
        context["budget"] = budget

        by_provider = (
            AICallLog.objects.values("provider", "is_local_provider")
            .annotate(
                calls=Count("id"),
                tokens=Sum("prompt_tokens") + Sum("completion_tokens"),
                cost=Sum("estimated_cost_usd"),
            )
            .order_by("-cost")
        )
        context["by_provider"] = by_provider

        by_feature = (
            AICallLog.objects.values("feature")
            .annotate(
                calls=Count("id"),
                tokens=Sum("prompt_tokens") + Sum("completion_tokens"),
                cost=Sum("estimated_cost_usd"),
            )
            .order_by("-calls")
        )
        context["by_feature"] = by_feature
        context["feature_labels"] = dict(AIFeature.choices)

        outcomes = (
            AICallLog.objects.values("outcome").annotate(count=Count("id")).order_by("-count")
        )
        context["outcomes"] = outcomes
        context["outcome_labels"] = dict(AICallLog.Outcome.choices)

        total_calls = AICallLog.objects.count()
        failed = AICallLog.objects.filter(outcome=AICallLog.Outcome.FAILED).count()
        context["total_calls"] = total_calls
        context["failure_rate"] = (
            (Decimal(failed) / Decimal(total_calls) * 100).quantize(Decimal("0.01"))
            if total_calls
            else Decimal("0.00")
        )
        context["pricing_note"] = _(
            "Maliyet yalnızca fiyatı elle tanımlanmış modeller için hesaplanır. "
            "Uygulama hiçbir sağlayıcının fiyatını varsaymaz."
        )
        return context
