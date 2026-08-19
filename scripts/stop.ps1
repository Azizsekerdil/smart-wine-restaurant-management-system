<#
.SYNOPSIS
    Çalışan Wine House sunucusunu durdurur.

.DESCRIPTION
    Yapılandırılmış portu dinleyen Python sürecini bulur ve nazikçe kapatır.
    Yalnızca bu projenin .venv dizinindeki Python süreçleri hedeflenir;
    sistemdeki diğer Python uygulamalarına dokunulmaz.
#>

[CmdletBinding()]
param([int]$Port = 0)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

if ($Port -eq 0) {
    $Port = 8000
    $envFile = Join-Path $ProjectRoot ".env"
    if (Test-Path $envFile) {
        $line = Select-String -Path $envFile -Pattern '^\s*WINEHOUSE_PORT\s*=\s*(\d+)' | Select-Object -First 1
        if ($line) { $Port = [int]$line.Matches[0].Groups[1].Value }
    }
}

$venvPath = (Join-Path $ProjectRoot ".venv").ToLower()
$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue

if (-not $connections) {
    Write-Host "[BILGI] $Port portunda calisan sunucu bulunamadi." -ForegroundColor Yellow
    exit 0
}

$stopped = 0
foreach ($connection in $connections) {
    $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
    if (-not $process) { continue }

    # Güvenlik: yalnızca bu projenin sanal ortamındaki süreçler durdurulur
    $path = ""
    try { $path = $process.Path.ToLower() } catch { }
    if ($path -and -not $path.StartsWith($venvPath)) {
        Write-Host "[ATLANDI] $Port portunu baska bir uygulama kullaniyor: $($process.ProcessName) (PID $($process.Id))" -ForegroundColor Yellow
        Write-Host "          Bu surece dokunulmadi." -ForegroundColor Yellow
        continue
    }

    Write-Host "  Durduruluyor: PID $($process.Id) ($($process.ProcessName))" -ForegroundColor Cyan
    Stop-Process -Id $process.Id -Force
    $stopped++
}

if ($stopped -gt 0) {
    Write-Host "[TAMAM] Wine House sunucusu durduruldu ($stopped surec)." -ForegroundColor Green
} else {
    Write-Host "[BILGI] Wine House surecine ait dinleyici bulunamadi." -ForegroundColor Yellow
}
