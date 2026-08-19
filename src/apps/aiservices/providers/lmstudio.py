"""LM Studio yerel sağlayıcı adaptörü.

LM Studio, ``http://localhost:1234/v1`` adresinde OpenAI uyumlu bir sunucu
açar. Bu adaptör:

  * Model listesini **dinamik olarak** ``/v1/models`` uç noktasından okur —
    hiçbir model adı koda gömülmez.
  * Sunucu kapalıysa açık ve anlaşılır bir hata mesajı üretir.
  * Model yüklü değilse "model hazır değil" durumunu ayırt eder.
  * Yerel çalıştığı için gizlilik açısından **öncelikli sağlayıcıdır**:
    kişisel veriler maskelenmeden gönderilebilir (yine de gizlilik modu
    açıkken maskeleme uygulanır).
"""

from __future__ import annotations

import logging
from typing import Any

from apps.aiservices.providers.base import ModelInfo, ProviderUnavailableError
from apps.aiservices.providers.openai_compatible import (
    VISION_HINTS,
    OpenAICompatibleProvider,
)

logger = logging.getLogger("winehouse.ai")

#: Görev türüne göre model seçiminde kullanılan ipuçları.
#: Yalnızca *sıralama* için kullanılır; hiçbir model adı zorunlu değildir.
TASK_HINTS: dict[str, tuple[str, ...]] = {
    # Genel asistan / sommelier sohbeti
    "general": ("instruct", "chat", "it", "gemma", "llama", "mistral", "phi", "qwen"),
    # Kod üretimi (AI Development Studio)
    "coding": ("coder", "code", "deepseek", "starcoder", "codestral"),
    # Etiket / menü görseli çözümleme
    "vision": VISION_HINTS,
    # Analitik / sayısal görevler
    "analytical": ("math", "reason", "qwq", "r1", "deepseek"),
    # Gömme (embedding)
    "embedding": ("embed", "bge", "e5", "gte", "nomic"),
}

#: Bir görev için **uygun olmayan** uzmanlaşmış model işaretleri.
#:
#: Bu liste canlı bir kusurdan doğdu: yalnızca olumlu ipuçlarına bakan seçim,
#: genel sommelier sorusu için bir *matematik* modelini seçmiş ve model soruyu
#: matematik problemi sanmıştı. Uzmanlaşmış modeller artık kendi görevleri
#: dışında elenir.
TASK_ANTI_HINTS: dict[str, tuple[str, ...]] = {
    "general": (
        "math",
        "embed",
        "bge-",
        "coder",
        "starcoder",
        "vision",
        "-vl",
        "vl-",
        "llava",
        "moondream",
        "rerank",
    ),
    "coding": ("math", "embed", "vision", "llava", "moondream", "rerank"),
    "vision": ("math", "embed", "coder", "rerank"),
    "analytical": ("embed", "vision", "llava", "moondream", "rerank"),
    "embedding": ("chat", "instruct", "coder", "vision"),
}

#: Alan dışı modeller: kurulu olsalar bile genel görevlerde önerilmez.
#: (Örn. tıbbi alana özel modeller restoran/şarap görevleri için uygun değildir.)
OFF_DOMAIN_HINTS: tuple[str, ...] = (
    "biomistral",
    "medalpaca",
    "meditron",
    "clinical",
    "pubmed",
    "biogpt",
)


