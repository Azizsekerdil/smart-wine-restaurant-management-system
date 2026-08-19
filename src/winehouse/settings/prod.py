"""Wine House — üretim ayarları.

Güvenlik başlıkları açık, DEBUG kapalı, gizli anahtar zorunlu.
Tek işletme içi ağda HTTPS olmadan çalıştırılabilmesi için TLS zorlaması
``WINEHOUSE_FORCE_HTTPS`` ile denetlenir (varsayılan: kapalı, yerel kurulum).
"""

from __future__ import annotations

import os

from .base import *  # noqa: F403
from .base import env, env_bool, env_list

DEBUG = False

# Üretimde gizli anahtar zorunludur; otomatik üretilen geçici anahtar kabul edilmez.
SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY tanımlı değil. Üretim modunda gizli anahtar zorunludur.\n"
        'Üretmek için: python -c "import secrets; print(secrets.token_urlsafe(64))"\n'
        "Değeri .env dosyasına DJANGO_SECRET_KEY=... olarak ekleyin."
    )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

# --- Güvenlik başlıkları ---
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# İşletme içi kurulumda HTTPS olmayabilir; açıkça istenirse zorlanır.
FORCE_HTTPS = env_bool("WINEHOUSE_FORCE_HTTPS", default=False)
SECURE_SSL_REDIRECT = FORCE_HTTPS
SESSION_COOKIE_SECURE = FORCE_HTTPS
CSRF_COOKIE_SECURE = FORCE_HTTPS
if FORCE_HTTPS:
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- AI Development Studio üretimde VARSAYILAN OLARAK KAPALI ---
DEVSTUDIO = {
    **globals()["DEVSTUDIO"],
    "ENABLED": env_bool("WINEHOUSE_DEVSTUDIO_ENABLED", default=False),
    "ALLOW_COMMANDS": env_bool("WINEHOUSE_DEVSTUDIO_ALLOW_COMMANDS", default=False),
}

# --- Canlı ödeme / e-Fatura yalnızca açık onayla ---
PAYMENT_MODE = env("WINEHOUSE_PAYMENT_MODE", "sandbox")
EINVOICE_MODE = env("WINEHOUSE_EINVOICE_MODE", "sandbox")

EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
