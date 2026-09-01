# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller yapılandırması — Wine House.

Kullanım:
    .venv\\Scripts\\python.exe -m PyInstaller winehouse.spec --noconfirm
    (önce: scripts\\build_exe.ps1 — statikleri üretim ayarlarıyla toplar)

Taşınabilirlik: tüm yollar SPECPATH'e görelidir; makineye özgü mutlak yol
yoktur. Aynı spec macOS CI'da da çalışır — Windows'a özgü ikon yalnızca
Windows'ta ve dosya mevcutsa eklenir.

Django'yu paketlerken üç konu özel dikkat ister:

1. **src/ yerleşimi**: `winehouse` ve `apps` paketleri `src/` altındadır;
   hem statik çözümleme (pathex) hem de collect_submodules çağrıları için
   `src/` arama yoluna eklenir.
2. **Veri dosyaları**: şablonlar, statikler ve .env.example Python modülü
   olmadıkları için otomatik toplanmaz; açıkça eklenir.
3. **Yazılabilir veri**: veritabanı/medya/günlük paketin geçici açılma
   dizinine değil exe'nin yanına yazılır (bkz. src/winehouse/settings/base.py
   DATA_DIR — bu olmadan her kapanışta tüm veri silinirdi).
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

PROJECT = Path(SPECPATH)
SRC = PROJECT / "src"

# collect_submodules ve Analysis, src/ altındaki paketleri bulabilsin
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# ------------------------------------------------------------------
#  Veri dosyaları
# ------------------------------------------------------------------
datas = [
    (str(SRC / "templates"), "templates"),
    (str(SRC / "static"), "static"),
    # collectstatic (üretim ayarları) çıktısı: hash'li adlar + manifest.
    # build_exe.ps1 bunu paketlemeden önce üretir.
    (str(PROJECT / "staticfiles"), "staticfiles"),
    (str(PROJECT / ".env.example"), "."),
]

# Çeviri katalogları (varsa). Boş dizin eklemek PyInstaller'ı yanıltmasın.
_locale = SRC / "locale"
if _locale.is_dir() and any(_locale.rglob("*.mo")):
    datas.append((str(_locale), "locale"))

# Django'nun kendi şablon/çeviri dosyaları (admin arayüzü, hata sayfaları)
datas += collect_data_files("django", include_py_files=False)
datas += collect_data_files("rest_framework", include_py_files=False)
datas += collect_data_files("django_htmx", include_py_files=False)

# ------------------------------------------------------------------
#  Gizli içe aktarmalar
# ------------------------------------------------------------------
hiddenimports = [
    # Veritabanı arka ucu (ayarlarda dize olarak seçilir)
    "django.db.backends.sqlite3",
    "django.db.backends.sqlite3.base",
    # Şifreleme / oturum / statik depolama
    "django.contrib.auth.hashers",
    "django.contrib.sessions.backends.db",
    "django.contrib.staticfiles.storage",
    "whitenoise.storage",
    "whitenoise.middleware",
    # Raporlama
    "reportlab.pdfbase._fontdata",
    "openpyxl",
    # AI sağlayıcıları
    "httpx",
    "httpcore",
    # Barkod / QR
    "qrcode",
]

# Proje paketleri: migration'lar, sinyaller, admin ve yönetim komutları
# dinamik yüklenir; statik çözümleyici göremez.
for package in ["winehouse", "apps"]:
    hiddenimports += collect_submodules(package)

# Django ve üçüncü taraf uygulamalar da dinamik yüklenir
for package in [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "rest_framework.authtoken",
    "django_htmx",
    # WhiteNoise ara katmanı ayarlarda dize olarak referanslanır
    "whitenoise",
]:
    hiddenimports += collect_submodules(package)

hiddenimports = sorted(set(hiddenimports))

# ------------------------------------------------------------------
#  Analiz
# ------------------------------------------------------------------
a = Analysis(
    ["launcher.py"],
    pathex=[str(PROJECT), str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Paketi gereksiz büyüten, çalışma zamanında kullanılmayan bileşenler
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "IPython",
        "jupyter",
        "pytest",
        "_pytest",
        "mypy",
        "black",
        "ruff",
        "bandit",
        "pip_audit",
        "pre_commit",
        "setuptools._distutils",
        # Sunum/belge araçları yalnızca geliştirme tarafındadır
        # (scripts/make_presentation.py). lxml, python-pptx bağımlılığıdır
        # ve pakete girerse ~4 MB gereksiz yer kaplar.
        "pptx",
        "pypdf",
        "lxml",
        # PostgreSQL isteğe bağlıdır; paket SQLite ile çalışır
        "psycopg",
        "psycopg2",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# ------------------------------------------------------------------
#  Platforma göre ikon (spec taşınabilir kalsın)
# ------------------------------------------------------------------
if sys.platform == "win32":
    _icon_file = PROJECT / "assets" / "winehouse.ico"
elif sys.platform == "darwin":
    _icon_file = PROJECT / "assets" / "winehouse.icns"
else:
    _icon_file = None
_icon = str(_icon_file) if (_icon_file and _icon_file.is_file()) else None

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Wine House",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX bazı virüs tarayıcılarında yanlış alarm üretir
    runtime_tmpdir=None,
    console=True,  # sunucu durumu, kurulum sihirbazı ve Ctrl+C için gerekli
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)
