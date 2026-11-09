@echo off
REM NEXO - de dois cliques neste arquivo. Instala o Python (se faltar) e abre o sistema.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\instalar_windows.ps1"
if errorlevel 1 pause
