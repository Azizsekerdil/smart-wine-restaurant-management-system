#!/usr/bin/env bash
# Wine House — macOS paketleme betiği.
#
# Sıra önemlidir (scripts/build_exe.ps1 ile aynı mantık):
#   1. Bağımlılıklar + PyInstaller kurulur
#   2. İkon üretilir (Pillow ile PNG -> sips + iconutil ile .icns)
#   3. Statik dosyalar ÜRETİM AYARLARIYLA toplanır (staticfiles.json
#      manifestosu pakete girmezse uygulama her sayfada 500 verir)
#   4. PyInstaller taşınabilir winehouse.spec ile paketi oluşturur
#
# NOT: macOS'un sistem bash'i 3.2'dir; "set -u" bilerek KULLANILMAZ
# (boş dizi açılımını unbound sayar).
set -eo pipefail

cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "HATA: macOS paketi bir Mac üzerinde oluşturulmalıdır."
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r requirements.txt
"$PYTHON_BIN" -m pip install "pyinstaller==6.16.0"

rm -rf build/macos "dist/Wine House" "dist/Wine House-macOS.zip"
mkdir -p build/macos

# ------------------------------------------------------------------ İkon
# Depoda PNG kaynağı yok; Windows ikonuyla aynı görsel dili kullanan PNG
# Pillow ile üretilir, sips + iconutil ile .icns'e çevrilir. winehouse.spec
# darwin'de assets/winehouse.icns dosyasını (varsa) otomatik kullanır;
# ikon üretilemezse paket ikonsuz devam eder.
if command -v sips >/dev/null && command -v iconutil >/dev/null; then
  if "$PYTHON_BIN" -c '
import sys
sys.path.insert(0, "scripts")
from make_icon import draw_goblet, rounded_background
image = rounded_background(1024)
draw_goblet(image, 1024)
image.save("build/macos/winehouse_1024.png")
'; then
    ICONSET="build/macos/WineHouse.iconset"
    mkdir -p "$ICONSET"
    for size in 16 32 128 256 512; do
      sips -z "$size" "$size" build/macos/winehouse_1024.png \
        --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
      double=$((size * 2))
      sips -z "$double" "$double" build/macos/winehouse_1024.png \
        --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
    done
    iconutil -c icns "$ICONSET" -o "$PROJECT_ROOT/assets/winehouse.icns"
    echo "İkon üretildi: assets/winehouse.icns"
  else
    echo "UYARI: ikon PNG'si üretilemedi; paket ikonsuz devam ediyor."
  fi
fi

# ------------------------------------------------------------------ Statikler
# KRİTİK: üretim ayarları + DEBUG=False olmalı. Aksi hâlde düz depolama
# kullanılır, staticfiles.json üretilmez ve paketlenmiş uygulama çalışma
# anında "Missing staticfiles manifest entry" hatası verir.
export DJANGO_SETTINGS_MODULE="winehouse.settings.prod"
export DJANGO_DEBUG="False"
export DJANGO_SECRET_KEY="build-time-only-not-a-real-secret"

"$PYTHON_BIN" manage.py collectstatic --noinput --clear

unset DJANGO_SETTINGS_MODULE DJANGO_DEBUG DJANGO_SECRET_KEY

if [[ ! -f staticfiles/staticfiles.json ]]; then
  echo "HATA: staticfiles.json üretilmedi; paket statik dosyaları sunamaz."
  exit 1
fi

# ------------------------------------------------------------------ Paketleme
# winehouse.spec SPECPATH'e göreli ve taşınabilirdir; tüm --add-data
# eşdeğerleri spec içinde mutlak yola çevrilir. Konsollu tek dosya üretir
# (--windowed KULLANILMAZ: ilk kurulum sihirbazı ve sunucu durumu konsol
# ister).
"$PYTHON_BIN" -m PyInstaller winehouse.spec --noconfirm --clean

APP_PATH="dist/Wine House"
if [[ ! -f "$APP_PATH" ]]; then
  echo "HATA: $APP_PATH oluşturulamadı."
  exit 1
fi

ditto -c -k --keepParent "$APP_PATH" "dist/Wine House-macOS.zip"
echo "Tamamlandı: $APP_PATH"
echo "Dağıtım ZIP'i: dist/Wine House-macOS.zip"
