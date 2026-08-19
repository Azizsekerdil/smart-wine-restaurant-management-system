"""NVIDIA bulut sağlayıcı adaptörü (build.nvidia.com / NIM).

NVIDIA'nın barındırılan uç noktası (``https://integrate.api.nvidia.com/v1``)
OpenAI uyumlu bir sözleşme sunar. Bu adaptör bu uyumluluğu **varsaymak
yerine doğrular**: ilk kullanımdan önce ``verify_compatibility()`` çağrılır
ve sonuç ``docs/NVIDIA_MODEL_EVALUATION.md`` içine kaydedilir.

GÜVENLİK: ``NVIDIA_API_KEY`` yalnızca ortam değişkeninden veya şifreli
ayar deposundan okunur; hiçbir zaman günlüğe, ekrana veya depoya yazılmaz.
"""

from __future__ import annotations

from typing import Any

from apps.aiservices.providers.base import ModelInfo
from apps.aiservices.providers.openai_compatible import OpenAICompatibleProvider


class NvidiaProvider(OpenAICompatibleProvider):
    """NVIDIA barındırılan model uç noktası."""

    name = "nvidia"
    is_local = False
    requires_api_key = True

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("base_url", "https://integrate.api.nvidia.com/v1")
        super().__init__(**kwargs)

    def _parse_model_entry(self, model_id: str, entry: dict[str, Any]) -> ModelInfo:
        info = super()._parse_model_entry(model_id, entry)
        # NVIDIA model kimlikleri "yayıncı/model" biçimindedir (ör. "meta/llama-...").
        if "/" in model_id:
            info.display_name = model_id.split("/", 1)[1]
        return info

    def models_by_publisher(self) -> dict[str, list[ModelInfo]]:
        """Modelleri yayıncıya göre gruplar (karşılaştırma tablosu için)."""
        grouped: dict[str, list[ModelInfo]] = {}
        for model in self.list_models():
            publisher = model.id.split("/", 1)[0] if "/" in model.id else "diğer"
            grouped.setdefault(publisher, []).append(model)
        return grouped
