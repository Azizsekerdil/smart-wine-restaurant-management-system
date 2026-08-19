<#
.SYNOPSIS
    Wine House — Akıllı Şarap Restoranı Yönetim Sistemi kurulum betiği.

.DESCRIPTION
    Bu betik Windows üzerinde sıfırdan kurulum yapar:
      1. Python sürümünü denetler
      2. Sanal ortam oluşturur
      3. Bağımlılıkları kurar
      4. .env dosyasını üretir (gizli anahtarlar otomatik oluşturulur)
      5. Veritabanı şemasını kurar
      6. Rolleri eşitler
      7. İlk yöneticiyi oluşturma sihirbazını başlatır
      8. İsteğe bağlı örnek veri yükler

    Kurulum internet bağlantısı gerektirir (yalnızca bağımlılıklar için).
    Hiçbir API anahtarı istemez; sistem yapay zekâ olmadan da tam çalışır.

.PARAMETER SkipDemoData
    Sentetik örnek veri yüklemeyi atlar.

.PARAMETER SkipAdmin
    İlk yönetici oluşturma adımını atlar.

.PARAMETER PythonPath
    Kullanılacak Python yorumlayıcısının tam yolu.

.EXAMPLE
    .\INSTALL_WINE_HOUSE.ps1

.EXAMPLE
    .\INSTALL_WINE_HOUSE.ps1 -SkipDemoData
#>

[CmdletBinding()]
param(
    [switch]$SkipDemoData,
    [switch]$SkipAdmin,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

# ---------------------------------------------------------------------------
# Görsel yardımcılar
# ---------------------------------------------------------------------------
function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor DarkMagenta
    Write-Host "  $Text" -ForegroundColor Magenta
    Write-Host ("=" * 70) -ForegroundColor DarkMagenta
}

function Write-Step { param([string]$Text) Write-Host "  -> $Text" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Text) Write-Host "  [TAMAM] $Text" -ForegroundColor Green }
function Write-Warn { param([string]$Text) Write-Host "  [UYARI] $Text" -ForegroundColor Yellow }
function Write-Fail { param([string]$Text) Write-Host "  [HATA]  $Text" -ForegroundColor Red }

Write-Header "Wine House — Kurulum"
Write-Host "  Akilli Sarap Restorani Yonetim Sistemi"
Write-Host "  Kurulum klasoru: $ProjectRoot"

# ---------------------------------------------------------------------------
# 1) Python denetimi
# ---------------------------------------------------------------------------
Write-Header "1/8  Python surumu denetleniyor"

function Find-Python {
    param([string]$Explicit)

    if ($Explicit) {
        if (Test-Path $Explicit) { return $Explicit }
        throw "Belirtilen Python bulunamadi: $Explicit"
    }

    # Uyumlu surumler: 3.11, 3.12, 3.13 (Django 5.2 destegi)
    foreach ($version in @("3.12", "3.13", "3.11")) {
        try {
            $found = & py "-$version" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $found) { return $found.Trim() }
        } catch { }
    }

    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) {
        $raw = & $command.Source -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($raw -match '^3\.(11|12|13)$') { return $command.Source }
    }
    return $null
}

$python = Find-Python -Explicit $PythonPath
if (-not $python) {
    Write-Fail "Uyumlu Python bulunamadi (3.11, 3.12 veya 3.13 gerekli)."
    Write-Host ""
    Write-Host "  Cozum: https://www.python.org/downloads/ adresinden Python 3.12 kurun."
    Write-Host "  Kurulum sirasinda 'Add python.exe to PATH' secenegini isaretleyin."
    exit 1
}

$pythonVersion = & $python -c "import sys; print('%d.%d.%d' % sys.version_info[:3])"
Write-Ok "Python $pythonVersion bulundu: $python"

