"""Wine House — ortak Django ayarları.

Tasarım ilkeleri:
  * local-first  : varsayılan kurulum tek makinede, SQLite ile, internetsiz çalışır
  * güvenli-varsayılan : gizli değerler yalnızca ortamdan okunur, koda gömülmez
  * modüler      : her iş alanı ayrı bir Django uygulamasıdır
  * çok dilli    : tüm arayüz metinleri çeviri dosyalarından gelir (TR/EN)
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Yollar
# ---------------------------------------------------------------------------
# base.py -> settings -> winehouse -> src -> PROJE KÖKÜ
SRC_DIR = Path(__file__).resolve().parent.parent.parent
BASE_DIR = SRC_DIR.parent

load_dotenv(BASE_DIR / ".env", override=False)


# ---------------------------------------------------------------------------
# Ortam değişkeni yardımcıları
# ---------------------------------------------------------------------------
def env(key: str, default: str = "") -> str:
    """Ortam değişkenini okur; tanımsızsa varsayılanı döndürür."""
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    return value


def env_bool(key: str, default: bool = False) -> bool:
    """Ortam değişkenini mantıksal değere çevirir."""
    raw = env(key, "").strip().lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "on", "evet", "açık", "acik"}


def env_int(key: str, default: int) -> int:
    """Ortam değişkenini tam sayıya çevirir; hatalıysa varsayılanı döndürür."""
    try:
        return int(env(key, str(default)))
    except ValueError:
        return default


def env_list(key: str, default: str = "") -> list[str]:
    """Virgülle ayrılmış ortam değişkenini listeye çevirir."""
    raw = env(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Temel güvenlik
# ---------------------------------------------------------------------------
# Gizli anahtar yalnızca ortamdan gelir. Geliştirmede tanımsızsa geçici bir
# anahtar üretilir; üretim ayarları (prod.py) bunu hata olarak reddeder.
SECRET_KEY = env("DJANGO_SECRET_KEY") or secrets.token_urlsafe(64)

DEBUG = env_bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

CSRF_TRUSTED_ORIGINS = [
    f"http://{host}:{env_int('WINEHOUSE_PORT', 8000)}"
    for host in ALLOWED_HOSTS
    if host not in {"*"}
]

# ---------------------------------------------------------------------------
# Uygulamalar
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
    "django_htmx",
]

LOCAL_APPS = [
    # Çekirdek: denetim kaydı, ayarlar, ortak taban modeller
    "apps.core",
    # Kullanıcılar, roller, yetkiler
    "apps.accounts",
    # Menü, kategoriler, reçeteler, alerjenler
    "apps.catalog",
    # Dijital şarap kavı, sommelier özellikleri
    "apps.cellar",
    # Tedarikçi, satın alma, stok, fire
    "apps.inventory",
    # Masa, rezervasyon, sipariş, KDS, ödeme
    "apps.operations",
    # Müşteri ilişkileri, sadakat, KVKK
    "apps.crm",
    # Personel, vardiya, performans
    "apps.hr",
    # Raporlar ve dışa aktarım
    "apps.reporting",
    # Yapay zekâ sağlayıcı katmanı
    "apps.aiservices",
    # Human Sovereignty Protocol: pre-action politika + haklar makbuzu
    "apps.hsp",
    # Uyum motoru: lisans/SBOM taraması ve release gate araçları
    "apps.compliance",
    # Güvenli AI Development Studio
    "apps.devstudio",
    # CAIO kendini geliştirme ajanı
    "apps.caio",
    # Yedekleme / geri yükleme
    "apps.backups",
    # Rol bazlı eğitim merkezi
    "apps.training",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Ara katmanlar
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    # Denetim kaydı için istek bağlamını (kullanıcı, IP) taşır
    "apps.core.middleware.AuditContextMiddleware",
    # Parola değişimi zorunluysa parola ekranı dışındaki her yolu kapatır
    "apps.core.middleware.PasswordChangeRequiredMiddleware",
    # PIN oturumunu salon / mutfak / bar ekranlarıyla sınırlar
    "apps.core.middleware.PinSessionScopeMiddleware",
]

ROOT_URLCONF = "winehouse.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [SRC_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "apps.core.context_processors.app_context",
            ],
        },
    },
]

WSGI_APPLICATION = "winehouse.wsgi.application"
ASGI_APPLICATION = "winehouse.asgi.application"

# ---------------------------------------------------------------------------
# Veritabanı
# ---------------------------------------------------------------------------
DB_ENGINE = env("WINEHOUSE_DB_ENGINE", "sqlite").lower()

if DB_ENGINE == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("WINEHOUSE_PG_NAME", "winehouse"),
            "USER": env("WINEHOUSE_PG_USER", "winehouse"),
            "PASSWORD": env("WINEHOUSE_PG_PASSWORD"),
            "HOST": env("WINEHOUSE_PG_HOST", "127.0.0.1"),
            "PORT": env("WINEHOUSE_PG_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    sqlite_path = Path(env("WINEHOUSE_SQLITE_PATH", "var/winehouse.sqlite3"))
    if not sqlite_path.is_absolute():
        sqlite_path = BASE_DIR / sqlite_path
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(sqlite_path),
            "OPTIONS": {
                # Çevrimdışı/tek makine kullanımında eşzamanlı okuma başarımı
                "init_command": "PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;",
                "transaction_mode": "IMMEDIATE",
                "timeout": 20,
            },
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Kimlik doğrulama
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Parola karma algoritması ---
# Birincil algoritma Argon2id'dir (OWASP'ın parola saklama için birinci
# önerisi). PBKDF2 listede kalır ki eski kurulumlardan gelen karmalar hâlâ
# doğrulanabilsin; Django bu karmaları ilk başarılı girişte sessizce Argon2'ye
# yükseltir. Parolalar hiçbir koşulda düz metin saklanmaz.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

SESSION_COOKIE_AGE = 60 * 60 * 12  # 12 saat - tek vardiya
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # HTMX'in başlık göndermesi için okunabilir olmalı

# ---------------------------------------------------------------------------
# Uluslararasılaştırma (TR / EN)
# ---------------------------------------------------------------------------
LANGUAGE_CODE = env("WINEHOUSE_DEFAULT_LANGUAGE", "tr")
TIME_ZONE = env("WINEHOUSE_TIME_ZONE", "Europe/Istanbul")
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ("tr", "Türkçe"),
    ("en", "English"),
]

LOCALE_PATHS = [SRC_DIR / "locale"]

# Türkçe para ve tarih biçimleri
WINEHOUSE_CURRENCY = env("WINEHOUSE_CURRENCY", "TRY")
WINEHOUSE_CURRENCY_SYMBOL = env("WINEHOUSE_CURRENCY_SYMBOL", "₺")

# ---------------------------------------------------------------------------
# Statik ve medya dosyaları
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [SRC_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "2000/hour",
        "anon": "60/hour",
        "ai": "120/hour",
    },
}

# ---------------------------------------------------------------------------
# Veri koruma / şifreleme
# ---------------------------------------------------------------------------
# Hassas alan şifreleme anahtarı (Fernet). Boşsa şifreleme devre dışıdır ve
# uygulama başlangıçta uyarı verir.
FIELD_ENCRYPTION_KEY = env("WINEHOUSE_FIELD_ENCRYPTION_KEY")

BACKUP_DIR = Path(env("WINEHOUSE_BACKUP_DIR", "backups"))
if not BACKUP_DIR.is_absolute():
    BACKUP_DIR = BASE_DIR / BACKUP_DIR

BACKUP_ENCRYPTION = env_bool("WINEHOUSE_BACKUP_ENCRYPTION", default=True)
BACKUP_RETENTION_DAYS = env_int("WINEHOUSE_BACKUP_RETENTION_DAYS", 30)

# KVKK / GDPR veri saklama politikası (gün)
DATA_RETENTION_DAYS = {
    "audit_log": env_int("WINEHOUSE_RETENTION_AUDIT_DAYS", 365 * 2),
    "ai_call_log": env_int("WINEHOUSE_RETENTION_AI_LOG_DAYS", 180),
    "customer_inactive": env_int("WINEHOUSE_RETENTION_CUSTOMER_DAYS", 365 * 3),
}

# ---------------------------------------------------------------------------
# Yapay zekâ yapılandırması
# ---------------------------------------------------------------------------
AI_SETTINGS = {
    "DEFAULT_PROVIDER": env("WINEHOUSE_AI_DEFAULT_PROVIDER", "lmstudio"),
    "PREFER_LOCAL": env_bool("WINEHOUSE_AI_PREFER_LOCAL", default=True),
    "FALLBACK_ORDER": env_list("WINEHOUSE_AI_FALLBACK_ORDER", "lmstudio,anthropic,nvidia,mock"),
    "PRIVACY_MODE": env_bool("WINEHOUSE_AI_PRIVACY_MODE", default=True),
    "LOCAL_ONLY": env_bool("WINEHOUSE_AI_LOCAL_ONLY", default=False),
    "MONTHLY_COST_LIMIT_USD": env_int("WINEHOUSE_AI_MONTHLY_COST_LIMIT_USD", 10),
    "PROVIDERS": {
        "lmstudio": {
            "base_url": env("WINEHOUSE_LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
            "model": env("WINEHOUSE_LMSTUDIO_MODEL"),
            "timeout": env_int("WINEHOUSE_LMSTUDIO_TIMEOUT", 60),
            "api_key_env": "WINEHOUSE_LMSTUDIO_API_KEY",
            "is_local": True,
        },
        "anthropic": {
            "base_url": env("WINEHOUSE_ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
            "model": env("WINEHOUSE_ANTHROPIC_MODEL"),
            "timeout": env_int("WINEHOUSE_ANTHROPIC_TIMEOUT", 60),
            "api_key_env": "ANTHROPIC_API_KEY",
            "is_local": False,
        },
        "nvidia": {
            "base_url": env("WINEHOUSE_NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            "model": env("WINEHOUSE_NVIDIA_MODEL"),
            "timeout": env_int("WINEHOUSE_NVIDIA_TIMEOUT", 60),
            "api_key_env": "NVIDIA_API_KEY",
            "is_local": False,
        },
        "mock": {
            "base_url": "",
            "model": "winehouse-mock-1",
            "timeout": 5,
            "api_key_env": "",
            "is_local": True,
        },
    },
}

# ---------------------------------------------------------------------------
# AI Development Studio (geliştirici terminali) — üretimde varsayılan KAPALI
# ---------------------------------------------------------------------------
DEVSTUDIO = {
    "ENABLED": env_bool("WINEHOUSE_DEVSTUDIO_ENABLED", default=False),
    "WORKSPACE": Path(env("WINEHOUSE_DEVSTUDIO_WORKSPACE", str(BASE_DIR))).resolve(),
    "ALLOW_COMMANDS": env_bool("WINEHOUSE_DEVSTUDIO_ALLOW_COMMANDS", default=False),
}

# ---------------------------------------------------------------------------
# Ödeme / mali entegrasyon — canlı mod kullanıcı onayı olmadan açılmaz
# ---------------------------------------------------------------------------
PAYMENT_MODE = env("WINEHOUSE_PAYMENT_MODE", "sandbox")
EINVOICE_MODE = env("WINEHOUSE_EINVOICE_MODE", "sandbox")

# ---------------------------------------------------------------------------
# Günlükleme
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        # API anahtarlarını ve gizli değerleri log çıktısından maskeler
        "mask_secrets": {"()": "apps.core.logging_filters.SecretMaskingFilter"},
    },
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name}: {message}",
            "style": "{",
        },
        "simple": {"format": "[{levelname}] {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["mask_secrets"],
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "winehouse.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "verbose",
            "filters": ["mask_secrets"],
        },
        "ai_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "ai.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "encoding": "utf-8",
            "formatter": "verbose",
            "filters": ["mask_secrets"],
        },
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "security.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 10,
            "encoding": "utf-8",
            "formatter": "verbose",
            "filters": ["mask_secrets"],
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "winehouse.ai": {
            "handlers": ["console", "ai_file"],
            "level": "INFO",
            "propagate": False,
        },
        "winehouse.security": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
        "winehouse.devstudio": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
