"""Wine House — test ayarları.

Hızlı, yalıtılmış ve tamamen çevrimdışı test koşumu:
  * bellek içi SQLite
  * hızlı parola hash'i
  * yalnızca Mock AI sağlayıcısı (hiçbir ağ çağrısı yapılmaz)
"""

from __future__ import annotations

from base64 import urlsafe_b64encode as _urlsafe_b64encode
from hashlib import sha256 as _sha256

from .base import *  # noqa: F403
from .base import AI_SETTINGS, BASE_DIR, LOGGING

DEBUG = False
TESTING = True

ALLOWED_HOSTS = ["*"]

SECRET_KEY = "test-only-secret-key-not-used-in-production"  # noqa: S105

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "OPTIONS": {"init_command": "PRAGMA foreign_keys=ON;"},
    }
}

# Testlerde parola hash'i hızlandırılır.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Test sırasında migration'lar çalıştırılır (şema doğruluğunu da sınar).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# --- Yapay zekâ: testlerde YALNIZCA mock; ağ erişimi yok ---
AI_SETTINGS = {
    **AI_SETTINGS,
    "DEFAULT_PROVIDER": "mock",
    "FALLBACK_ORDER": ["mock"],
    "LOCAL_ONLY": True,
    "PRIVACY_MODE": True,
}

# --- AI Development Studio testlerde açık ama komut çalıştırma kapalı ---
DEVSTUDIO = {
    "ENABLED": True,
    "WORKSPACE": BASE_DIR,
    "ALLOW_COMMANDS": False,
}

# --- Test şifreleme anahtarı ---
# Anahtar depoda LİTERAL OLARAK TUTULMAZ; sabit bir test tohumundan her koşumda
# yeniden türetilir. Böylece:
#   * depoda Fernet biçimli bir anahtar dizgesi bulunmaz (gizli anahtar
#     tarayıcıları tetiklenmez ve değer yanlışlıkla üretimde kullanılamaz),
#   * testler yine belirlenimcidir (aynı tohum → aynı anahtar).
# ÜRETİMDE bu dosya kullanılmaz; gerçek anahtar WINEHOUSE_FIELD_ENCRYPTION_KEY
# ortam değişkeninden okunur (bkz. .env.example).
FIELD_ENCRYPTION_KEY = _urlsafe_b64encode(
    _sha256(b"winehouse-test-suite-deterministic-seed-not-a-real-key").digest()
).decode()

BACKUP_DIR = BASE_DIR / "var" / "test-backups"

# Test çıktısını sadeleştir: hiçbir günlük dosyası oluşturulmaz.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": LOGGING["filters"],
    "formatters": LOGGING["formatters"],
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["mask_secrets"],
        }
    },
    "root": {"handlers": ["console"], "level": "ERROR"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "winehouse.ai": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "winehouse.security": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "winehouse.devstudio": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
