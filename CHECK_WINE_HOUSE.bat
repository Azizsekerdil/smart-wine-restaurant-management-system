@echo off
REM ===================================================================
REM  Wine House - Sistem saglik kontrolu
REM ===================================================================
chcp 65001 >nul
title Wine House - Saglik Kontrolu
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\check.ps1"
pause
