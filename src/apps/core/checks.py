"""Django sistem kontrolleri.

``python manage.py check`` çalıştırıldığında güvenlik ve yapılandırma
eksiklikleri açıkça raporlanır. Amaç, sessiz güvensiz kurulumları önlemektir.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import Error, Warning, register


@register("winehouse")
def check_encryption_key(app_configs: Any, **kwargs: Any) -> list[Any]:
    """Hassas alan şifreleme anahtarının varlığını denetler."""
    problems: list[Any] = []
    if not getattr(settings, "FIELD_ENCRYPTION_KEY", ""):
        problems.append(
            Warning(
                "Hassas alan şifreleme anahtarı tanımlı değil; kişisel veriler "
                "veritabanında düz metin saklanacak.",
                hint=(
                    "Anahtar üretin ve .env dosyasına ekleyin:\n"
                    '  python -c "from cryptography.fernet import Fernet; '
                    'print(Fernet.generate_key().decode())"\n'
                    "  WINEHOUSE_FIELD_ENCRYPTION_KEY=..."
                ),
                id="winehouse.W001",
            )
        )
    return problems


@register("winehouse")
def check_devstudio_safety(app_configs: Any, **kwargs: Any) -> list[Any]:
    """AI Development Studio'nun üretimde güvenli yapılandırıldığını denetler."""
    problems: list[Any] = []
    devstudio = getattr(settings, "DEVSTUDIO", {})
    if not settings.DEBUG and devstudio.get("ENABLED"):
        problems.append(
            Warning(
                "AI Development Studio üretim modunda AÇIK. Bu modül kod "
                "değişikliği önerebilir ve yalnızca geliştirme ortamında "
                "açılmalıdır.",
                hint="WINEHOUSE_DEVSTUDIO_ENABLED=False yapın.",
                id="winehouse.W002",
            )
        )
    workspace = devstudio.get("WORKSPACE")
    if workspace and not str(workspace).strip():
        problems.append(
            Error(
                "AI Development Studio çalışma alanı tanımsız.",
                hint="WINEHOUSE_DEVSTUDIO_WORKSPACE değerini ayarlayın.",
                id="winehouse.E001",
            )
        )
    return problems


@register("winehouse")
def check_payment_mode(app_configs: Any, **kwargs: Any) -> list[Any]:
    """Canlı ödeme/e-Fatura modunun kazara açılmadığını denetler."""
    problems: list[Any] = []
    if getattr(settings, "PAYMENT_MODE", "sandbox") != "sandbox":
        problems.append(
            Warning(
                "Ödeme modu 'sandbox' değil. Canlı ödeme altyapısı bu sürümde "
                "yalnızca adaptör arayüzü olarak bulunur ve gerçek işlem yapmaz.",
                hint="WINEHOUSE_PAYMENT_MODE=sandbox olarak bırakın.",
                id="winehouse.W003",
            )
        )
    if getattr(settings, "EINVOICE_MODE", "sandbox") != "sandbox":
        problems.append(
            Warning(
                "e-Fatura modu 'sandbox' değil. Kamu entegrasyonu bu sürümde "
                "yalnızca adaptör arayüzü olarak bulunur.",
                hint="WINEHOUSE_EINVOICE_MODE=sandbox olarak bırakın.",
                id="winehouse.W004",
            )
        )
    return problems


@register("winehouse")
def check_ai_privacy(app_configs: Any, **kwargs: Any) -> list[Any]:
    """Bulut yapay zekâ kullanımında gizlilik modunun açık olduğunu denetler."""
    problems: list[Any] = []
    ai = getattr(settings, "AI_SETTINGS", {})
    cloud_providers = {"anthropic", "nvidia"}
    fallback = set(ai.get("FALLBACK_ORDER", []))
    uses_cloud = bool(cloud_providers & fallback) or ai.get("DEFAULT_PROVIDER") in cloud_providers
    if uses_cloud and not ai.get("PRIVACY_MODE", True):
        problems.append(
            Warning(
                "Bulut yapay zekâ sağlayıcısı etkin ancak gizlilik modu kapalı. "
                "Kişisel veriler maskelenmeden gönderilebilir.",
                hint="WINEHOUSE_AI_PRIVACY_MODE=True yapın.",
                id="winehouse.W005",
            )
        )
    return problems