# ---------------------------------------------------------------------------
# 2) Sanal ortam
# ---------------------------------------------------------------------------
Write-Header "2/8  Sanal ortam hazirlaniyor"

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    Write-Ok "Sanal ortam zaten var (.venv)"
} else {
    Write-Step "Sanal ortam olusturuluyor..."
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Fail "Sanal ortam olusturulamadi."; exit 1 }
    Write-Ok "Sanal ortam olusturuldu (.venv)"
}

# ---------------------------------------------------------------------------
# 3) Bagimliliklar
# ---------------------------------------------------------------------------
Write-Header "3/8  Bagimliliklar kuruluyor"
Write-Step "pip guncelleniyor..."
& $venvPython -m pip install --quiet --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { Write-Fail "pip guncellenemedi."; exit 1 }

Write-Step "Paketler kuruluyor (bu birkac dakika surebilir)..."
& $venvPython -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Bagimliliklar kurulamadi. Internet baglantinizi kontrol edin."
    exit 1
}
Write-Ok "Calisma zamani bagimliliklari kuruldu"

$installDev = Read-Host "  Gelistirme araclari da kurulsun mu? (test, lint) [e/H]"
if ($installDev -match '^(e|E|y|Y)') {
    Write-Step "Gelistirme araclari kuruluyor..."
    & $venvPython -m pip install --quiet -r requirements-dev.txt
    Write-Ok "Gelistirme araclari kuruldu"
}

# ---------------------------------------------------------------------------
# 4) Ortam dosyasi
# ---------------------------------------------------------------------------
Write-Header "4/8  Ortam yapilandirmasi (.env)"

$envPath = Join-Path $ProjectRoot ".env"
if (Test-Path $envPath) {
    Write-Ok ".env dosyasi zaten var; degistirilmedi"
} else {
    Write-Step "Gizli anahtarlar uretiliyor..."
    $generator = @'
import pathlib, secrets
from cryptography.fernet import Fernet

template = pathlib.Path(".env.example").read_text(encoding="utf-8")
template = template.replace("DJANGO_SECRET_KEY=", "DJANGO_SECRET_KEY=" + secrets.token_urlsafe(64), 1)
template = template.replace(
    "WINEHOUSE_FIELD_ENCRYPTION_KEY=",
    "WINEHOUSE_FIELD_ENCRYPTION_KEY=" + Fernet.generate_key().decode(),
    1,
)
pathlib.Path(".env").write_text(template, encoding="utf-8")
print("ok")
'@
    $generator | & $venvPython -
    if ($LASTEXITCODE -ne 0) { Write-Fail ".env olusturulamadi."; exit 1 }
    Write-Ok ".env olusturuldu (Django gizli anahtari + sifreleme anahtari uretildi)"
    Write-Warn "Bu dosya gizli bilgi icerir; ASLA paylasmayin veya GitHub'a gondermeyin."
}

# ---------------------------------------------------------------------------
# 5) Veritabani
# ---------------------------------------------------------------------------
Write-Header "5/8  Veritabani kuruluyor"
Write-Step "Sema olusturuluyor (migrate)..."
& $venvPython manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { Write-Fail "Veritabani kurulamadi."; exit 1 }
Write-Ok "Veritabani hazir (SQLite: var\winehouse.sqlite3)"

# ---------------------------------------------------------------------------
# 6) Roller
# ---------------------------------------------------------------------------
Write-Header "6/8  Roller ve yetkiler eslestiriliyor"
& $venvPython manage.py sync_roles --quiet
if ($LASTEXITCODE -ne 0) { Write-Fail "Roller eslestirilemedi."; exit 1 }
Write-Ok "19 restoran rolu ve yetkileri tanimlandi"

# ---------------------------------------------------------------------------
# 7) Ilk yonetici
# ---------------------------------------------------------------------------
Write-Header "7/8  Ilk yonetici"

