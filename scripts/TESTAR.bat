@echo off
chcp 65001 >nul
REM NEXO - Roda todos os testes automaticos do projeto.
call "%~dp0preparar.bat" || exit /b 1
cd /d "%~dp0.."
echo.
".venv\Scripts\python.exe" -m testes.executar
echo.
pause
