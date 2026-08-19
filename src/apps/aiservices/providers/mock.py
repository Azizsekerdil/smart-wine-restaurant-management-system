"""Mock sağlayıcı — test ve tam çevrimdışı kullanım için.

Hiçbir ağ çağrısı yapmaz. Yanıtlar istemin içeriğine göre *belirlenimci*
(deterministic) biçimde üretilir; böylece testler kararlıdır ve internet
veya yerel model olmadan da uygulamanın tüm yapay zekâ akışları çalışır.

Bu sağlayıcı gerçek bir dil modeli değildir. Ürettiği metinler arayüzde
her zaman "Mock — gerçek model yanıtı değil" etiketiyle gösterilir.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator

from apps.aiservices.providers.base import (
    AIProvider,
    CancellationToken,
    ChatMessage,
    ChatResponse,
    ModelInfo,
    TokenUsage,
)

MOCK_NOTICE = "[Mock sağlayıcı — gerçek model yanıtı değildir.]"


class MockProvider(AIProvider):
    """Belirlenimci sahte sağlayıcı."""

    name = "mock"
    is_local = True
    requires_api_key = False

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("model", "winehouse-mock-1")
        kwargs.setdefault("timeout", 5)
        super().__init__(**kwargs)  # type: ignore[arg-type]

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                id="winehouse-mock-1",
                provider=self.name,
                display_name="Wine House Mock (genel)",
                context_length=8192,
                supports_vision=False,
            ),
            ModelInfo(
                id="winehouse-mock-vision-1",
                provider=self.name,
                display_name="Wine House Mock (görsel)",
                context_length=8192,
                supports_vision=True,
            ),
        ]

    # -- Yanıt üretimi ------------------------------------------------------
    @staticmethod
    def _last_user_message(messages: list[ChatMessage]) -> str:
        for message in reversed(messages):
            if message.role == "user":
                return message.content
        return ""

    def _compose(self, messages: list[ChatMessage]) -> str:
        """İstemin konusuna göre uygun sahte yanıtı seçer."""
        prompt = self._last_user_message(messages)
        lowered = prompt.lower()
        # Belirlenimcilik için istemin özetinden sabit bir "tohum" üretilir
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]

        if any(word in lowered for word in ("eşleş", "pairing", "uyum", "hangi şarap")):
            return (
                f"{MOCK_NOTICE}\n\n"
                "**Önerilen eşleştirme**\n"
                "- Yağlı ve tuzlu tabaklarda yüksek asiditeli beyazlar dengeyi kurar.\n"
                "- Tanenli kırmızılar, kolajen açısından zengin kırmızı etlerle uyumludur.\n"
                "- Tatlı tabakta şarabın tatlılığı tatlıdan yüksek olmalıdır.\n\n"
                "Bu öneri sommelier onayı gerektirir.\n"
                f"(referans: {digest})"
            )

        if any(word in lowered for word in ("rapor", "report", "satış", "özet")):
            return (
                f"{MOCK_NOTICE}\n\n"
                "**Dönem özeti**\n"
                "- Net satış önceki döneme göre yatay seyretti.\n"
                "- Kadeh şarap satışının payı şişe satışına göre arttı.\n"
                "- Fire maliyeti kabul edilebilir aralıkta.\n\n"
                "Sayısal doğrulama için rapor ekranındaki tabloyu esas alın.\n"
                f"(referans: {digest})"
            )

        if any(word in lowered for word in ("stok", "sipariş öner", "satın alma", "tedarik")):
            return (
                f"{MOCK_NOTICE}\n\n"
                "**Stok önerisi**\n"
                "- Minimum seviyenin altındaki kalemler için sipariş taslağı hazırlanabilir.\n"
                "- Son kullanma tarihi yaklaşan partiler önce tüketilmelidir (FEFO).\n\n"
                "Öneri, kullanıcı onayı olmadan uygulanmaz.\n"
                f"(referans: {digest})"
            )

        if any(word in lowered for word in ("etiket", "görsel", "fotoğraf", "label")):
            return (
                f"{MOCK_NOTICE}\n\n"
                "Görsel çözümleme bu sağlayıcıda benzetilmiştir. Gerçek etiket "
                "okuma için görsel destekli bir model seçin.\n"
                f"(referans: {digest})"
            )

        # Genel yanıt: istemi özetleyen belirlenimci metin
        preview = re.sub(r"\s+", " ", prompt).strip()[:160]
        return (
            f"{MOCK_NOTICE}\n\n"
            f"Alınan istem: “{preview}”\n\n"
            "Bu sağlayıcı test amaçlıdır ve gerçek bir dil modeli çalıştırmaz. "
            "Gerçek yanıt için Ayarlar → Yapay Zekâ ekranından LM Studio, "
            "Anthropic veya NVIDIA sağlayıcısını etkinleştirin.\n"
            f"(referans: {digest})"
        )

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        cancellation: CancellationToken | None = None,
    ) -> ChatResponse:
        if cancellation:
            cancellation.raise_if_cancelled(self.name)
        text = self._compose(messages)
        prompt_characters = sum(len(message.content) for message in messages)
        return ChatResponse(
            text=text,
            model=self.resolve_model(model=model),
            provider=self.name,
            usage=TokenUsage(
                prompt_tokens=max(1, prompt_characters // 4),
                completion_tokens=max(1, len(text) // 4),
            ),
            latency_ms=1,
            finish_reason="stop",
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
        text = self._compose(messages)
        for word in text.split(" "):
            if cancellation:
                cancellation.raise_if_cancelled(self.name)
            yield word + " "
