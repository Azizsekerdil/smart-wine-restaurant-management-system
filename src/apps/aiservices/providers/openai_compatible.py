"""OpenAI uyumlu sohbet API'si konuşan sağlayıcılar için ortak taban.

LM Studio ve NVIDIA (``integrate.api.nvidia.com``) aynı sözleşmeyi kullanır:
``GET /models`` ve ``POST /chat/completions``. Bu sınıf bu sözleşmeyi
uygular; alt sınıflar yalnızca kimlik/uyumluluk ayrıntılarını değiştirir.

**Uyumluluk varsayılmaz, doğrulanır**: ``verify_compatibility()`` çağrısı
uç noktanın gerçekten beklenen biçimde yanıt verdiğini sınar. Doğrulama
başarısız olursa sağlayıcı kullanılmaz.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx

from apps.aiservices.providers.base import (
    AIProvider,
    AIProviderError,
    AuthenticationError,
    CancellationToken,
    ChatMessage,
    ChatResponse,
    ModelInfo,
    ModelNotReadyError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
    TokenUsage,
)

logger = logging.getLogger("winehouse.ai")

#: Model kimliğinde geçtiğinde görsel desteği olduğu kabul edilen ipuçları.
#: Bu yalnızca bir *ön tahmindir*; gerçek destek ``probe_vision`` ile sınanır.
VISION_HINTS = ("vision", "-vl", "vl-", "llava", "multimodal", "image")


class OpenAICompatibleProvider(AIProvider):
    """OpenAI uyumlu ``/v1`` API'si konuşan sağlayıcılar için taban sınıf."""

    name = "openai_compatible"
    requires_api_key = True

    #: ``Authorization: Bearer`` yerine farklı bir başlık gerekiyorsa değiştirilir
    auth_header = "Authorization"
    auth_prefix = "Bearer "

    # -- HTTP yardımcıları --------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers[self.auth_header] = f"{self.auth_prefix}{self._api_key}"
        return headers

    def _client(self, *, timeout: float | None = None) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=httpx.Timeout(timeout or self.timeout, connect=min(10.0, self.timeout)),
            follow_redirects=True,
        )

    def _handle_status(self, response: httpx.Response) -> None:
        """HTTP durum kodunu uygun hata sınıfına çevirir."""
        if response.status_code < 400:
            return

        # Yanıt gövdesi API anahtarı içerebilir; maskelenerek kaydedilir.
        from apps.core.security import mask_secrets

        body = mask_secrets(response.text[:500])

        if response.status_code in (401, 403):
            raise AuthenticationError(
                "API anahtarı geçersiz veya yetkisiz.", provider=self.name, detail=body
            )
        if response.status_code == 404:
            raise ModelNotReadyError(
                "İstenen model veya uç nokta bulunamadı. Modelin yüklü olduğundan " "emin olun.",
                provider=self.name,
                detail=body,
            )
        if response.status_code == 429:
            raise RateLimitError(
                "Sağlayıcı hız sınırı uygulandı. Lütfen biraz sonra tekrar deneyin.",
                provider=self.name,
                detail=body,
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"Sağlayıcı sunucu hatası döndürdü ({response.status_code}).",
                provider=self.name,
                detail=body,
            )
        raise ProviderUnavailableError(
            f"İstek başarısız oldu ({response.status_code}).", provider=self.name, detail=body
        )

    def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        cancellation: CancellationToken | None = None,
    ) -> httpx.Response:
        """Yeniden deneme ve üstel geri çekilme ile HTTP isteği yapar.

        Kimlik doğrulama hataları yeniden denenmez (anahtar yanlışsa
        beklemenin faydası yoktur).
        """
        delays = self._retry_delays()
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if cancellation:
                cancellation.raise_if_cancelled(self.name)
            try:
                with self._client() as client:
                    response = client.request(method, path, json=json_body)
                self._handle_status(response)
                return response
            except AuthenticationError:
                raise
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_error = ProviderUnavailableError(
                    f"Sağlayıcıya bağlanılamadı: {self.base_url}", provider=self.name
                )
                logger.warning(
                    "AI sağlayıcı bağlantı hatası (%s, deneme %s/%s): %s",
                    self.name,
                    attempt + 1,
                    self.max_retries + 1,
                    type(exc).__name__,
                )
            except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as exc:
                last_error = TimeoutError(
                    f"İstek {self.timeout} saniyede tamamlanamadı.", provider=self.name
                )
                logger.warning(
                    "AI sağlayıcı zaman aşımı (%s, deneme %s/%s): %s",
                    self.name,
                    attempt + 1,
                    self.max_retries + 1,
                    type(exc).__name__,
                )
            except RateLimitError as exc:
                last_error = exc
            except ProviderUnavailableError as exc:
                last_error = exc

            if attempt < len(delays):
                time.sleep(delays[attempt])

        raise last_error or ProviderUnavailableError("İstek başarısız oldu.", provider=self.name)

    # -- Arayüz uygulaması --------------------------------------------------
    def list_models(self) -> list[ModelInfo]:
        """``GET /models`` ile kullanılabilir modelleri okur."""
        response = self._request_with_retry("GET", "/models")
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ProviderUnavailableError(
                "Model listesi okunamadı: yanıt geçerli JSON değil.", provider=self.name
            ) from exc

        entries = payload.get("data")
        if not isinstance(entries, list):
            raise ProviderUnavailableError(
                "Model listesi beklenen biçimde değil ('data' dizisi yok).",
                provider=self.name,
            )

        models: list[ModelInfo] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("id") or "").strip()
            if not model_id:
                continue
            models.append(self._parse_model_entry(model_id, entry))
        return models

    def _parse_model_entry(self, model_id: str, entry: dict[str, Any]) -> ModelInfo:
        """Sağlayıcı yanıtını ``ModelInfo``'ya çevirir. Alt sınıflar genişletir."""
        lowered = model_id.lower()
        return ModelInfo(
            id=model_id,
            provider=self.name,
            display_name=model_id,
            context_length=entry.get("context_length") or entry.get("max_context_length"),
            supports_vision=any(hint in lowered for hint in VISION_HINTS),
            supports_streaming=True,
            is_loaded=True,
            raw=entry,
        )

    def _build_payload(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "messages": [message.as_dict() for message in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        cancellation: CancellationToken | None = None,
    ) -> ChatResponse:
        resolved = self.resolve_model(model=model)
        started = time.monotonic()

        response = self._request_with_retry(
            "POST",
            "/chat/completions",
            json_body=self._build_payload(
                messages,
                model=resolved,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            ),
            cancellation=cancellation,
        )
        latency_ms = int((time.monotonic() - started) * 1000)

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ProviderUnavailableError(
                "Yanıt okunamadı: geçerli JSON değil.", provider=self.name
            ) from exc

        choices = payload.get("choices") or []
        if not choices:
            raise ModelNotReadyError(
                "Model yanıt üretmedi. Modelin yüklendiğinden emin olun.",
                provider=self.name,
            )

        first = choices[0]
        message = first.get("message") or {}
        text = message.get("content") or ""

        # Bazı akıl yürütme (reasoning) modelleri görünür yanıtı `content`
        # yerine `reasoning_content` alanına yazar ve `content` boş kalır.
        # Bu durumda kullanıcıya boş yanıt göstermek yerine akıl yürütme
        # metnini kullanırız.
        if not text.strip():
            text = message.get("reasoning_content") or message.get("reasoning") or ""

        usage_payload = payload.get("usage") or {}

        return ChatResponse(
            text=text,
            model=payload.get("model") or resolved,
            provider=self.name,
            usage=TokenUsage(
                prompt_tokens=int(usage_payload.get("prompt_tokens") or 0),
                completion_tokens=int(usage_payload.get("completion_tokens") or 0),
            ),
            latency_ms=latency_ms,
            finish_reason=str(first.get("finish_reason") or ""),
            raw=payload,
        )

    def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        cancellation: CancellationToken | None = None,
    ) -> Iterator[str]:
        """Sunucu tarafı olay akışı (SSE) ile parça parça yanıt üretir."""
        resolved = self.resolve_model(model=model)
        payload = self._build_payload(
            messages,
            model=resolved,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        try:
            with (
                self._client() as client,
                client.stream("POST", "/chat/completions", json=payload) as response,
            ):
                self._handle_status(response)
                for line in response.iter_lines():
                    if cancellation:
                        cancellation.raise_if_cancelled(self.name)
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data in {"", "[DONE]"}:
                        if data == "[DONE]":
                            break
                        continue
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        piece = delta.get("content") or delta.get("reasoning_content")
                        if piece:
                            yield piece
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise ProviderUnavailableError(
                f"Sağlayıcıya bağlanılamadı: {self.base_url}", provider=self.name
            ) from exc
        except (httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            raise TimeoutError(
                f"Akış {self.timeout} saniyede tamamlanamadı.", provider=self.name
            ) from exc

    # -- Uyumluluk doğrulama ------------------------------------------------
    def verify_compatibility(self) -> tuple[bool, str]:
        """Uç noktanın gerçekten OpenAI uyumlu olduğunu sınar.

        Endpoint biçimi *varsayılmaz*; ``/models`` yanıtının beklenen şemayı
        taşıdığı fiilen doğrulanır.

        Returns:
            ``(uyumlu_mu, açıklama)``
        """
        try:
            models = self.list_models()
        except AIProviderError as exc:
            return False, f"Uyumluluk doğrulanamadı: {exc.user_message()}"
        if not models:
            return False, "Uç nokta yanıt verdi ancak hiç model bildirmedi."
        return True, f"OpenAI uyumlu uç nokta doğrulandı ({len(models)} model bulundu)."

    def probe_vision(self, model_id: str) -> tuple[bool, str]:
        """Modelin görsel girdiyi *gerçekten* kabul edip etmediğini sınar.

        1×1 piksellik saydam bir PNG gönderilir. Model adında "vision" geçmesi
        yeterli kabul edilmez; uç nokta fiilen denenir.
        """
        tiny_png = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        payload = {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Bu görselde ne var? Tek kelimeyle yanıtla."},
                        {"type": "image_url", "image_url": {"url": tiny_png}},
                    ],
                }
            ],
            "max_tokens": 16,
            "stream": False,
        }
        try:
            with self._client(timeout=min(30, self.timeout)) as client:
                response = client.post("/chat/completions", json=payload)
            if response.status_code >= 400:
                return False, f"Görsel girdi reddedildi (HTTP {response.status_code})."
        except httpx.HTTPError as exc:
            return False, f"Görsel desteği sınanamadı: {type(exc).__name__}"
        return True, "Model görsel girdiyi kabul etti."
