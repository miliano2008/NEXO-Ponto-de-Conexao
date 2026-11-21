"""NEXO — serviço do simulador (Fase 4): dados bancários, regras por modalidade, simulação
recorrente, cenários salvos (histórico) e fontes da comparação lado a lado.

As rotas ficam em app/servidor.py; a matemática em nucleo/ (bancario.py, comparacao.py).
"""

import threading
from datetime import date, timedelta

from app import analises
from banco import repositorio
from nucleo import bancario, comparacao

MAX_REPETICOES = 30
MAX_INTERVALO_DIAS = 90

_trava = threading.Lock()
_bancos = {"assinatura": None, "dados": None}


def dados_bancarios():
    """Dados bancários fictícios da base atual (recalculados só quando a base muda)."""
    contas, transacoes, assinatura = analises.obter_base()
    with _trava:
        if _bancos["assinatura"] != assinatura:
            _bancos.update(assinatura=assinatura, dados=bancario.dados_bancarios(contas, transacoes))
        return _bancos["dados"]


def titulares():
    return {c["id_conta"]: c["tipo_titular"] for c in analises.obter_base()[0]}


def regras():
    return bancario.regras_com_ajustes(repositorio.ler_ajustes_regras())


def regras_para_tela():
    """Regras com origem, ação, parâmetros, quem ajustou e a conferência informativa da base."""
    ajustes, atuais = repositorio.ler_ajustes_regras(), regras()
    _, base, _ = analises.obter_base()
    fora = bancario.conferir_base(base, titulares(), dados_bancarios(), atuais)
    return [{"id": rid, **r, "padrao": {"acao": bancario.REGRAS_PADRAO[rid]["acao"],
                                        "parametros": bancario.REGRAS_PADRAO[rid]["parametros"]},
             "ajustado_por": ajustes.get(rid, {}).get("atualizado_por"),
             "ajustado_em": ajustes.get(rid, {}).get("atualizado_em"),
             "base_fora": fora.get(rid, 0)} for rid, r in atuais.items()]


def expandir(nova, repetir=None):
    """A transação e as repetições "a cada N dias" (cada uma vira uma transação, na mesma hora)."""
    repetir = repetir or {}
    try:
        vezes = int(repetir.get("vezes") or 1)
        intervalo = int(repetir.get("a_cada_dias") or 0)
    except (TypeError, ValueError) as erro:
        raise ValueError("Repetição inválida: informe números inteiros.") from erro
    if not 1 <= vezes <= MAX_REPETICOES:
        raise ValueError(f"Repita de 1 a {MAX_REPETICOES} vezes.")
    if vezes > 1 and not 1 <= intervalo <= MAX_INTERVALO_DIAS:
        raise ValueError(f"O intervalo entre as repetições precisa ser de 1 a {MAX_INTERVALO_DIAS} dias.")
    try:
        inicio = date.fromisoformat(str(nova["data"]))
    except ValueError as erro:
        raise ValueError("Data inválida.") from erro
    return [{**nova, "data": (inicio + timedelta(days=i * intervalo)).isoformat()} for i in range(vezes)]


def verificar(linhas):
    """Confere cada transação com as regras da modalidade. Retorna (verificações por linha, bloqueios, alertas)."""
    bancos, tit, atuais = dados_bancarios(), titulares(), regras()
    resultado = []
    for linha in linhas:
        t = {"de": linha["conta_origem"], "para": linha["conta_destino"], "valor": linha["valor"],
             "data": linha["data"], "hora": linha["hora"], "tipo": linha["tipo_transacao"]}
        try:
            checks = bancario.avaliar_transacao(t, tit.get(t["de"]), bancos, atuais)
        except (ValueError, KeyError):
            checks = []   # dado inválido: o motor recusa com a mensagem certa logo depois
        resultado.append({"data": linha["data"], "hora": linha["hora"], "verificacoes": checks})
    bloqueios = sum(1 for r in resultado for v in r["verificacoes"] if v["resultado"] == "bloqueio")
    alertas = sum(1 for r in resultado for v in r["verificacoes"] if v["resultado"] == "alerta")
    return resultado, bloqueios, alertas


# ---------------------------------------------------------------- cenários (histórico)

def resumo_execucao(antes, depois, quantidade):
    diff = comparacao.comparar(antes, depois)
    alteradas = [c for c in diff["contas"] if "so_em" not in c and (c["delta_score"] or c["nivel"][0] != c["nivel"][1])]
    maior = max(alteradas, key=lambda c: abs(c["delta_score"]), default=None)
    return {"transacoes_simuladas": quantidade, "contas_alteradas": len(alteradas),
            "maior_variacao": {"conta": maior["id"], "delta": maior["delta_score"]} if maior else None,
            "prioridade_alta": [antes["risco"]["resumo"]["por_nivel"].get("Alta", 0),
                                depois["risco"]["resumo"]["por_nivel"].get("Alta", 0)],
            "comunidades": [antes["dashboard"]["total_comunidades"], depois["dashboard"]["total_comunidades"]],
            "volume": [antes["dashboard"]["volume_total"], depois["dashboard"]["volume_total"]]}


def salvar_cenario(usuario, nome, descricao, recorte):
    nome = " ".join(str(nome or "").split())[:80]
    if len(nome) < 3:
        raise ValueError("Dê um nome ao cenário (mínimo de 3 caracteres).")
    simuladas = repositorio.listar_simuladas(usuario["id"])
    if not simuladas:
        raise ValueError("A simulação está vazia: inclua ao menos uma transação antes de salvar o cenário.")
    r = analises.normalizar_recorte(recorte)
    depois, _ = analises.calcular(r, simuladas)
    antes, _ = analises.calcular(r, [])
    resumo = resumo_execucao(antes, depois, len(simuladas))
    return repositorio.salvar_cenario(usuario["id"], nome, str(descricao or "").strip()[:500], simuladas, r, resumo,
                                      comparacao.compacto(depois), comparacao.compacto(antes))


# ---------------------------------------------------------------- comparação

def fonte(usuario, texto):
    """Resultado compacto e rótulo de uma fonte de comparação:
       base · recorte:AAAA-MM-DD:AAAA-MM-DD · rascunho · cenario:ID · cenario:ID:base"""
    partes = str(texto or "base").split(":")
    tipo = partes[0]
    if tipo == "base":
        resultado, _ = analises.calcular(0, [])
        return comparacao.compacto(resultado), "Base completa"
    if tipo == "recorte" and len(partes) == 3:
        resultado, _ = analises.calcular({"inicio": partes[1], "fim": partes[2]}, [])
        ini, fim = (date.fromisoformat(p).strftime("%d/%m/%Y") for p in partes[1:])
        return comparacao.compacto(resultado), f"{ini} a {fim}"
    if tipo == "rascunho":
        simuladas = repositorio.listar_simuladas(usuario["id"])
        if not simuladas:
            raise ValueError("Sua simulação atual está vazia.")
        resultado, _ = analises.calcular(0, simuladas)
        return comparacao.compacto(resultado), f"Simulação atual ({len(simuladas)} transação(ões))"
    if tipo == "cenario" and len(partes) in (2, 3):
        try:
            cid = int(partes[1])
        except ValueError as erro:
            raise ValueError("Cenário inválido.") from erro
        cenario = repositorio.obter_cenario(usuario["id"], cid)
        if cenario is None:
            raise ValueError("Cenário não encontrado.")
        if len(partes) == 3:
            return cenario["resultado_base"], f"Base no momento de “{cenario['nome']}”"
        return cenario["resultado"], f"Cenário “{cenario['nome']}”"
    raise ValueError("Fonte de comparação inválida.")
