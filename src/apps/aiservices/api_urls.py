"""Yapay zekâ API yönlendirmeleri."""

from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.aiservices import api

router = DefaultRouter()
router.register("conversations", api.AIConversationViewSet, basename="api-aiconversation")
router.register("calls", api.AICallLogViewSet, basename="api-aicall")
router.register("suggestions", api.AISuggestionViewSet, basename="api-aisuggestion")
router.register("pricing", api.ProviderPricingViewSet, basename="api-aipricing")
router.register("budgets", api.AIBudgetViewSet, basename="api-aibudget")
router.register("feedback", api.QualityFeedbackViewSet, basename="api-aifeedback")

urlpatterns = [
    path("providers/", api.ProviderListView.as_view(), name="api-aiprovider-list"),
    path("providers/health/", api.ProviderHealthView.as_view(), name="api-aiprovider-health"),
    path(
        "providers/<str:code>/models/",
        api.ProviderModelsView.as_view(),
        name="api-aiprovider-models",
    ),
    path("ask/", api.AskView.as_view(), name="api-ai-ask"),
    path("pairing/", api.PairingSuggestionView.as_view(), name="api-ai-pairing"),
    *router.urls,
]