if ($SkipAdmin) {
    Write-Warn "Yonetici olusturma atlandi (-SkipAdmin)."
    Write-Host "  Daha sonra su komutu calistirin:"
    Write-Host "    .venv\Scripts\python.exe manage.py create_admin" -ForegroundColor Gray
} else {
    $hasSuperuser = & $venvPython -c @"
import os, sys
sys.path.insert(0, 'src')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'winehouse.settings.dev')
import django; django.setup()
from apps.accounts.models import User
print('1' if User.objects.filter(is_superuser=True).exists() else '0')
"@
    if ($hasSuperuser.Trim() -eq "1") {
        Write-Ok "Yonetici hesabi zaten var; olusturma atlandi"
    } else {
        Write-Host "  Simdi ilk yonetici hesabini olusturacaksiniz."
        Write-Host "  Parola ekranda gorunmez ve en az 10 karakter olmalidir."
        Write-Host ""
        & $venvPython manage.py create_admin --skip-if-exists
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Yonetici olusturulamadi. Daha sonra su komutu calistirabilirsiniz:"
            Write-Host "    .venv\Scripts\python.exe manage.py create_admin" -ForegroundColor Gray
        }
    }
}

# ---------------------------------------------------------------------------
# 8) Ornek veri
# ---------------------------------------------------------------------------
Write-Header "8/8  Ornek veri"

if ($SkipDemoData) {
    Write-Warn "Ornek veri yuklemesi atlandi (-SkipDemoData)."
} else {
    Write-Host "  Ornek veri; menu, sarap kavi, masa plani ve gecmis satislari icerir."
    Write-Host "  TUM VERILER SENTETIKTIR; gercek kisi veya kurum bilgisi icermez."
    $loadDemo = Read-Host "  Ornek veri yuklensin mi? [E/h]"
    if ($loadDemo -notmatch '^(h|H|n|N)') {
        & $venvPython manage.py seed_demo --with-sales --days 14
        if ($LASTEXITCODE -eq 0) { Write-Ok "Ornek veri yuklendi" }
        else { Write-Warn "Ornek veri yuklenemedi (kurulum yine de tamamlandi)." }
    }
}

# ---------------------------------------------------------------------------
# Masaustu kisayolu
# ---------------------------------------------------------------------------
Write-Header "Masaustu kisayolu"
$createShortcut = Read-Host "  Masaustune kisayol olusturulsun mu? [E/h]"
if ($createShortcut -notmatch '^(h|H|n|N)') {
    $shortcutScript = Join-Path $ProjectRoot "scripts\create_shortcut.ps1"
    if (Test-Path $shortcutScript) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $shortcutScript
    } else {
        Write-Warn "Kisayol betigi bulunamadi: $shortcutScript"
    }
}

# ---------------------------------------------------------------------------
# Ozet
# ---------------------------------------------------------------------------
Write-Header "Kurulum tamamlandi"
Write-Host ""
Write-Host "  Uygulamayi baslatmak icin:" -ForegroundColor Green
Write-Host "     START_WINE_HOUSE.bat dosyasina cift tiklayin" -ForegroundColor White
Write-Host ""
Write-Host "  Adres:      http://127.0.0.1:8000/" -ForegroundColor White
Write-Host "  Giris:      http://127.0.0.1:8000/hesap/giris/" -ForegroundColor White
Write-Host "  QR menu:    http://127.0.0.1:8000/menu/qr/" -ForegroundColor White
Write-Host ""
Write-Host "  Diger betikler:" -ForegroundColor Green
Write-Host "     CHECK_WINE_HOUSE.bat   - sistem saglik kontrolu"
Write-Host "     BACKUP_WINE_HOUSE.bat  - yedek al"
Write-Host "     STOP_WINE_HOUSE.bat    - sunucuyu durdur"
Write-Host ""
Write-Host "  Notlar:" -ForegroundColor Yellow
Write-Host "     - Sistem internet olmadan calisir."
Write-Host "     - Yapay zeka ozellikleri icin LM Studio'yu baslatin (yerel, ucretsiz)."
Write-Host "     - Odeme ve e-Fatura SANDBOX modundadir; gercek islem yapilmaz."
Write-Host "     - .env dosyasini paylasmayin."
Write-Host ""
