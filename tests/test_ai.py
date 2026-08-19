"""Yapay zekâ katmanı testleri.

Hiçbir test gerçek ağ çağrısı yapmaz: LM Studio / Anthropic / NVIDIA
adaptörleri sahte HTTP taşıyıcılarıyla sınanır.
"""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest

from apps.aiservices.providers.base import (
    AuthenticationError,
    CancellationToken,
    ChatMessage,
    ProviderUnavailableError,
    RequestCancelledError,
    TokenUsage,
)

pytestmark = pytest.mark.ai


# ---------------------------------------------------------------------------
# Sahte taşıyıcı yardımcıları
# ---------------------------------------------------------------------------
def mock_transport(handler):
    """httpx.MockTransport üretir."""
    return httpx.MockTransport(handler)


def patch_client(monkeypatch, provider, handler):
    """Sağlayıcının HTTP istemcisini sahte taşıyıcıyla değiştirir."""
    original = provider._client

    def _client(*, timeout=None):
        client = original(timeout=timeout)
        client._transport = mock_transport(handler)
        return client

    monkeypatch.setattr(provider, "_client", _client)


# ---------------------------------------------------------------------------
# Mock sağlayıcı
# ---------------------------------------------------------------------------
def test_mock_saglayici_belirlenimcidir() -> None:
    from apps.aiservices.providers.mock import MockProvider

    provider = MockProvider()
    messages = [ChatMessage("user", "Kuzu tandır için şarap öner")]
    first = provider.chat(messages)
    second = provider.chat(messages)

    assert first.text == second.text
    assert "Mock sağlayıcı" in first.text
    assert first.usage.total_tokens > 0


def test_mock_saglayici_eslesme_sorusunu_taniyor() -> None:
    from apps.aiservices.providers.mock import MockProvider

    result = MockProvider().chat([ChatMessage("user", "Hangi şarap uyar?")])
    assert "eşleştirme" in result.text.lower() or "asidite" in result.text.lower()


def test_mock_saglayici_akis_uretir() -> None:
    from apps.aiservices.providers.mock import MockProvider

    parts = list(MockProvider().stream_chat([ChatMessage("user", "merhaba")]))
    assert len(parts) > 1
    assert "".join(parts).strip()


def test_iptal_isareti_akisi_durdurur() -> None:
    from apps.aiservices.providers.mock import MockProvider

    token = CancellationToken()
    token.cancel()
    with pytest.raises(RequestCancelledError):
        MockProvider().chat([ChatMessage("user", "test")], cancellation=token)


# ---------------------------------------------------------------------------
# LM Studio adaptörü
# ---------------------------------------------------------------------------
def test_lmstudio_model_listesini_dinamik_okur(monkeypatch) -> None:
    """Model adları koda gömülmez; /models ucundan okunur."""
    from apps.aiservices.providers.lmstudio import LMStudioProvider

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gemma-3-12b-it", "state": "loaded", "max_context_length": 8192},
                    {"id": "qwen2.5-coder-7b", "state": "not-loaded"},
                    {"id": "llava-v1.6-vision", "state": "loaded"},
                ]
            },
        )

    provider = LMStudioProvider()
    patch_client(monkeypatch, provider, handler)

    models = provider.list_models()
    assert [m.id for m in models] == [
        "gemma-3-12b-it",
        "qwen2.5-coder-7b",
        "llava-v1.6-vision",
    ]
    assert models[0].is_loaded
    assert not models[1].is_loaded
    assert models[2].supports_vision


def test_lmstudio_gorev_bazli_model_onerir(monkeypatch) -> None:
    from apps.aiservices.providers.lmstudio import LMStudioProvider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gemma-3-12b-it", "state": "loaded"},
                    {"id": "qwen2.5-coder-14b", "state": "loaded"},
                    {"id": "llava-vision-7b", "state": "loaded"},
                    {"id": "nomic-embed-text", "state": "loaded"},
                ]
            },
        )

    provider = LMStudioProvider()
    patch_client(monkeypatch, provider, handler)

    assert "coder" in provider.suggest_model("coding")
    assert "llava" in provider.suggest_model("vision")
    assert "embed" in provider.suggest_model("embedding")


def test_lmstudio_alan_disi_modeli_onermez(monkeypatch) -> None:
    """Kurulu olsa bile alan dışı (ör. tıbbi) model genel görevde seçilmez."""
    from apps.aiservices.providers.lmstudio import LMStudioProvider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "BioMistral-7B", "state": "loaded"},
                    {"id": "gemma-3-4b-it", "state": "loaded"},
                ]
            },
        )

    provider = LMStudioProvider()
    patch_client(monkeypatch, provider, handler)
    assert provider.suggest_model("general") == "gemma-3-4b-it"


