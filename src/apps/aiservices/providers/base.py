"""Yapay zekâ sağlayıcı soyutlaması.

Tasarım hedefi: uygulamanın hiçbir yerinde belirli bir sağlayıcıya (LM Studio,
Anthropic, NVIDIA) bağımlılık olmaması. Tüm sağlayıcılar aynı arayüzü sunar:

    provider = get_provider("lmstudio")
    health = provider.health_check()
    models = provider.list_models()
    response = provider.chat([ChatMessage("user", "Merhaba")])

**Model adları asla koda gömülmez.** Kullanılabilir modeller her zaman
sağlayıcının kendi ``/models`` uç noktasından dinamik olarak okunur.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

Role = Literal["system", "user", "assistant"]


# ---------------------------------------------------------------------------
# Hata sınıfları
# ---------------------------------------------------------------------------
class AIProviderError(Exception):
    """Tüm sağlayıcı hatalarının temel sınıfı."""

    #: Bu hata türünde yedek sağlayıcıya geçilmeli mi?
    should_fallback: bool = True

    def __init__(self, message: str, *, provider: str = "", detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.detail = detail

    def user_message(self) -> str:
        """Kullanıcıya gösterilebilecek, gizli bilgi içermeyen mesaj."""
        from apps.core.security import mask_secrets

        return mask_secrets(self.message)


class ProviderUnavailableError(AIProviderError):
    """Sağlayıcıya hiç ulaşılamadı (bağlantı reddedildi, ağ yok)."""


class ModelNotReadyError(AIProviderError):
    """Sağlayıcı ayakta ancak istenen model yüklü/hazır değil."""


class TimeoutError(AIProviderError):  # noqa: A001 - alan adı bilinçli
    """İstek zaman aşımına uğradı."""


class RateLimitError(AIProviderError):
    """Sağlayıcı hız sınırı uygulandı."""


class AuthenticationError(AIProviderError):
    """API anahtarı eksik veya geçersiz."""

    #: Kimlik hatasında yedek sağlayıcıya geçilir, ancak yeniden denenmez.
    should_fallback = True


class CostLimitExceededError(AIProviderError):
    """Yapılandırılmış maliyet üst sınırı aşıldı."""

    should_fallback = False


class RequestCancelledError(AIProviderError):
    """Kullanıcı isteği iptal etti."""

    should_fallback = False


# ---------------------------------------------------------------------------
# Veri yapıları
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ChatMessage:
    """Tek bir sohbet mesajı."""

    role: Role
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class TokenUsage:
    """Belirteç (token) kullanımı ve tahmini maliyet."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def estimated_cost_usd(
        self, *, input_per_million: Decimal, output_per_million: Decimal
    ) -> Decimal:
        """Milyon belirteç başına fiyat verilerek tahmini maliyeti hesaplar."""
        million = Decimal("1000000")
        cost = (
            Decimal(self.prompt_tokens) / million * input_per_million
            + Decimal(self.completion_tokens) / million * output_per_million
        )
        return cost.quantize(Decimal("0.000001"))


@dataclass
class ChatResponse:
    """Sağlayıcıdan dönen yanıt."""

    text: str
    model: str
    provider: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: int = 0
    finish_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_truncated(self) -> bool:
        return self.finish_reason in {"length", "max_tokens"}


@dataclass
class ModelInfo:
    """Sağlayıcıdan okunan model bilgisi."""

    id: str
    provider: str
    display_name: str = ""
    context_length: int | None = None
    supports_vision: bool = False
    supports_streaming: bool = True
    is_loaded: bool = True
    raw: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.display_name or self.id


@dataclass
class ProviderHealth:
    """Sağlayıcı sağlık kontrolü sonucu."""

    provider: str
    reachable: bool
    models_available: int = 0
    default_model: str = ""
    latency_ms: int = 0
    message: str = ""
    is_local: bool = False
    requires_api_key: bool = False
    api_key_configured: bool = False

    @property
    def status_label(self) -> str:
        if self.reachable:
            return "Çalışıyor"
        if self.requires_api_key and not self.api_key_configured:
            return "API anahtarı yok"
        return "Ulaşılamıyor"

    @property
    def badge_class(self) -> str:
        if self.reachable:
            return "bg-success"
        if self.requires_api_key and not self.api_key_configured:
            return "bg-secondary"
        return "bg-danger"


