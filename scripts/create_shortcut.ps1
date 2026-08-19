<#
.SYNOPSIS
    Masaüstünde Wine House kısayolu oluşturur.
#>

[CmdletBinding()]
param([string]$Name = "Wine House")

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

$target = Join-Path $ProjectRoot "START_WINE_HOUSE.bat"
if (-not (Test-Path $target)) {
    Write-Host "[HATA] START_WINE_HOUSE.bat bulunamadi." -ForegroundColor Red
    exit 1
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "$Name.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $ProjectRoot
$shortcut.Description = "Akilli Sarap Restorani Yonetim Sistemi"

$iconPath = Join-Path $ProjectRoot "src\static\img\winehouse.ico"
if (Test-Path $iconPath) { $shortcut.IconLocation = $iconPath }

$shortcut.Save()
Write-Host "[TAMAM] Masaustu kisayolu olusturuldu: $shortcutPath" -ForegroundColor Green
