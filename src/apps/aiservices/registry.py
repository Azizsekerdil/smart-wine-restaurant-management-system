"""Sağlayıcı kayıt defteri ve anahtar çözümleme.

Uygulama kodu sağlayıcıları **yalnızca** buradan alır::

    provider = get_provider("lmstudio")
    chain = build_fallback_chain()

API anahtarları şu öncelikle çözülür:
  1. Veritabanındaki şifreli ayar (``AppSetting``, ``is_secret=True``)
  2. Ortam değişkeni (``.env`` veya sistem ortamı)

Anahtarlar hiçbir zaman günlüğe yazılmaz ve arayüze yalnızca kısaltılmış
(``sk-a…9f2c``) biçimde gönderilir.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from django.conf import settings

from apps.aiservices.providers.anthropic import AnthropicProvider
from apps.aiservices.providers.base import AIProvider
from apps.aiservices.providers.lmstudio import LMStudioProvider
from apps.aiservices.providers.mock import MockProvider
from apps.aiservices.providers.nvidia import NvidiaProvider

logger = logging.getLogger("winehouse.ai")

PROVIDER_CLASSES: dict[str, type[AIProvider]] = {
    "lmstudio": LMStudioProvider,
    "anthropic": AnthropicProvider,
    "nvidia": NvidiaProvider,
    "mock": MockProvider,
}

#: Ayarlar ekranında gösterilen okunur adlar
PROVIDER_LABELS: dict[str, str] = {
    "lmstudio": "LM Studio (yerel)",
    "anthropic": "Anthropic Claude (bulut)",
    "nvidia": "NVIDIA (bulut)",
    "mock": "Mock (test / çevrimdışı)",
}


class UnknownProviderError(ValueError):
    """Tanımsız sağlayıcı kodu istendiğinde yükseltilir."""


def _provider_settings(code: str) -> dict[str, Any]:
    """Sağlayıcının ayar sözlüğünü döndürür."""
    providers = getattr(settings, "AI_SETTINGS", {}).get("PROVIDERS", {})
    if code not in providers:
        raise UnknownProviderError(
            f"Tanımsız yapay zekâ sağlayıcısı: {code}. "
            f"Tanımlı olanlar: {', '.join(sorted(providers))}"
        )
    return dict(providers[code])


def resolve_api_key(code: str) -> str:
    """Sağlayıcının API anahtarını güvenli kaynaklardan çözer.

    Döndürülen değer **asla** günlüğe veya arayüze düz metin yazılmamalıdır.
    """
    config = _provider_settings(code)
    env_name = config.get("api_key_env") or ""

    # 1) Veritabanındaki şifreli ayar
    try:
        from apps.core.models import AppSetting

        record = (
            AppSetting.objects.filter(key=f"ai.{code}.api_key", is_secret=True)
            .only("secret_value")
            .first()
        )
        if record and record.secret_value:
            return record.secret_value
    except Exception:  # pragma: no cover - migration öncesi / veritabanı yok
        logger.debug("Şifreli anahtar deposu okunamadı (sağlayıcı=%s).", code)

    # 2) Ortam değişkeni
    if env_name:
        return os.environ.get(env_name, "")
    return ""


def get_provider(code: str = "", **overrides: Any) -> AIProvider:
    """Sağlayıcı örneği üretir.

    Args:
        code: Sağlayıcı kodu. Boşsa varsayılan sağlayıcı kullanılır.
        **overrides: ``base_url``, ``model``, ``timeout`` gibi geçici değişiklikler.
    """
    ai_settings = getattr(settings, "AI_SETTINGS", {})
    resolved_code = code or ai_settings.get("DEFAULT_PROVIDER", "mock")

    if resolved_code not in PROVIDER_CLASSES:
        raise UnknownProviderError(
            f"Tanımsız yapay zekâ sağlayıcısı: {resolved_code}. "
            f"Tanımlı olanlar: {', '.join(sorted(PROVIDER_CLASSES))}"
        )

    config = _provider_settings(resolved_code)
    provider_class = PROVIDER_CLASSES[resolved_code]

    kwargs: dict[str, Any] = {
        "base_url": config.get("base_url", ""),
        "model": config.get("model", ""),
        "timeout": int(config.get("timeout", 60)),
        "api_key": resolve_api_key(resolved_code),
    }
    kwargs.update(overrides)
    # Boş base_url'i alt sınıf varsayılanının ezmesine izin ver
    if not kwargs.get("base_url"):
        kwargs.pop("base_url")

    return provider_class(**kwargs)


def available_provider_codes() -> list[str]:
    """Yapılandırmada tanımlı tüm sağlayıcı kodları."""
    return sorted(getattr(settings, "AI_SETTINGS", {}).get("PROVIDERS", {}))


def build_fallback_chain(*, preferred: str = "") -> list[str]:
    """Denenecek sağlayıcı sırasını üretir.

    Kurallar:
      * ``LOCAL_ONLY`` açıkken bulut sağlayıcıları zincire hiç girmez.
      * ``PREFER_LOCAL`` açıkken yerel sağlayıcılar başa alınır.
      * ``mock`` her zaman son çare olarak sonda bulunur; böylece yapay zekâ
        özellikleri hiçbir koşulda çökmez, yalnızca "gerçek model yok"
        uyarısıyla çalışır.
    """
    ai_settings = getattr(settings, "AI_SETTINGS", {})
    configured = list(ai_settings.get("FALLBACK_ORDER") or [])
    providers = ai_settings.get("PROVIDERS", {})

    chain = [code for code in configured if code in PROVIDER_CLASSES]

    if preferred and preferred in PROVIDER_CLASSES:
        chain = [preferred] + [code for code in chain if code != preferred]

    if ai_settings.get("LOCAL_ONLY"):
        chain = [code for code in chain if providers.get(code, {}).get("is_local")]
    elif ai_settings.get("PREFER_LOCAL"):
        local = [code for code in chain if providers.get(code, {}).get("is_local")]
        cloud = [code for code in chain if not providers.get(code, {}).get("is_local")]
        chain = local + cloud

    if "mock" not in chain:
        chain.append("mock")
    else:
        chain = [code for code in chain if code != "mock"] + ["mock"]

    return chain


def health_report() -> list[Any]:
    """Tüm sağlayıcıların sağlık durumunu döndürür (ayarlar ekranı için)."""
    report = []
    for code in available_provider_codes():
        try:
            report.append(get_provider(code).health_check())
        except Exception as exc:  # pragma: no cover - yapılandırma hatası yolu
            from apps.aiservices.providers.base import ProviderHealth

            report.append(
                ProviderHealth(
                    provider=code,
                    reachable=False,
                    message=f"Yapılandırma hatası: {type(exc).__name__}",
                )
            )
    return report
