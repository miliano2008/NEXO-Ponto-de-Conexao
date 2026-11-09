@echo off
chcp 65001 >nul
REM NEXO - Confere Python, bibliotecas, configuracao, banco (Aiven ou local), esquema, base e e-mail.
call "%~dp0preparar.bat" || exit /b 1
cd /d "%~dp0.."
echo.
".venv\Scripts\python.exe" -m app.diagnostico
echo.
pause
