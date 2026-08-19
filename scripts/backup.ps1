<#
.SYNOPSIS
    Wine House veritabanının şifreli yedeğini alır ve doğrular.

.DESCRIPTION
    Yedek ZIP arşivi olarak alınır, Fernet ile şifrelenir ve SHA-256
    özetiyle doğrulanır. Saklama politikası uygulanır (en az 3 yedek
    daima korunur).

    Windows Görev Zamanlayıcı ile günlük çalıştırılabilir:
        Program : powershell.exe
        Argüman : -NoProfile -ExecutionPolicy Bypass -File "D:\Wine_House\scripts\backup.ps1"

.PARAMETER Destination
    Yedeğin yazılacağı klasör. Boşsa .env dosyasındaki WINEHOUSE_BACKUP_DIR.

.PARAMETER NoEncrypt
    Şifrelemeyi kapatır (önerilmez).
#>

[CmdletBinding()]
param(
    [string]$Destination = "",
    [switch]$NoEncrypt
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[HATA] Sanal ortam bulunamadi. Once INSTALL_WINE_HOUSE.ps1 calistirin." -ForegroundColor Red
    exit 1
}

$env:PYTHONIOENCODING = "utf-8"
$env:DJANGO_SETTINGS_MODULE = "winehouse.settings.dev"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor DarkMagenta
Write-Host "  Wine House - Yedekleme" -ForegroundColor Magenta
Write-Host "======================================================================" -ForegroundColor DarkMagenta

$arguments = @("manage.py", "backup_now", "--apply-retention")
if ($Destination) { $arguments += @("--destination", $Destination) }
if ($NoEncrypt)   { $arguments += "--no-encrypt" }

& $venvPython @arguments
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "[TAMAM] Yedekleme basariyla tamamlandi ve dogrulandi." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[HATA] Yedekleme basarisiz (cikis kodu: $exitCode)." -ForegroundColor Red
}
exit $exitCode
