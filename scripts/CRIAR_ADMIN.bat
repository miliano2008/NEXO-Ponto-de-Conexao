@echo off
chcp 65001 >nul
REM NEXO - Cria um administrador ou promove uma conta existente.
call "%~dp0preparar.bat" || exit /b 1
cd /d "%~dp0.."
echo.
".venv\Scripts\python.exe" -m app.criar_admin
echo.
pause
