@echo off
chcp 65001 >nul
REM NEXO - Assistente: dados do Aiven (Host, Port, User, Password, ca.pem) e do e-mail, gravados no .env.
call "%~dp0preparar.bat" || exit /b 1
cd /d "%~dp0.."
echo.
".venv\Scripts\python.exe" -m app.configurar
echo.
pause
