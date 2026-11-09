#!/usr/bin/env bash
# NEXO — prepara o ambiente (se preciso) e inicia o simulador.
cd "$(dirname "$0")" || exit 1

PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then
  echo "[ERRO] Python não encontrado. Linux Mint/Ubuntu: sudo apt install python3 python3-venv python3-pip"
  exit 1
fi

# Um .venv copiado de outro computador não funciona: testa e recria se preciso
if [ -d .venv ] && ! .venv/bin/python -c "import sys" >/dev/null 2>&1; then
  echo "Ambiente .venv inválido (copiado de outro computador?). Recriando..."
  rm -rf .venv
fi
if [ ! -d .venv ]; then
  echo "Criando ambiente virtual..."
  if ! "$PY" -m venv .venv; then
    rm -rf .venv
    echo "[ERRO] Falha ao criar o .venv. No Linux Mint/Ubuntu instale: sudo apt install python3-venv"
    exit 1
  fi
fi

echo "Instalando/conferindo bibliotecas..."
.venv/bin/python -m pip install -q -r requirements.txt || {
  echo "[ERRO] Falha ao instalar as bibliotecas. Verifique a internet ou o proxy da rede."; exit 1; }

# Primeira vez neste computador: assistente para conectar ao banco do grupo (Aiven)
[ -f .env ] || [ -f config.ini ] || .venv/bin/python -m app.configurar

.venv/bin/python -m app.diagnostico --rapido

# Aplica migrações pendentes e confere se existe administrador
if ! .venv/bin/python -c "from app import auth; import sys; auth.iniciar_banco(); sys.exit(0 if auth.contar_administradores_ativos() else 1)"; then
  echo; echo "Nenhum administrador encontrado. Vamos criar o seu acesso:"
  .venv/bin/python -m app.criar_admin
fi

# Abre o navegador alguns segundos depois do servidor subir
( sleep 5; (command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:5000) || open http://127.0.0.1:5000 ) >/dev/null 2>&1 &
echo "Para encerrar o NEXO, pressione Ctrl+C."
.venv/bin/python -m app
