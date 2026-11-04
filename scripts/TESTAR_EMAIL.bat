@echo off
chcp 65001 >nul
REM NEXO - Testa o login no servidor de e-mail e envia uma mensagem de teste.
call "%~dp0preparar.bat" || exit /b 1
cd /d "%~dp0.."
echo.
".venv\Scripts\python.exe" -m app.envio_email
echo.
pause
