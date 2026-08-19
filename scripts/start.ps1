<#
.SYNOPSIS
    Wine House sunucusunu başlatır ve tarayıcıyı açar.

.DESCRIPTION
    Yerel geliştirme/işletme sunucusunu çalıştırır. Sunucu yalnızca bu
    makineden erişilebilir (127.0.0.1). İşletme ağındaki başka terminallerden
    erişim için -Host 0.0.0.0 kullanın.

.PARAMETER Port
    Dinlenecek port (varsayılan .env dosyasındaki WINEHOUSE_PORT veya 8000).

.PARAMETER BindHost
    Dinlenecek adres. Varsayılan 127.0.0.1 (yalnızca bu makine).

.PARAMETER NoBrowser
    Tarayıcıyı otomatik açmaz.

.PARAMETER Production
    Üretim ayarlarıyla çalıştırır (DEBUG kapalı).
#>

[CmdletBinding()]
param(
    [int]$Port = 0,
    [string]$BindHost = "127.0.0.1",
    [switch]$NoBrowser,
    [switch]$Production
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[HATA] Sanal ortam bulunamadi. Once INSTALL_WINE_HOUSE.ps1 calistirin." -ForegroundColor Red
    exit 1
}

# Port: parametre > .env > 8000
if ($Port -eq 0) {
    $Port = 8000
    $envFile = Join-Path $ProjectRoot ".env"
    if (Test-Path $envFile) {
        $line = Select-String -Path $envFile -Pattern '^\s*WINEHOUSE_PORT\s*=\s*(\d+)' | Select-Object -First 1
        if ($line) { $Port = [int]$line.Matches[0].Groups[1].Value }
    }
}

$settings = if ($Production) { "winehouse.settings.prod" } else { "winehouse.settings.dev" }
$env:DJANGO_SETTINGS_MODULE = $settings
$env:PYTHONIOENCODING = "utf-8"

# Port kullanımda mı?
$inUse = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($inUse) {
    Write-Host ""
    Write-Host "[UYARI] $Port portu zaten kullanimda." -ForegroundColor Yellow
    Write-Host "  Wine House zaten calisiyor olabilir: http://127.0.0.1:$Port/"
    Write-Host "  Durdurmak icin STOP_WINE_HOUSE.bat dosyasini calistirin."
    Write-Host ""
    $continue = Read-Host "  Yine de devam edilsin mi? [e/H]"
    if ($continue -notmatch '^(e|E|y|Y)') { exit 0 }
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor DarkMagenta
Write-Host "  Wine House - Akilli Sarap Restorani Yonetim Sistemi" -ForegroundColor Magenta
Write-Host "======================================================================" -ForegroundColor DarkMagenta
Write-Host "  Mod       : $(if ($Production) { 'URETIM' } else { 'GELISTIRME' })"
Write-Host "  Adres     : http://${BindHost}:$Port/"
Write-Host "  Giris     : http://127.0.0.1:$Port/hesap/giris/"
Write-Host "  QR menu   : http://127.0.0.1:$Port/menu/qr/"
Write-Host ""
Write-Host "  Durdurmak icin bu pencerede Ctrl+C tuslayin." -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor DarkMagenta
Write-Host ""

if (-not $NoBrowser) {
    Start-Job -ScriptBlock {
        param($url)
        Start-Sleep -Seconds 3
        Start-Process $url
    } -ArgumentList "http://127.0.0.1:$Port/" | Out-Null
}

# Üretim modunda statik dosyalar toplanır
if ($Production) {
    Write-Host "  Statik dosyalar toplaniyor..." -ForegroundColor Cyan
    & $venvPython manage.py collectstatic --noinput --clear | Out-Null
}

& $venvPython manage.py runserver "${BindHost}:$Port"
