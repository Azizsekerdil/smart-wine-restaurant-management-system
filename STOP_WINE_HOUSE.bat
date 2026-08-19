@echo off
REM ===================================================================
REM  Wine House - Calisan sunucuyu durdurur
REM ===================================================================
chcp 65001 >nul
title Wine House - Durdur
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
pause