class CancellationToken:
    """İstek iptali için iş parçacığı güvenli işaret.

    Uzun süren bir yapay zekâ isteği sırasında kullanıcı "İptal" düğmesine
    bastığında bu işaret kaldırılır ve akış bir sonraki parçada durur.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self, provider: str = "") -> None:
        if self.is_cancelled:
            raise RequestCancelledError(
                "İstek kullanıcı tarafından iptal edildi.", provider=provider
            )


# ---------------------------------------------------------------------------
# Soyut sağlayıcı
# ---------------------------------------------------------------------------
class AIProvider(ABC):
    """Tüm yapay zekâ sağlayıcılarının uyguladığı arayüz."""

    #: Sağlayıcı kodu (ayarlardaki anahtarla aynı olmalıdır)
    name: str = "base"
    #: Yerel mi çalışıyor? Yerel sağlayıcılara kişisel veri maskelenmeden gidebilir.
    is_local: bool = False
    #: API anahtarı zorunlu mu?
    requires_api_key: bool = True

    def __init__(
        self,
        *,
        base_url: str = "",
        api_key: str = "",
        model: str = "",
        timeout: int = 60,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    # -- Alt sınıfların uygulaması gerekenler ------------------------------
    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """Sağlayıcıda kullanılabilir modelleri döndürür.

        Model adları **asla** koda gömülmez; her zaman buradan okunur.
        """

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        cancellation: CancellationToken | None = None,
    ) -> ChatResponse:
        """Sohbet tamamlaması üretir."""

    @abstractmethod
    def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        cancellation: CancellationToken | None = None,
    ) -> Iterator[str]:
        """Yanıtı parça parça (streaming) üretir."""

    # -- Ortak davranış -----------------------------------------------------
    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    @property
    def redacted_api_key(self) -> str:
        """Arayüzde gösterilmek üzere kısaltılmış anahtar."""
        from apps.core.security import redact_key

        return redact_key(self._api_key)

    def health_check(self) -> ProviderHealth:
        """Sağlayıcının erişilebilirliğini sınar.

        Hiçbir koşulda istisna fırlatmaz; sonucu ``ProviderHealth`` içinde
        raporlar. Böylece ayarlar ekranı her zaman çizilebilir.
        """
        started = time.monotonic()
        if self.requires_api_key and not self.has_api_key:
            return ProviderHealth(
                provider=self.name,
                reachable=False,
                message="API anahtarı yapılandırılmamış.",
                is_local=self.is_local,
                requires_api_key=True,
                api_key_configured=False,
            )
        try:
            models = self.list_models()
        except AIProviderError as exc:
            return ProviderHealth(
                provider=self.name,
                reachable=False,
                latency_ms=int((time.monotonic() - started) * 1000),
                message=exc.user_message(),
                is_local=self.is_local,
                requires_api_key=self.requires_api_key,
                api_key_configured=self.has_api_key,
            )
        except Exception as exc:  # pragma: no cover - beklenmeyen hata yolu
            return ProviderHealth(
                provider=self.name,
                reachable=False,
                latency_ms=int((time.monotonic() - started) * 1000),
                message=f"Beklenmeyen hata: {type(exc).__name__}",
                is_local=self.is_local,
                requires_api_key=self.requires_api_key,
                api_key_configured=self.has_api_key,
            )

        return ProviderHealth(
            provider=self.name,
            reachable=True,
            models_available=len(models),
            default_model=self.resolve_model(models=models),
            latency_ms=int((time.monotonic() - started) * 1000),
            message="Bağlantı başarılı.",
            is_local=self.is_local,
            requires_api_key=self.requires_api_key,
            api_key_configured=self.has_api_key,
        )

    def resolve_model(self, *, model: str = "", models: list[ModelInfo] | None = None) -> str:
        """Kullanılacak model kimliğini belirler.

        Öncelik sırası:
          1. Çağrıda açıkça verilen model
          2. Yapılandırmadaki model
          3. Sağlayıcıdan okunan ilk kullanılabilir model
        """
        if model:
            return model
        if self.model:
            return self.model
        available = models if models is not None else self.list_models()
        if not available:
            raise ModelNotReadyError(
                "Sağlayıcıda kullanılabilir model bulunamadı.", provider=self.name
            )
        return available[0].id

    def supports_vision(self, model_id: str) -> bool:
        """Modelin görsel girdi destekleyip desteklemediğini bildirir.

        Varsayılan uygulama sağlayıcının model listesindeki bayrağa bakar.
        Bayrak yoksa ``False`` döner — *varsayım yapılmaz*.
        """
        for info in self.list_models():
            if info.id == model_id:
                return info.supports_vision
        return False

    def _retry_delays(self) -> list[float]:
        """Üstel geri çekilme (exponential backoff) gecikmeleri."""
        return [0.5 * (2**attempt) for attempt in range(self.max_retries)]
