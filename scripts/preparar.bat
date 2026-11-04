@echo off
chcp 65001 >nul
REM NEXO - prepara o ambiente: encontra o Python, cria o .venv e instala as bibliotecas.
REM Usado por iniciar.bat e por todos os atalhos da pasta scripts\. Roda sempre na raiz do projeto.
cd /d "%~dp0.."

REM Confere se o projeto esta completo (rodar de dentro de um .zip nao funciona)
if not exist "app\servidor.py" (
  echo [ERRO] app\servidor.py nao encontrado. Baixe/extraia o projeto inteiro antes de executar.
  pause & exit /b 1
)

REM Encontra o Python: "py" (launcher do Windows) ou "python"
set PY=
py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY python --version >nul 2>&1 && set PY=python
if not defined PY (
  echo [ERRO] Python nao encontrado. Instale o Python 3.10 ou mais novo em https://www.python.org/downloads/
  echo        e marque a opcao "Add python.exe to PATH" na instalacao.
  pause & exit /b 1
)

REM Um .venv copiado de outro computador nao funciona: testa e recria se preciso
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys" >nul 2>&1 || (
    echo Ambiente .venv invalido (copiado de outro computador?^). Recriando...
    rmdir /s /q .venv
  )
) else (
  if exist ".venv" rmdir /s /q .venv
)
if not exist ".venv" (
  echo Criando ambiente virtual...
  %PY% -m venv .venv || ( echo [ERRO] Falha ao criar o .venv. & pause & exit /b 1 )
)

echo Instalando/conferindo bibliotecas...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || (
  echo [ERRO] Falha ao instalar as bibliotecas. Verifique a internet ou o proxy da rede.
  pause & exit /b 1
)
exit /b 0
