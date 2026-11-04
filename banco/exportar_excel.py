"""Exporta as abas Contas e Transacoes do Excel para banco/dados/*.csv.

Executar: python -m banco.exportar_excel [caminho_do_excel]
A planilha original não é alterada.
"""

import csv
import sys
from datetime import date, datetime, time
from pathlib import Path

import openpyxl

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "dados"
PADRAO = DADOS / "NEXO_Base_Transacoes.xlsx"


def texto(valor):
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, time):
        return valor.strftime("%H:%M")
    if isinstance(valor, float):
        return f"{valor:.2f}"
    return "" if valor is None else str(valor).strip()


def exportar_aba(planilha, aba, destino):
    linhas = [l for l in planilha[aba].iter_rows(values_only=True) if any(v is not None for v in l)]
    with destino.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow([texto(v) for v in linhas[0]])
        for linha in linhas[1:]:
            escritor.writerow([texto(v) for v in linha])
    return len(linhas) - 1


if __name__ == "__main__":
    origem = Path(sys.argv[1]) if len(sys.argv) > 1 else PADRAO
    planilha = openpyxl.load_workbook(origem, data_only=True, read_only=True)
    print("Contas:", exportar_aba(planilha, "Contas", DADOS / "contas.csv"))
    print("Transações:", exportar_aba(planilha, "Transacoes", DADOS / "transacoes.csv"))