def test_lmstudio_kapali_sunucu_yol_gosterici_hata_verir(monkeypatch) -> None:
    from apps.aiservices.providers.lmstudio import LMStudioProvider

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("bağlantı reddedildi", request=request)

    provider = LMStudioProvider(timeout=1, max_retries=0)
    patch_client(monkeypatch, provider, handler)

    with pytest.raises(ProviderUnavailableError) as exc:
        provider.list_models()

    message = str(exc.value)
    assert "LM Studio" in message
    assert "Start Server" in message


def test_lmstudio_saglik_kontrolu_istisna_firlatmaz(monkeypatch) -> None:
    """Ayar ekranı her koşulda çizilebilmelidir."""
    from apps.aiservices.providers.lmstudio import LMStudioProvider

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("kapalı", request=request)

    provider = LMStudioProvider(timeout=1, max_retries=0)
    patch_client(monkeypatch, provider, handler)

    health = provider.health_check()
    assert not health.reachable
    assert health.badge_class == "bg-danger"
    assert "LM Studio" in health.message


def test_lmstudio_zaman_asimi_bildirilir(monkeypatch) -> None:
    from apps.aiservices.providers.base import TimeoutError as AITimeoutError
    from apps.aiservices.providers.lmstudio import LMStudioProvider

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("çok yavaş", request=request)

    provider = LMStudioProvider(timeout=2, max_retries=0)
    patch_client(monkeypatch, provider, handler)

    with pytest.raises(AITimeoutError, match="2 saniyede"):
        provider.list_models()


def test_lmstudio_sohbet_yaniti_ayristirilir(monkeypatch) -> None:
    from apps.aiservices.providers.lmstudio import LMStudioProvider

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "test-model"}]})
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["stream"] is False
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [
                    {"message": {"content": "Öküzgözü öneririm."}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 42, "completion_tokens": 17},
            },
        )

    provider = LMStudioProvider()
    patch_client(monkeypatch, provider, handler)

    response = provider.chat([ChatMessage("user", "öner")])
    assert response.text == "Öküzgözü öneririm."
    assert response.usage.prompt_tokens == 42
    assert response.usage.completion_tokens == 17
    assert response.finish_reason == "stop"


def test_openai_uyumluluk_dogrulanir(monkeypatch) -> None:
    """Uyumluluk varsayılmaz; fiilen sınanır."""
    from apps.aiservices.providers.nvidia import NvidiaProvider

    def uyumlu(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "meta/llama-3.3-70b"}]})

    def uyumsuz(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": ["x"]})  # 'data' yok

    provider = NvidiaProvider(api_key="nvapi-test", max_retries=0)

    patch_client(monkeypatch, provider, uyumlu)
    ok, message = provider.verify_compatibility()
    assert ok and "doğrulandı" in message

    patch_client(monkeypatch, provider, uyumsuz)
    ok, message = provider.verify_compatibility()
    assert not ok


def test_nvidia_modelleri_yayinciya_gore_gruplanir(monkeypatch) -> None:
    from apps.aiservices.providers.nvidia import NvidiaProvider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "meta/llama-3.3-70b-instruct"},
                    {"id": "meta/llama-3.1-8b-instruct"},
                    {"id": "mistralai/mistral-large"},
                ]
            },
        )

    provider = NvidiaProvider(api_key="nvapi-test")
    patch_client(monkeypatch, provider, handler)

    grouped = provider.models_by_publisher()
    assert set(grouped) == {"meta", "mistralai"}
    assert len(grouped["meta"]) == 2


# ---------------------------------------------------------------------------
# Anthropic adaptörü
# ---------------------------------------------------------------------------
def test_anthropic_dogru_baslikları_gonderir(monkeypatch) -> None:
    from apps.aiservices.providers.anthropic import ANTHROPIC_VERSION, AnthropicProvider

    gorulen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gorulen.update(request.headers)
        return httpx.Response(200, json={"data": [{"id": "model-x", "display_name": "X"}]})

    provider = AnthropicProvider(api_key="sk-ant-test-key")
    patch_client(monkeypatch, provider, handler)
    provider.list_models()

    assert gorulen["x-api-key"] == "sk-ant-test-key"
    assert gorulen["anthropic-version"] == ANTHROPIC_VERSION
    assert "authorization" not in gorulen