class LMStudioProvider(OpenAICompatibleProvider):
    """LM Studio yerel API adaptörü."""

    name = "lmstudio"
    is_local = True
    #: LM Studio anahtar istemez; yine de bazı kurulumlar sahte bir anahtar bekler.
    requires_api_key = False

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("base_url", "http://localhost:1234/v1")
        kwargs.setdefault("api_key", "lm-studio")
        super().__init__(**kwargs)

    def _parse_model_entry(self, model_id: str, entry: dict[str, Any]) -> ModelInfo:
        info = super()._parse_model_entry(model_id, entry)
        # LM Studio bazı sürümlerde yükleme durumunu bildirir.
        state = str(entry.get("state") or entry.get("status") or "").lower()
        if state:
            info.is_loaded = state in {"loaded", "ready", "loaded-idle"}
        max_context = entry.get("max_context_length") or entry.get("loaded_context_length")
        if max_context:
            info.context_length = int(max_context)
        return info

    def list_models(self) -> list[ModelInfo]:
        """Modelleri okur; sunucu kapalıysa yol gösterici hata üretir."""
        try:
            return super().list_models()
        except ProviderUnavailableError as exc:
            raise ProviderUnavailableError(
                "LM Studio sunucusuna ulaşılamadı.\n"
                "Kontrol listesi:\n"
                "  1. LM Studio uygulaması açık mı?\n"
                "  2. 'Developer' → 'Start Server' ile yerel sunucu başlatıldı mı?\n"
                f"  3. Adres doğru mu? (yapılandırılan: {self.base_url})\n"
                "  4. En az bir model yüklendi mi?",
                provider=self.name,
                detail=exc.detail,
            ) from exc

    def loaded_models(self) -> list[ModelInfo]:
        """Yalnızca belleğe yüklenmiş (kullanıma hazır) modelleri döndürür."""
        return [model for model in self.list_models() if model.is_loaded]

    def suggest_model(self, task: str = "general", *, allow_off_domain: bool = False) -> str:
        """Göreve en uygun yüklü modeli önerir.

        Seçim tamamen *çalışan sunucudan okunan* listeye dayanır. Uygun aday
        bulunamazsa ilk yüklü model döndürülür; hiç model yoksa hata verilir.

        Args:
            task: ``TASK_HINTS`` anahtarlarından biri.
            allow_off_domain: ``True`` ise alan dışı modeller de değerlendirilir.
        """
        models = self.list_models()
        if not models:
            raise ProviderUnavailableError(
                "LM Studio'da yüklü model bulunamadı. Lütfen bir model yükleyin.",
                provider=self.name,
            )

        candidates = [model for model in models if model.is_loaded] or models

        if not allow_off_domain:
            on_domain = [
                model
                for model in candidates
                if not any(hint in model.id.lower() for hint in OFF_DOMAIN_HINTS)
            ]
            candidates = on_domain or candidates

        hints = TASK_HINTS.get(task, TASK_HINTS["general"])
        anti_hints = TASK_ANTI_HINTS.get(task, TASK_ANTI_HINTS["general"])

        def score(model: ModelInfo) -> tuple[int, int, int]:
            """(uygunluk, ipucu_eşleşmesi, bağlam) — büyük olan kazanır."""
            lowered = model.id.lower()

            # 1) Uygunluk: göreve aykırı uzmanlık taşıyan modeller elenir.
            #    Bu, "genel sohbet için matematik modeli seçme" hatasını önler.
            suitability = 0 if any(anti in lowered for anti in anti_hints) else 1

            # Görsel görevde sağlayıcı görsel desteği bildirmiyorsa uygun değildir.
            if task == "vision" and not model.supports_vision:
                suitability = 0

            # 2) İpucu eşleşme sayısı
            hint_score = sum(1 for hint in hints if hint in lowered)

            return (suitability, hint_score, model.context_length or 0)

        best = max(candidates, key=score)
        logger.info(
            "LM Studio model önerisi: görev=%s seçilen=%s (aday sayısı=%s)",
            task,
            best.id,
            len(candidates),
        )
        return best.id

    def health_check(self):  # type: ignore[override]
        """Sağlık kontrolüne 'yüklü model var mı' bilgisini ekler."""
        health = super().health_check()
        if health.reachable:
            loaded = [model for model in self.list_models() if model.is_loaded]
            if not loaded:
                health.message = (
                    "LM Studio çalışıyor ancak belleğe yüklü model yok. "
                    "LM Studio'da bir model yükleyin."
                )
            else:
                health.message = f"LM Studio çalışıyor · {len(loaded)} model yüklü."
        return health
