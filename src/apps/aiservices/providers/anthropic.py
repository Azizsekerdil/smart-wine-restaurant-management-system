"""Anthropic Claude bulut sağlayıcı adaptörü.

Anthropic Messages API'si OpenAI sözleşmesinden farklıdır; bu nedenle
``OpenAICompatibleProvider`` yerine doğrudan ``AIProvider`` uygulanır.

Sözleşme özeti:
  * Kimlik: ``x-api-key`` başlığı (``Authorization: Bearer`` **değil**)
  * Sürüm: ``anthropic-version`` başlığı zorunludur
  * Uç noktalar: ``POST /v1/messages``, ``GET /v1/models``
  * Sistem istemi ayrı ``system`` alanındadır (mesaj listesinde değil)
  * ``max_tokens`` zorunludur
  * Yanıt gövdesi: ``content`` bir *blok dizisidir*, düz metin değildir
  * Kullanım: ``usage.input_tokens`` / ``usage.output_tokens``

**Model adları koda gömülmez.** Kullanılabilir modeller her zaman
``GET /v1/models`` uç noktasından okunur; yapılandırmada model belirtilmezse
listedeki ilk (en güncel) model kullanılır.

GÜVENLİK: ``ANTHROPIC_API_KEY`` yalnızca ortamdan veya şifreli ayar
deposundan okunur. Anahtar; günlüklere, hata mesajlarına, arayüze veya
sürüm denetimine hiçbir koşulda yazılmaz.
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

#: Messages API sürüm başlığı. Anthropic sürüm başlığını zorunlu kılar.
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(AIProvider):
    """Anthropic Messages API adaptörü."""

    name = "anthropic"
    is_local = False
    requires_api_key = True

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("base_url", "https://api.anthropic.com/v1")
        super().__init__(**kwargs)

    # -- HTTP yardımcıları --------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "content-type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }

    def _client(self, *, timeout: float | None = None) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=httpx.Timeout(timeout or self.timeout, connect=min(10.0, self.timeout)),
            follow_redirects=True,
        )

    def _handle_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return

        from apps.core.security import mask_secrets

        body = mask_secrets(response.text[:500])

        if response.status_code in (401, 403):
            raise AuthenticationError(
                "Anthropic API anahtarı geçersiz veya yetkisiz. "
                "Ayarlar → Yapay Zekâ ekranından anahtarı kontrol edin.",
                provider=self.name,
                detail=body,
            )
        if response.status_code == 404:
            raise ModelNotReadyError(
                "İstenen model bu hesap için kullanılabilir değil. "
                "Model listesinden erişilebilir bir model seçin.",
                provider=self.name,
                detail=body,
            )
        if response.status_code == 429:
            raise RateLimitError(
                "Anthropic hız sınırı uygulandı. Lütfen biraz sonra tekrar deneyin.",
                provider=self.name,
                detail=body,
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"Anthropic sunucu hatası ({response.status_code}).",
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
        params: dict[str, Any] | None = None,
        cancellation: CancellationToken | None = None,
    ) -> httpx.Response:
        delays = self._retry_delays()
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if cancellation:
                cancellation.raise_if_cancelled(self.name)
            try:
                with self._client() as client:
                    response = client.request(method, path, json=json_body, params=params)
                self._handle_status(response)
                return response
            except AuthenticationError:
                raise
            except (httpx.ConnectError, httpx.ConnectTimeout):
                last_error = ProviderUnavailableError(
                    "Anthropic API'sine bağlanılamadı. İnternet bağlantısını kontrol edin.",
                    provider=self.name,
                )
            except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout):
                last_error = TimeoutError(
                    f"İstek {self.timeout} saniyede tamamlanamadı.", provider=self.name
                )
            except (RateLimitError, ProviderUnavailableError) as exc:
                last_error = exc

            if attempt < len(delays):
                time.sleep(delays[attempt])

        raise last_error or ProviderUnavailableError("İstek başarısız oldu.", provider=self.name)

    # -- Arayüz uygulaması --------------------------------------------------
    def list_models(self) -> list[ModelInfo]:
        """``GET /v1/models`` ile hesabın erişebildiği modelleri okur.

        Anthropic listeyi en yeni model başta olacak şekilde döndürür.
        Sayfalama ``has_more`` / ``after_id`` ile yapılır.
        """
        models: list[ModelInfo] = []
        params: dict[str, Any] = {"limit": 100}
        guard = 0

        while guard < 10:
            guard += 1
            response = self._request_with_retry("GET", "/models", params=params)
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

            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                model_id = str(entry.get("id") or "").strip()
                if not model_id:
                    continue
                models.append(
                    ModelInfo(
                        id=model_id,
                        provider=self.name,
                        display_name=str(entry.get("display_name") or model_id),
                        # Bağlam uzunluğu ve görsel desteği listeleme yanıtında
                        # bildirilmez; varsayım yapılmaz (None / False bırakılır).
                        context_length=None,
                        supports_vision=False,
                        supports_streaming=True,
                        raw=entry,
                    )
                )

            if not payload.get("has_more") or not payload.get("last_id"):
                break
            params = {"limit": 100, "after_id": payload["last_id"]}

        return models

    @staticmethod
    def _split_system(messages: list[ChatMessage]) -> tuple[str, list[dict[str, str]]]:
        """Sistem istemini ayırır.

        Anthropic sözleşmesinde ``system`` mesaj listesinde değil, ayrı bir
        üst düzey alandır.
        """
        system_parts: list[str] = []
        conversation: list[dict[str, str]] = []
        for message in messages:
            if message.role == "system":
                system_parts.append(message.content)
            else:
                conversation.append(message.as_dict())
        return "\n\n".join(system_parts), conversation

    @staticmethod
    def _extract_text(content: Any) -> str:
        """``content`` blok dizisinden düz metni çıkarır."""
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ""
        parts = [
            str(block.get("text") or "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts)

    def _build_payload(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> dict[str, Any]:
        system_prompt, conversation = self._split_system(messages)
        if not conversation:
            raise ModelNotReadyError(
                "Anthropic isteği en az bir kullanıcı mesajı gerektirir.", provider=self.name
            )
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": conversation,
            "temperature": temperature,
            "stream": stream,
        }
        if system_prompt:
            payload["system"] = system_prompt
        return payload

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
            "/messages",
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

        usage_payload = payload.get("usage") or {}

        return ChatResponse(
            text=self._extract_text(payload.get("content")),
            model=str(payload.get("model") or resolved),
            provider=self.name,
            usage=TokenUsage(
                prompt_tokens=int(usage_payload.get("input_tokens") or 0),
                completion_tokens=int(usage_payload.get("output_tokens") or 0),
            ),
            latency_ms=latency_ms,
            finish_reason=str(payload.get("stop_reason") or ""),
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
        """Messages API akışını (SSE) metin parçalarına dönüştürür.

        İlgilenilen olay ``content_block_delta`` ve içindeki
        ``delta.type == "text_delta"`` alanıdır.
        """
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
                client.stream("POST", "/messages", json=payload) as response,
            ):
                self._handle_status(response)
                for line in response.iter_lines():
                    if cancellation:
                        cancellation.raise_if_cancelled(self.name)
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    event_type = event.get("type")
                    if event_type == "content_block_delta":
                        delta = event.get("delta") or {}
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            yield str(delta["text"])
                    elif event_type in {"message_stop", "error"}:
                        break
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise ProviderUnavailableError(
                "Anthropic API'sine bağlanılamadı.", provider=self.name
            ) from exc
        except (httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            raise TimeoutError(
                f"Akış {self.timeout} saniyede tamamlanamadı.", provider=self.name
            ) from exc

    def count_tokens(self, messages: list[ChatMessage], *, model: str = "") -> int:
        """İstek göndermeden önce belirteç sayısını tahmin eder.

        Maliyet sınırı denetimi bu değeri kullanır. Uç nokta desteklenmiyorsa
        kaba bir tahmine (≈4 karakter = 1 belirteç) düşer.
        """
        resolved = self.resolve_model(model=model)
        system_prompt, conversation = self._split_system(messages)
        body: dict[str, Any] = {"model": resolved, "messages": conversation}
        if system_prompt:
            body["system"] = system_prompt

        try:
            response = self._request_with_retry("POST", "/messages/count_tokens", json_body=body)
            payload = response.json()
            return int(payload.get("input_tokens") or 0)
        except Exception:  # pragma: no cover - tahmin yedeği
            characters = sum(len(message.content) for message in messages)
            return max(1, characters // 4)