def test_anthropic_model_adi_gomulu_degil(monkeypatch) -> None:
    """Yapılandırmada model yoksa listeden ilk model kullanılır."""
    from apps.aiservices.providers.anthropic import AnthropicProvider

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "model-newest", "display_name": "En yeni"},
                        {"id": "model-older", "display_name": "Eski"},
                    ],
                    "has_more": False,
                },
            )
        payload = json.loads(request.content)
        assert payload["model"] == "model-newest"
        return httpx.Response(
            200,
            json={
                "model": "model-newest",
                "content": [{"type": "text", "text": "Merhaba"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    provider = AnthropicProvider(api_key="sk-ant-test")
    patch_client(monkeypatch, provider, handler)

    response = provider.chat([ChatMessage("user", "selam")])
    assert response.text == "Merhaba"
    assert response.usage.prompt_tokens == 10
    assert response.usage.completion_tokens == 5


def test_anthropic_sistem_istemi_ayri_alanda_gonderilir(monkeypatch) -> None:
    from apps.aiservices.providers.anthropic import AnthropicProvider

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "m"}], "has_more": False})
        payload = json.loads(request.content)
        assert payload["system"] == "Sen bir sommelier asistanısın."
        assert all(m["role"] != "system" for m in payload["messages"])
        assert "max_tokens" in payload
        return httpx.Response(
            200,
            json={
                "model": "m",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    provider = AnthropicProvider(api_key="sk-ant-test")
    patch_client(monkeypatch, provider, handler)
    provider.chat(
        [
            ChatMessage("system", "Sen bir sommelier asistanısın."),
            ChatMessage("user", "öner"),
        ]
    )


def test_anthropic_401_kimlik_hatasi_verir(monkeypatch) -> None:
    from apps.aiservices.providers.anthropic import AnthropicProvider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    provider = AnthropicProvider(api_key="sk-ant-yanlis", max_retries=2)
    patch_client(monkeypatch, provider, handler)

    with pytest.raises(AuthenticationError, match="geçersiz"):
        provider.list_models()


def test_anahtarsiz_saglayici_saglik_kontrolu(monkeypatch) -> None:
    from apps.aiservices.providers.anthropic import AnthropicProvider

    health = AnthropicProvider(api_key="").health_check()
    assert not health.reachable
    assert health.requires_api_key
    assert not health.api_key_configured
    assert "anahtarı" in health.message


def test_hata_mesajinda_anahtar_sizmaz(monkeypatch) -> None:
    """Sağlayıcı yanıtı anahtar içerse bile hata mesajı maskelenir."""
    from apps.aiservices.providers.base import AIProviderError
    from apps.aiservices.providers.lmstudio import LMStudioProvider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad request with key sk-ant-api03-cokgizlideger123456")

    provider = LMStudioProvider(max_retries=0)
    patch_client(monkeypatch, provider, handler)

    with pytest.raises(AIProviderError) as exc:
        provider.list_models()
    assert "cokgizlideger" not in exc.value.detail


# ---------------------------------------------------------------------------
# Kayıt defteri ve yedekleme zinciri
# ---------------------------------------------------------------------------
def test_yedekleme_zinciri_mock_ile_biter() -> None:
    from apps.aiservices.registry import build_fallback_chain

    chain = build_fallback_chain()
    assert chain[-1] == "mock", "Zincir mock ile bitmeli; akış hiç çökmemeli."


def test_yerel_oncelik_zinciri_siralar(settings) -> None:
    from apps.aiservices.registry import build_fallback_chain

    settings.AI_SETTINGS = {
        **settings.AI_SETTINGS,
        "FALLBACK_ORDER": ["anthropic", "lmstudio", "nvidia"],
        "PREFER_LOCAL": True,
        "LOCAL_ONLY": False,
    }
    chain = build_fallback_chain()
    assert chain.index("lmstudio") < chain.index("anthropic")


def test_yalnizca_yerel_modda_bulut_zincire_girmez(settings) -> None:
    from apps.aiservices.registry import build_fallback_chain

    settings.AI_SETTINGS = {
        **settings.AI_SETTINGS,
        "FALLBACK_ORDER": ["lmstudio", "anthropic", "nvidia"],
        "LOCAL_ONLY": True,
    }
    chain = build_fallback_chain()
    assert "anthropic" not in chain
    assert "nvidia" not in chain


def test_bilinmeyen_saglayici_hata_verir() -> None:
    from apps.aiservices.registry import UnknownProviderError, get_provider

    with pytest.raises(UnknownProviderError, match="Tanımsız"):
        get_provider("gpt-uydurma")


# ---------------------------------------------------------------------------
# Servis katmanı: gizlilik, maliyet, yedekleme
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_bulut_gonderiminden_once_kisisel_veri_maskelenir(settings) -> None:
    from apps.aiservices.services import prepare_prompt_for_provider

    settings.AI_SETTINGS = {**settings.AI_SETTINGS, "PRIVACY_MODE": True}
    text, masking = prepare_prompt_for_provider(
        "Müşteri ayse@ornek.com, 0555 123 45 67", is_local_provider=False
    )
    assert "ayse@ornek.com" not in text
    assert masking is not None and masking.was_masked


@pytest.mark.django_db
def test_gizlilik_kapaliyken_yerel_saglayiciya_ham_metin_gider(settings) -> None:
    from apps.aiservices.services import prepare_prompt_for_provider

    settings.AI_SETTINGS = {**settings.AI_SETTINGS, "PRIVACY_MODE": False}
    original = "Müşteri ayse@ornek.com"
    text, masking = prepare_prompt_for_provider(original, is_local_provider=True)
    assert text == original
    assert masking is None


@pytest.mark.django_db
def test_ask_mock_ile_calisir_ve_kayit_uretir(admin_user) -> None:
    from apps.aiservices.models import AICallLog, AIFeature
    from apps.aiservices.services import ask

    result = ask(
        user=admin_user,
        feature=AIFeature.SOMMELIER,
        prompt="Kuzu tandır için şarap öner",
    )

    assert result.is_mock
    assert result.text
    assert AICallLog.objects.filter(outcome=AICallLog.Outcome.SUCCESS).exists()
    assert result.call_log.provider == "mock"


@pytest.mark.django_db
def test_ask_gizlilik_bildirimi_uretir(admin_user) -> None:
    from apps.aiservices.models import AIFeature
    from apps.aiservices.services import ask

    result = ask(
        user=admin_user,
        feature=AIFeature.SOMMELIER,
        prompt="Müşteri ayse@ornek.com için öneri",
    )
    assert result.privacy_notice


@pytest.mark.django_db
def test_maliyet_fiyat_tanimliysa_hesaplanir() -> None:
    from apps.aiservices.models import ProviderPricing
    from apps.aiservices.services import estimate_cost

    usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=500_000)

    # Fiyat tanımlı değil → 0 (uygulama hiçbir fiyatı varsaymaz)
    assert estimate_cost("anthropic", "model-x", usage) == Decimal("0.000000")

    ProviderPricing.objects.create(
        provider="anthropic",
        model="model-x",
        input_usd_per_million=Decimal("3.0000"),
        output_usd_per_million=Decimal("15.0000"),
    )
    assert estimate_cost("anthropic", "model-x", usage) == Decimal("10.500000")


@pytest.mark.django_db
def test_butce_asilinca_bulut_engellenir(admin_user, settings) -> None:
    """Kesin sınır aşıldığında bulut sağlayıcı atlanır, akış mock'a düşer."""
    from apps.aiservices.models import AICallLog, AIFeature
    from apps.aiservices.services import ask, current_budget

    settings.AI_SETTINGS = {
        **settings.AI_SETTINGS,
        "LOCAL_ONLY": False,
        "FALLBACK_ORDER": ["anthropic", "mock"],
        "PREFER_LOCAL": False,
    }
    budget = current_budget()
    budget.limit_usd = Decimal("1.00")
    budget.spent_usd = Decimal("5.00")
    budget.is_hard_limit = True
    budget.save()

    result = ask(user=admin_user, feature=AIFeature.SOMMELIER, prompt="test")

    assert result.is_mock
    assert AICallLog.objects.filter(outcome=AICallLog.Outcome.BLOCKED).exists()


@pytest.mark.django_db
def test_sohbet_gecmisi_kaydedilir(admin_user) -> None:
    from apps.aiservices.models import AIConversation, AIFeature, AIMessage
    from apps.aiservices.services import ask

    conversation = AIConversation.objects.create(user=admin_user, feature=AIFeature.SOMMELIER)
    ask(
        user=admin_user,
        feature=AIFeature.SOMMELIER,
        prompt="Şarap öner",
        conversation=conversation,
    )

    messages = AIMessage.objects.filter(conversation=conversation).order_by("sequence")
    assert messages.count() == 2
    assert messages[0].role == AIMessage.Role.USER
    assert messages[1].role == AIMessage.Role.ASSISTANT
    conversation.refresh_from_db()
    assert conversation.title


@pytest.mark.django_db
def test_eslesme_onerisi_yalnizca_verilen_saraplardan_secer(admin_user) -> None:
    from apps.aiservices.services import suggest_wine_pairing

    result = suggest_wine_pairing(
        user=admin_user,
        dish_description="Kuzu tandır",
        available_wines=["Anadolu Terroir Öküzgözü 2020"],
    )
    assert result.text
    assert result.is_mock


@pytest.mark.django_db
def test_sistem_istemi_sorumlu_servis_kurallarini_icerir() -> None:
    from apps.aiservices.services import SOMMELIER_SYSTEM_PROMPT

    assert "sağlık iddiasında" in SOMMELIER_SYSTEM_PROMPT
    assert "18 yaş" in SOMMELIER_SYSTEM_PROMPT
    assert "uydurma" in SOMMELIER_SYSTEM_PROMPT
