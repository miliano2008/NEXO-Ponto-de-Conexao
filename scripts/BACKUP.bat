@echo off
chcp 65001 >nul
REM NEXO - Copia de seguranca do banco (Aiven: arquivo .sql; local: copia do nexo.db) em banco\dados\backups.
call "%~dp0preparar.bat" || exit /b 1
cd /d "%~dp0.."
echo.
".venv\Scripts\python.exe" -m banco.backup
echo.
pause
