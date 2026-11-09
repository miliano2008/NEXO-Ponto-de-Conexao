#!/usr/bin/env bash
# NEXO — instalador para Linux Mint / Ubuntu / Debian. Executar (na raiz): bash scripts/instalar_linux.sh
cd "$(dirname "$0")/.." || exit 1   # raiz do projeto
echo "=== NEXO — instalação no Linux ==="
if command -v apt-get >/dev/null; then
  echo "Instalando Python 3, venv e pip (vai pedir sua senha do sudo)..."
  sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip || {
    echo "[ERRO] Falha no apt-get."; exit 1; }
elif command -v dnf >/dev/null; then
  sudo dnf install -y python3 python3-pip || exit 1
else
  echo "[ERRO] Gerenciador de pacotes não reconhecido. Instale python3, python3-venv e python3-pip."; exit 1
fi
chmod +x iniciar.sh
./iniciar.sh
