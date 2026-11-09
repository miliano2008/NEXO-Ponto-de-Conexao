@echo off
chcp 65001 >nul
REM NEXO - prepara o ambiente (se preciso) e inicia o sistema.
cd /d "%~dp0"
call "%~dp0scripts\preparar.bat" || exit /b 1
cd /d "%~dp0"

REM Primeira vez neste computador: assistente para conectar ao banco do grupo (Aiven) e ao e-mail
if not exist ".env" if not exist "config.ini" ".venv\Scripts\python.exe" -m app.configurar

".venv\Scripts\python.exe" -m app.diagnostico --rapido

REM Aplica migracoes pendentes e confere se existe administrador
".venv\Scripts\python.exe" -c "from app import auth; import sys; auth.iniciar_banco(); sys.exit(0 if auth.contar_administradores_ativos() else 1)" || (
  echo.
  echo Nenhum administrador encontrado. Vamos criar o seu acesso:
  ".venv\Scripts\python.exe" -m app.criar_admin
)

REM Abre o navegador alguns segundos depois do servidor subir
start "" cmd /c "timeout /t 5 >nul & start http://127.0.0.1:5000"
echo.
echo Para encerrar o NEXO, feche esta janela ou pressione Ctrl+C.
".venv\Scripts\python.exe" -m app
pause
