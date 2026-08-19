@echo off
REM ===================================================================
REM  Wine House - Yedek alir ve dogrular
REM  Windows Gorev Zamanlayici ile de calistirilabilir.
REM ===================================================================
chcp 65001 >nul
title Wine House - Yedekleme
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\backup.ps1" %*
if errorlevel 1 pause
