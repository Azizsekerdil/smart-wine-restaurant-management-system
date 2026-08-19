"""Yapay zekâ REST API'si.

GÜVENLİK: Hiçbir uç nokta API anahtarı döndürmez. Anahtarlar yalnızca
kısaltılmış (``sk-a…9f2c``) biçimde gösterilir.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.aiservices import registry, services
from apps.aiservices.models import (
    AIBudget,
    AICallLog,
    AIConversation,
    AIFeature,
    AIMessage,
    AIQualityFeedback,
    AISuggestion,
    ProviderPricing,
)


class AIMessageSerializer(serializers.ModelSerializer):
    was_masked = serializers.BooleanField(read_only=True)

    class Meta:
        model = AIMessage
        fields = [
            "id",
            "conversation",
            "role",
            "content",
            "masked_content",
            "masking_summary",
            "was_masked",
            "sequence",
            "created_at",
        ]


class AIConversationSerializer(serializers.ModelSerializer):
    messages = AIMessageSerializer(many=True, read_only=True)
    total_tokens = serializers.IntegerField(read_only=True)

    class Meta:
        model = AIConversation
        fields = [
            "id",
            "title",
            "feature",
            "user",
            "provider",
            "model",
            "is_archived",
            "created_at",
            "updated_at",
            "messages",
            "total_tokens",
        ]
        read_only_fields = ["user", "provider", "model"]


class AICallLogSerializer(serializers.ModelSerializer):
    total_tokens = serializers.IntegerField(read_only=True)

    class Meta:
        model = AICallLog
        fields = "__all__"


class AISuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AISuggestion
        fields = [
            "id",
            "kind",
            "title",
            "summary",
            "payload",
            "previous_state",
            "target_type",
            "target_id",
            "status",
            "confidence",
            "created_for",
            "reviewed_by",
            "reviewed_at",
            "applied_at",
            "review_note",
            "created_at",
        ]
        read_only_fields = ["status", "reviewed_by", "reviewed_at", "applied_at"]


class ProviderPricingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderPricing
        fields = "__all__"


class AIBudgetSerializer(serializers.ModelSerializer):
    usage_percent = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    is_exceeded = serializers.BooleanField(read_only=True)

    class Meta:
        model = AIBudget
        fields = "__all__"


class QualityFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIQualityFeedback
        fields = ["id", "call_log", "message", "rating", "issue_tags", "comment"]


# ---------------------------------------------------------------------------
# Sağlayıcı uç noktaları
# ---------------------------------------------------------------------------
class ProviderListView(APIView):
    """Yapılandırılmış sağlayıcılar ve sağlık durumları."""

    def get(self, request: Request) -> Response:
        ai_settings = settings.AI_SETTINGS
        payload = []
        for code in registry.available_provider_codes():
            config = ai_settings["PROVIDERS"][code]
            try:
                provider = registry.get_provider(code)
                has_key = provider.has_api_key
                redacted = provider.redacted_api_key
            except Exception:
                has_key = False
                redacted = ""
            payload.append(
                {
                    "code": code,
                    "label": registry.PROVIDER_LABELS.get(code, code),
                    "base_url": config.get("base_url", ""),
                    "configured_model": config.get("model", "") or "(otomatik seçilecek)",
                    "timeout": config.get("timeout"),
                    "is_local": config.get("is_local", False),
                    "api_key_configured": has_key,
                    "api_key_preview": redacted,
                    "is_default": code == ai_settings.get("DEFAULT_PROVIDER"),
                }
            )
        return Response(
            {
                "providers": payload,
                "default_provider": ai_settings.get("DEFAULT_PROVIDER"),
                "prefer_local": ai_settings.get("PREFER_LOCAL"),
                "local_only": ai_settings.get("LOCAL_ONLY"),
                "privacy_mode": ai_settings.get("PRIVACY_MODE"),
                "fallback_chain": registry.build_fallback_chain(),
            }
        )


class ProviderHealthView(APIView):
    """Tüm sağlayıcıların canlı sağlık kontrolü."""

    def get(self, request: Request) -> Response:
        report = registry.health_report()
        return Response(
            [
                {
                    "provider": health.provider,
                    "label": registry.PROVIDER_LABELS.get(health.provider, health.provider),
                    "reachable": health.reachable,
                    "status_label": health.status_label,
                    "badge_class": health.badge_class,
                    "models_available": health.models_available,
                    "default_model": health.default_model,
                    "latency_ms": health.latency_ms,
                    "message": health.message,
                    "is_local": health.is_local,
                    "api_key_configured": health.api_key_configured,
                }
                for health in report
            ]
        )


class ProviderModelsView(APIView):
    """Bir sağlayıcının canlı model listesi.

    Model adları koda gömülmez; her zaman sağlayıcıdan okunur.
    """

    def get(self, request: Request, code: str) -> Response:
        try:
            provider = registry.get_provider(code)
        except registry.UnknownProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        try:
            models = provider.list_models()
        except Exception as exc:
            # `exc` blok bitiminde silinir; lambda ile kapatmak kirilgan olurdu.
            _user_message = getattr(exc, "user_message", None)
            message = _user_message() if callable(_user_message) else str(exc)
            return Response(
                {"detail": message, "provider": code},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "provider": code,
                "count": len(models),
                "models": [
                    {
                        "id": model.id,
                        "display_name": model.display_name,
                        "context_length": model.context_length,
                        "supports_vision": model.supports_vision,
                        "is_loaded": model.is_loaded,
                    }
                    for model in models
                ],
            }
        )


class AskView(APIView):
    """Yapay zekâya soru sorar (maskeleme + yedekleme zinciriyle)."""

    def post(self, request: Request) -> Response:
        prompt = (request.data.get("prompt") or "").strip()
        if not prompt:
            return Response(
                {"detail": "'prompt' alanı zorunludur."}, status=status.HTTP_400_BAD_REQUEST
            )

        feature = request.data.get("feature", AIFeature.SOMMELIER)
        provider_code = request.data.get("provider", "")

        is_cloud = provider_code and not settings.AI_SETTINGS["PROVIDERS"].get(
            provider_code, {}
        ).get("is_local")
        may_use_cloud = (
            request.user.has_perm("aiservices.can_use_cloud_ai") or request.user.is_superuser
        )
        if is_cloud and not may_use_cloud:
            return Response(
                {"detail": "Bulut yapay zekâ kullanma yetkiniz yok."},
                status=status.HTTP_403_FORBIDDEN,
            )

        conversation = None
        conversation_id = request.data.get("conversation")
        if conversation_id:
            conversation = AIConversation.objects.filter(
                pk=conversation_id, user=request.user
            ).first()

        try:
            result = services.ask(
                user=request.user,
                feature=feature,
                prompt=prompt,
                provider_code=provider_code,
                model=request.data.get("model", ""),
                temperature=float(request.data.get("temperature", 0.4)),
                max_tokens=int(request.data.get("max_tokens", 1024)),
                conversation=conversation,
                allow_cloud=bool(request.data.get("allow_cloud", True)),
            )
        except services.AIUnavailableError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            # `exc` blok bitiminde silinir; lambda ile kapatmak kirilgan olurdu.
            _user_message = getattr(exc, "user_message", None)
            message = _user_message() if callable(_user_message) else str(exc)
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "text": result.text,
                "provider": result.response.provider,
                "model": result.response.model,
                "is_mock": result.is_mock,
                "used_fallback": result.used_fallback,
                "attempted_providers": result.attempted_providers,
                "privacy_notice": result.privacy_notice,
                "sent_to_provider": result.masking.text if result.masking else None,
                "usage": {
                    "prompt_tokens": result.response.usage.prompt_tokens,
                    "completion_tokens": result.response.usage.completion_tokens,
                    "total_tokens": result.response.usage.total_tokens,
                },
                "latency_ms": result.response.latency_ms,
                "call_log_id": result.call_log.pk,
            }
        )


class PairingSuggestionView(APIView):
    """Yemek için kavdaki şaraplardan eşleştirme önerir."""

    def post(self, request: Request) -> Response:
        from apps.cellar.models import Wine

        dish = (request.data.get("dish") or "").strip()
        if not dish:
            return Response(
                {"detail": "'dish' alanı zorunludur."}, status=status.HTTP_400_BAD_REQUEST
            )

        wines = list(
            Wine.objects.filter(
                is_deleted=False, is_active=True, is_on_wine_list=True
            ).select_related("producer")[:60]
        )
        available = [
            f"{wine.producer.name} {wine.name} {wine.display_vintage} "
            f"({wine.get_wine_type_display()})"
            for wine in wines
            if wine.bottles_on_hand > 0 or wine.glasses_available > 0
        ]
        if not available:
            return Response(
                {
                    "detail": "Kavda stokta şarap bulunamadı; öneri üretilemedi.",
                    "wines_considered": 0,
                },
                status=status.HTTP_409_CONFLICT,
            )

        try:
            result = services.suggest_wine_pairing(
                user=request.user,
                dish_description=dish,
                available_wines=available,
                language=request.data.get("language", "tr"),
                provider_code=request.data.get("provider", ""),
            )
        except services.AIUnavailableError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        from apps.cellar.models import RESPONSIBLE_CONSUMPTION_NOTICE_TR

        return Response(
            {
                "suggestion": result.text,
                "provider": result.response.provider,
                "model": result.response.model,
                "is_mock": result.is_mock,
                "wines_considered": len(available),
                "privacy_notice": result.privacy_notice,
                "responsible_consumption_notice": RESPONSIBLE_CONSUMPTION_NOTICE_TR,
                "note": (
                    "Bu bir öneridir. Sommelier onayı olmadan menüye veya "
                    "eşleştirme kaydına işlenmez."
                ),
            }
        )


# ---------------------------------------------------------------------------
# Görünüm kümeleri
# ---------------------------------------------------------------------------
class AIConversationViewSet(viewsets.ModelViewSet):
    serializer_class = AIConversationSerializer

    def get_queryset(self):  # type: ignore[override]
        return AIConversation.objects.filter(user=self.request.user).prefetch_related("messages")

    def perform_create(self, serializer: Any) -> None:
        serializer.save(user=self.request.user, created_by=self.request.user)


class AICallLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AICallLog.objects.select_related("user", "conversation")
    serializer_class = AICallLogSerializer


class AISuggestionViewSet(viewsets.ModelViewSet):
    queryset = AISuggestion.objects.select_related("created_for", "reviewed_by")
    serializer_class = AISuggestionSerializer

    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str | None = None) -> Response:
        """Öneriyi onaylar. Uygulama ayrı bir adımdır."""
        if not (
            request.user.has_perm("aiservices.can_apply_ai_suggestion") or request.user.is_superuser
        ):
            return Response({"detail": "Yetkiniz yok."}, status=status.HTTP_403_FORBIDDEN)

        from django.utils import timezone

        suggestion = self.get_object()
        if suggestion.status != AISuggestion.Status.PENDING:
            return Response(
                {"detail": f"Öneri {suggestion.get_status_display()} durumunda."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        suggestion.status = AISuggestion.Status.APPROVED
        suggestion.reviewed_by = request.user
        suggestion.reviewed_at = timezone.now()
        suggestion.review_note = request.data.get("note", "")
        suggestion.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"]
        )

        from apps.core.audit import record
        from apps.core.models import AuditAction, AuditSeverity

        record(
            action=AuditAction.AI_APPLY,
            obj=suggestion,
            message=f"Yapay zekâ önerisi onaylandı: {suggestion.title}",
            severity=AuditSeverity.NOTICE,
            request=request,
        )
        return Response(AISuggestionSerializer(suggestion).data)

    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk: str | None = None) -> Response:
        """Öneriyi reddeder."""
        from django.utils import timezone

        suggestion = self.get_object()
        suggestion.status = AISuggestion.Status.REJECTED
        suggestion.reviewed_by = request.user
        suggestion.reviewed_at = timezone.now()
        suggestion.review_note = request.data.get("note", "")
        suggestion.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"]
        )
        return Response(AISuggestionSerializer(suggestion).data)


class ProviderPricingViewSet(viewsets.ModelViewSet):
    queryset = ProviderPricing.objects.all()
    serializer_class = ProviderPricingSerializer


class AIBudgetViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AIBudget.objects.all()
    serializer_class = AIBudgetSerializer


class QualityFeedbackViewSet(viewsets.ModelViewSet):
    queryset = AIQualityFeedback.objects.select_related("call_log")
    serializer_class = QualityFeedbackSerializer

    def perform_create(self, serializer: Any) -> None:
        serializer.save(submitted_by=self.request.user)
