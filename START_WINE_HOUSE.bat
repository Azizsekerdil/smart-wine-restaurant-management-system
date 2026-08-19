@echo off
REM ===================================================================
REM  Wine House - Uygulamayi baslatir
REM  Bu dosyaya CIFT TIKLAYIN. PowerShell icine yapistirmayin.
REM ===================================================================
chcp 65001 >nul
title Wine House - Sunucu
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  [HATA] Kurulum bulunamadi.
    echo  Once INSTALL_WINE_HOUSE.ps1 dosyasina sag tiklayip
    echo  "PowerShell ile calistir" secenegini kullanin.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
if errorlevel 1 pause
