"""Roda todos os testes do NEXO: scripts\\TESTAR.bat  ou  python -m testes.executar

- test_nucleo, test_login e test_fase0: sempre (CSV + SQLite temporários).
- test_mysql: só se o MySQL estiver configurado; usa um banco TEMPORÁRIO (nexo_teste)
  e o apaga no final — o banco do grupo não é alterado.
- e2e/test_navegador: só se o Playwright estiver instalado (requirements-dev.txt).
"""
import importlib.util
import os
import subprocess
import sys
import time

from nucleo.configuracao import RAIZ

TESTES = ["testes.test_nucleo", "testes.test_login", "testes.test_fase0"]


def mysql_configurado():
    from banco import conexao as db
    return db.usando_mysql()


def main():
    roteiro = list(TESTES)
    if mysql_configurado():
        roteiro.append("testes.test_mysql")
    else:
        print("(pulando testes.test_mysql: MySQL não configurado)")
    if importlib.util.find_spec("playwright"):
        roteiro.append("testes.e2e.test_navegador")
    else:
        print("(pulando testes.e2e.test_navegador: instale com  python -m pip install -r requirements-dev.txt)")

    falhas = []
    for modulo in roteiro:
        inicio = time.perf_counter()
        r = subprocess.run([sys.executable, "-m", modulo], cwd=RAIZ, capture_output=True, text=True, env=os.environ)
        duracao = time.perf_counter() - inicio
        linhas = [l for l in r.stdout.splitlines() if l.startswith("TESTES OK")]
        if r.returncode == 0:
            print(f"  [OK]    {modulo:30s} {duracao:5.1f}s  {linhas[-1] if linhas else ''}")
        else:
            falhas.append(modulo)
            print(f"  [FALHA] {modulo:30s} {duracao:5.1f}s")
            print("\n".join("          " + l for l in (r.stdout + r.stderr).strip().splitlines()[-15:]))
    print()
    if falhas:
        print(f"{len(falhas)} conjunto(s) de testes falharam: {', '.join(falhas)}")
        raise SystemExit(1)
    print(f"Todos os {len(roteiro)} conjuntos de testes passaram.")


if __name__ == "__main__":
    main()
