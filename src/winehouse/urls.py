"""Wine House — kök URL yapılandırması.

Arayüz URL'leri dil öneki olmadan çalışır; dil seçimi oturum/çerez üzerinden
``LocaleMiddleware`` tarafından belirlenir. Böylece TR/EN geçişi mevcut
sayfadan ayrılmadan yapılabilir.
"""

from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # --- Django yönetim paneli (yalnızca sistem yöneticisi) ---
    path("django-admin/", admin.site.urls),
    # --- Dil değiştirme (django.views.i18n.set_language) ---
    path("i18n/", include("django.conf.urls.i18n")),
    # --- Kimlik doğrulama ve kullanıcı yönetimi ---
    path("hesap/", include("apps.accounts.urls", namespace="accounts")),
    # --- Menü / reçete ---
    path("menu/", include("apps.catalog.urls", namespace="catalog")),
    # --- Şarap kavı ---
    path("kav/", include("apps.cellar.urls", namespace="cellar")),
    # --- Stok / satın alma ---
    path("stok/", include("apps.inventory.urls", namespace="inventory")),
    # --- Salon operasyonu: masa, rezervasyon, sipariş, KDS, ödeme ---
    path("operasyon/", include("apps.operations.urls", namespace="operations")),
    # --- Müşteri ilişkileri ---
    path("musteri/", include("apps.crm.urls", namespace="crm")),
    # --- Personel ---
    path("personel/", include("apps.hr.urls", namespace="hr")),
    # --- Raporlar ---
    path("rapor/", include("apps.reporting.urls", namespace="reporting")),
    # --- Yapay zekâ ---
    path("yapay-zeka/", include("apps.aiservices.urls", namespace="aiservices")),
    # --- AI Development Studio (yalnızca geliştirici/yönetici) ---
    path("dev-studio/", include("apps.devstudio.urls", namespace="devstudio")),
    # --- CAIO ajanı ---
    path("caio/", include("apps.caio.urls", namespace="caio")),
    # --- Yedekleme / geri yükleme ---
    path("yedek/", include("apps.backups.urls", namespace="backups")),
    # --- Eğitim merkezi ---
    path("egitim/", include("apps.training.urls", namespace="training")),
    # --- REST API ---
    path("api/v1/", include("winehouse.api_urls")),
    # --- Ana panel ve genel sayfalar (en sonda: kök yolu yakalar) ---
    path("", include("apps.core.urls", namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Yönetim paneli başlıkları
admin.site.site_header = "Wine House — Sistem Yönetimi"
admin.site.site_title = "Wine House"
admin.site.index_title = "Veri Yönetimi"
