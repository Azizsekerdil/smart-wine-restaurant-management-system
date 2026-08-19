<#
.SYNOPSIS
    Wine House sistem sağlık kontrolü.

.DESCRIPTION
    Kurulumun ve çalışma ortamının doğruluğunu denetler:
      * Python, sanal ortam ve bağımlılıklar
      * .env yapılandırması ve gizli anahtarların varlığı
      * Veritabanı, migration, roller ve yönetici hesabı
      * Django güvenlik kontrolleri ve mod ayarları
      * Yapay zekâ sağlayıcı erişilebilirliği (LM Studio dâhil)
      * Yedekleme durumu ve sunucunun çalışıp çalışmadığı

    Django tarafındaki denetimler scripts\healthcheck.py içindedir.

    Hiçbir gizli değer (API anahtarı, parola) ekrana yazılmaz.

.PARAMETER Port
    Denetlenecek sunucu portu. Boşsa .env dosyasındaki WINEHOUSE_PORT.
#>

[CmdletBinding()]
param([int]$Port = 0)

# Türkçe karakterlerin konsolda doğru görünmesi için
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$script:Passed = 0
$script:Failed = 0
$script:Warned = 0

function Show-Result {
    param([string]$Status, [string]$Title, [string]$Detail = "")

    $text = if ($Detail) { "$Title`: $Detail" } else { $Title }
    switch ($Status) {
        "OK"   { Write-Host ("  [OK]    {0}" -f $text) -ForegroundColor Green;    $script:Passed++ }
        "WARN" { Write-Host ("  [UYARI] {0}" -f $text) -ForegroundColor Yellow;   $script:Warned++ }
        "FAIL" { Write-Host ("  [HATA]  {0}" -f $text) -ForegroundColor Red;      $script:Failed++ }
        default { Write-Host ("  [BILGI] {0}" -f $text) -ForegroundColor DarkGray }
    }
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor DarkMagenta
Write-Host "  Wine House - Sistem Saglik Kontrolu" -ForegroundColor Magenta
Write-Host "======================================================================" -ForegroundColor DarkMagenta

# ---------------------------------------------------------------------------
# 1) Kurulum
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  KURULUM" -ForegroundColor Cyan

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Show-Result "FAIL" "Sanal ortam" "bulunamadi"
    Write-Host ""
    Write-Host "  Kurulum eksik. INSTALL_WINE_HOUSE.ps1 dosyasini calistirin." -ForegroundColor Red
    exit 1
}
Show-Result "OK" "Sanal ortam" ".venv"

$pythonVersion = (& $venvPython -c "import sys; print('%d.%d.%d' % sys.version_info[:3])").Trim()
if ($pythonVersion -match '^3\.(11|12|13)\.') {
    Show-Result "OK" "Python surumu" $pythonVersion
} else {
    Show-Result "WARN" "Python surumu" "$pythonVersion (3.11-3.13 onerilir)"
}

foreach ($package in @("django", "rest_framework", "httpx", "cryptography", "reportlab", "openpyxl")) {
    & $venvPython -c "import $package" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Show-Result "OK" "Paket" $package
    } else {
        Show-Result "FAIL" "Paket" "$package eksik"
    }
}

# ---------------------------------------------------------------------------
# 2) Ortam dosyası
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  YAPILANDIRMA" -ForegroundColor Cyan

$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
    Show-Result "OK" ".env dosyasi" "mevcut"

    $secretLine = Select-String -Path $envFile -Pattern 'DJANGO_SECRET_KEY\s*=\s*(\S+)' | Select-Object -First 1
    if ($null -ne $secretLine -and $secretLine.Matches[0].Groups[1].Value.Length -ge 32) {
        Show-Result "OK" "Django gizli anahtari" "tanimli"
    } else {
        Show-Result "FAIL" "Django gizli anahtari" "tanimsiz veya cok kisa"
    }

    $keyLine = Select-String -Path $envFile -Pattern 'WINEHOUSE_FIELD_ENCRYPTION_KEY\s*=\s*(\S+)' | Select-Object -First 1
    if ($null -ne $keyLine -and $keyLine.Matches[0].Groups[1].Value.Length -ge 32) {
        Show-Result "OK" "Alan sifreleme anahtari" "tanimli"
    } else {
        Show-Result "WARN" "Alan sifreleme anahtari" "tanimsiz - kisisel veriler duz metin saklanir"
    }
} else {
    Show-Result "FAIL" ".env dosyasi" "yok - INSTALL_WINE_HOUSE.ps1 calistirin"
}

$gitignore = Join-Path $ProjectRoot ".gitignore"
if ((Test-Path $gitignore) -and (Select-String -Path $gitignore -Pattern '^\.env$' -Quiet)) {
    Show-Result "OK" ".env surum denetiminden haric" "korumali"
} else {
    Show-Result "FAIL" ".env surum denetimi" "GUVENLIK RISKI - .gitignore icinde .env yok"
}

# ---------------------------------------------------------------------------
# 3) Django tarafı denetimler
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  UYGULAMA" -ForegroundColor Cyan

$env:PYTHONIOENCODING = "utf-8"
$env:DJANGO_SETTINGS_MODULE = "winehouse.settings.dev"

$healthScript = Join-Path $ProjectRoot "scripts\healthcheck.py"
if (Test-Path $healthScript) {
    $report = & $venvPython $healthScript 2>$null
    foreach ($line in $report) {
        if (-not $line -or -not $line.Contains("|")) { continue }
        $parts = $line -split '\|', 3
        Show-Result $parts[0] $parts[1] $(if ($parts.Count -ge 3) { $parts[2] } else { "" })
    }
} else {
    Show-Result "FAIL" "Saglik betigi" "scripts\healthcheck.py bulunamadi"
}

# ---------------------------------------------------------------------------
# 4) Sunucu
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  SUNUCU" -ForegroundColor Cyan

if ($Port -eq 0) {
    $Port = 8000
    if (Test-Path $envFile) {
        $portLine = Select-String -Path $envFile -Pattern 'WINEHOUSE_PORT\s*=\s*(\d+)' | Select-Object -First 1
        if ($null -ne $portLine) { $Port = [int]$portLine.Matches[0].Groups[1].Value }
    }
}

$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/health/" -TimeoutSec 5
        Show-Result "OK" "Sunucu" "calisiyor - surum $($response.version), durum $($response.status)"
    } catch {
        Show-Result "INFO" "Port $Port" "dinleniyor ancak Wine House saglik ucu yanit vermedi (baska bir uygulama olabilir)"
    }
} else {
    Show-Result "INFO" "Sunucu" "calismiyor - START_WINE_HOUSE.bat ile baslatin"
}

# ---------------------------------------------------------------------------
# Özet
# ---------------------------------------------------------------------------
$color = if ($script:Failed -gt 0) { "Red" } elseif ($script:Warned -gt 0) { "Yellow" } else { "Green" }

Write-Host ""
Write-Host "======================================================================" -ForegroundColor DarkMagenta
Write-Host ("  Sonuc: {0} basarili, {1} uyari, {2} hata" -f $script:Passed, $script:Warned, $script:Failed) -ForegroundColor $color
Write-Host "======================================================================" -ForegroundColor DarkMagenta
Write-Host ""

if ($script:Failed -gt 0) { exit 1 }
exit 0
