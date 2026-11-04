"""Gera o JSON completo da análise da base atual: python -m nucleo

Saída: saida/resultados_nexo.json
"""
import json

from banco import repositorio
from nucleo import analise
from nucleo.configuracao import RAIZ

SAIDA = RAIZ / "saida" / "resultados_nexo.json"


def gerar_resultados():
    dados = analise.calcular(*repositorio.carregar_dados())
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2, allow_nan=False)
    return dados


if __name__ == "__main__":
    try:
        resultado = gerar_resultados()
        print("NEXO — processamento concluído!")
        print("Contas:", resultado["dashboard"]["total_contas"])
        print("Transações:", resultado["dashboard"]["total_transacoes"])
        print("Comunidades (Louvain):", resultado["dashboard"]["total_comunidades"])
        print("Conta líder do ranking:", resultado["contas"][0]["id"])
        print("Arquivo JSON:", SAIDA)
    except (FileNotFoundError, ValueError) as erro:
        print("Erro no processamento:", erro)
        raise SystemExit(1) from erro
