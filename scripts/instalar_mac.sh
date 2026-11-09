#!/usr/bin/env bash
# NEXO — instalador para macOS. Executar no Terminal (na raiz): bash scripts/instalar_mac.sh
cd "$(dirname "$0")/.." || exit 1   # raiz do projeto
echo "=== NEXO — instalação no macOS ==="
VERSAO=3.12.7
if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  echo "Python já instalado: $(python3 --version)"
elif command -v brew >/dev/null; then
  brew install python@3.12 || exit 1
else
  PKG="/tmp/python-$VERSAO-macos11.pkg"
  echo "Baixando o Python $VERSAO de python.org..."
  curl -fL -o "$PKG" "https://www.python.org/ftp/python/$VERSAO/python-$VERSAO-macos11.pkg" || exit 1
  echo "Instalando (vai pedir sua senha do Mac)..."
  sudo installer -pkg "$PKG" -target / || exit 1
  export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
fi
chmod +x iniciar.sh
./iniciar.sh
