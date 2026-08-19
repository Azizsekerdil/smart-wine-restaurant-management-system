"""Wine House — geliştirme ayarları.

Tek makine, SQLite, DEBUG açık. İnternet bağlantısı gerektirmez.
"""

from __future__ import annotations

from .base import *  # noqa: F403
from .base import BASE_DIR, INSTALLED_APPS, env_bool  # noqa: F401

DEBUG = env_bool("DJANGO_DEBUG", default=True)

# Yalnizca yerel makine. "0.0.0.0" bir Host basligi degeri degildir; listede
# bulunmasi sunucuyu aga acmaz ama yaniltici oldugu icin cikarilmistir.
# Gelistirme sunucusunu bilerek aga acmak gerekirse konagi bu listeye
# acikca ekleyin (DEBUG=True iken hata ayiklama izleri gorunur).
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INTERNAL_IPS = ["127.0.0.1"]

# Geliştirmede e-posta konsola yazılır; dışarıya hiçbir şey gönderilmez.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Geliştirmede manifest depolaması collectstatic gerektirir; sade depolama kullan.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Geliştirmede AI Development Studio açılabilir (üretimde varsayılan kapalı).
DEVSTUDIO = {
    **globals()["DEVSTUDIO"],
    "ENABLED": env_bool("WINEHOUSE_DEVSTUDIO_ENABLED", default=True),
}
