@echo off
chcp 65001 >nul
REM NEXO - Cria o banco no Aiven e envia as 40 contas e 160 transacoes (pode repetir: nao duplica).
call "%~dp0preparar.bat" || exit /b 1
cd /d "%~dp0.."
echo.
".venv\Scripts\python.exe" -m banco.migrar_mysql
echo.
pause
