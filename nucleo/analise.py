"""NEXO — motor matemático: grafos, matrizes, centralidades, Louvain, espectral e score.

Funções puras: recebem contas e transações (já lidas por banco/repositorio.py) e
devolvem o resultado da análise. Não leem arquivos nem acessam o banco.

Gerar o JSON completo pela linha de comando: python -m nucleo
"""

from collections import Counter, defaultdict
from datetime import date, time
from decimal import Decimal, InvalidOperation

import networkx as nx
import numpy as np

# Muda quando a matemática muda: resultados guardados de versões antigas são recalculados.
VERSAO_MOTOR = "1.0"

# PROPOSTA de teste do guia matemático, NÃO fórmula aprovada pela equipe.
PESOS = {"degree": 0.15, "betweenness": 0.25, "closeness": 0.10,
         "flow": 0.25, "imbalance": 0.25}
# Valores ilustrativos do HTML original, NÃO limites de risco comprovados.
LIMIAR_ANALISE = 45.0
LIMIAR_ALTA = 70.0


def validar_dados(contas, linhas):
    """Valida contas e transações vindas do CSV ou do simulador web."""
    contas = [{k: (v or "").strip() for k, v in c.items()} for c in contas]
    ids = [c["id_conta"] for c in contas]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("A aba de contas está vazia ou tem IDs duplicados.")
    conjunto = set(ids)
    transacoes = []
    vistos = set()
    for linha in linhas:
        tid = str(linha["id_transacao"]).strip()
        origem = str(linha["conta_origem"]).strip()
        destino = str(linha["conta_destino"]).strip()
        if not tid or tid in vistos:
            raise ValueError(f"ID de transação inválido ou duplicado: {tid}")
        vistos.add(tid)
        if origem not in conjunto or destino not in conjunto:
            raise ValueError(f"Transação {tid}: conta inexistente.")
        if origem == destino:
            raise ValueError(f"Transação {tid}: origem e destino iguais.")
        try:
            valor_centavos = int((Decimal(str(linha["valor"]).strip()) * 100).quantize(Decimal("1")))
            data_tx = date.fromisoformat(str(linha["data"]).strip())
            hora_tx = time.fromisoformat(str(linha["hora"]).strip())
        except (InvalidOperation, ValueError) as erro:
            raise ValueError(f"Transação {tid}: valor/data/hora inválidos.") from erro
        if valor_centavos <= 0:
            raise ValueError(f"Transação {tid}: valor precisa ser positivo.")
        transacoes.append({
            "id": tid, "de": origem, "para": destino,
            "valor": valor_centavos / 100, "centavos": valor_centavos,
            "data": data_tx.isoformat(), "hora": hora_tx.strftime("%H:%M"),
            "tipo": str(linha["tipo_transacao"]).strip(),
        })
    return contas, transacoes


def construir_grafos(contas, transacoes):
    """Etapa 2: grafo dirigido agregado; simetrização só onde necessário."""
    grafo = nx.DiGraph()
    for conta in contas:
        grafo.add_node(conta["id_conta"], tipo=conta["tipo_titular"])
    for t in transacoes:
        u, v = t["de"], t["para"]
        if not grafo.has_edge(u, v):
            grafo.add_edge(u, v, quantidade=0, centavos=0)
        grafo[u][v]["quantidade"] += 1
        grafo[u][v]["centavos"] += t["centavos"]
    # Louvain precisa de grafo não direcionado. O peso é a QUANTIDADE
    # de transações, somando as duas direções, para medir conectividade.
    nao_dirigido = nx.Graph()
    nao_dirigido.add_nodes_from(grafo.nodes)
    for u, v, attrs in grafo.edges(data=True):
        if not nao_dirigido.has_edge(u, v):
            nao_dirigido.add_edge(u, v, weight=0)
        nao_dirigido[u][v]["weight"] += attrs["quantidade"]
    return grafo, nao_dirigido


def calcular_matrizes(grafo, nao_dirigido, ids):
    """Etapa 3: A, W, D, L dirigidas e Laplaciana simétrica para espectral."""
    n = len(ids)
    indice = {conta: i for i, conta in enumerate(ids)}
    A = np.zeros((n, n), dtype=int)
    W = np.zeros((n, n), dtype=float)
    for u, v, attrs in grafo.edges(data=True):
        i, j = indice[u], indice[v]
        A[i, j] = 1
        W[i, j] = attrs["centavos"] / 100
    d_saida = A.sum(axis=1)
    D = np.diag(d_saida)
    L = D - A  # na parte dirigida, grau de SAÍDA; L não é simétrica.

    # Para eigenvalores reais e comunidades, usamos estrutura sem direção.
    As = np.zeros((n, n), dtype=int)
    for u, v in nao_dirigido.edges:
        i, j = indice[u], indice[v]
        As[i, j] = 1
        As[j, i] = 1
    Ds = np.diag(As.sum(axis=1))
    Ls = Ds - As
    return {"A": A, "W": W, "D": D, "L": L,
            "A_simetrica": As, "D_simetrica": Ds, "L_simetrica": Ls}


def calcular_metricas(grafo, transacoes):
    """Etapas 4 e 5: degree/fluxo financeiro e centralidades."""
    entradas = Counter()
    saidas = Counter()
    for t in transacoes:
        entradas[t["para"]] += t["centavos"]
        saidas[t["de"]] += t["centavos"]
    # Caminhos mínimos por número de saltos (não pelo valor financeiro).
    bet = nx.betweenness_centrality(grafo, normalized=True, weight=None)
    # Closeness de SAÍDA: quão facilmente uma conta alcança as outras.
    # NetworkX em DiGraph mede, por padrão, caminhos de entrada;
    # por isso usamos a visão reversa.
    clos = nx.closeness_centrality(grafo.reverse(copy=False), wf_improved=True)
    resultado = {}
    for id_conta in grafo.nodes:
        ent, sai = entradas[id_conta], saidas[id_conta]
        fluxo = ent + sai
        resultado[id_conta] = {
            "inDeg": grafo.in_degree(id_conta),
            "outDeg": grafo.out_degree(id_conta),
            "degree": grafo.in_degree(id_conta) + grafo.out_degree(id_conta),
            "entrada": round(ent / 100, 2),
            "saida": round(sai / 100, 2),
            "flow": round(fluxo / 100, 2),
            "imbalance": abs(ent - sai) / fluxo if fluxo else 0.0,
            "betw": float(bet[id_conta]),
            "close": float(clos[id_conta]),
            "qtd_transacoes_entrada": sum(t["para"] == id_conta for t in transacoes),
            "qtd_transacoes_saida": sum(t["de"] == id_conta for t in transacoes),
        }
    return resultado


def descobrir_comunidades(grafo_nao_dirigido, metricas):
    """Etapa 6: Louvain de verdade, com resultado reproduzível (seed=42)."""
    comunidades = nx.community.louvain_communities(
        grafo_nao_dirigido, weight="weight", resolution=1, seed=42
    )
    # Ordenação estável para o id 1, 2, 3... não variar arbitrariamente.
    comunidades = sorted((sorted(c) for c in comunidades), key=lambda c: c[0])
    for numero, membros in enumerate(comunidades, start=1):
        for id_conta in membros:
            metricas[id_conta]["com"] = numero
    # Sem arestas (ex.: período filtrado vazio) a modularidade não é definida.
    modularidade = (nx.community.modularity(grafo_nao_dirigido, [set(c) for c in comunidades], weight="weight")
                    if grafo_nao_dirigido.number_of_edges() else 0.0)
    return comunidades, float(modularidade)


def analise_espectral(matrizes, grafo_nao_dirigido, ids):
    """Etapa 7: resolve L v = lambda v na Laplaciana simétrica."""
    autovalores, autovetores = np.linalg.eigh(matrizes["L_simetrica"])
    autovalores[np.abs(autovalores) < 1e-10] = 0.0
    componentes = nx.number_connected_components(grafo_nao_dirigido)
    # Centralidade de autovetor é diferente de autovetores da Laplaciana.
    # Ela aparece como informação extra no HTML, mas não entra no score proposto.
    A_s = matrizes["A_simetrica"].astype(float)
    a_valores, a_vetores = np.linalg.eigh(A_s)
    vetor_centralidade = np.abs(a_vetores[:, int(np.argmax(a_valores))])
    return {
        "matriz_utilizada": "L_simetrica = D_simetrica - A_simetrica",
        "equacao": "L v = lambda v",
        "autovalores": [round(float(x), 10) for x in autovalores],
        "segundo_menor_autovalor": round(float(autovalores[1]), 10) if len(ids) > 1 else None,
        "componentes_conexas": componentes,
        "observacao": "Autovalores descrevem a estrutura da rede, não risco. A Laplaciana simétrica ignora a direção das transferências.",
        "vetor_segundo_autovalor": {id_conta: round(float(autovetores[i, 1]), 8) for i, id_conta in enumerate(ids)} if len(ids) > 1 else {},
        "centralidade_autovetor": {id_conta: float(vetor_centralidade[i]) for i, id_conta in enumerate(ids)},
    }


def min_max(valores):
    menor, maior = min(valores), max(valores)
    # Sem variação, a métrica não permite diferenciar contas.
    return [0.0 if maior == menor else (x - menor) / (maior - menor) for x in valores]


def score_e_ranking(contas, metricas, espectral):
    """Etapa 8: normalização min-max e Score 0–100 PROVISÓRIO."""
    ids = [c["id_conta"] for c in contas]
    nomes = {"degree": "degree", "betweenness": "betw", "closeness": "close",
             "flow": "flow", "imbalance": "imbalance"}
    normalizados = {
        metrica: dict(zip(ids, min_max([metricas[c][campo] for c in ids])))
        for metrica, campo in nomes.items()
    }
    lista = []
    for conta in contas:
        id_conta = conta["id_conta"]
        m = metricas[id_conta]
        nota = 100 * sum(PESOS[k] * normalizados[k][id_conta] for k in PESOS)
        nota = round(nota, 2)
        status = ("Alta relevância" if nota >= LIMIAR_ALTA else
                  "Em análise" if nota >= LIMIAR_ANALISE else
                  "Revisar" if nota >= LIMIAR_ANALISE * 0.66 else "Normal")
        lista.append({
            "id": id_conta, "id_conta": id_conta,
            "titular": conta["tipo_titular"], "tipo_titular": conta["tipo_titular"],
            "data_abertura": conta["data_abertura"],
            **m, "eig": espectral["centralidade_autovetor"][id_conta],
            "score": nota, "status": status,
            "normalizado": {k: round(normalizados[k][id_conta], 6) for k in PESOS},
        })
    lista.sort(key=lambda x: (-x["score"], x["id"]))
    for posicao, conta in enumerate(lista, start=1):
        conta["ranking"] = posicao
    return lista


def detectar_padroes(grafo, ranking):
    """Heurísticas simples para os padrões previstos no HTML. Não detectam fraude."""
    casos = []
    ids = sorted(grafo.nodes)
    for c in ids:
        if grafo.in_degree(c) >= 3:
            casos.append({"tipo": "Fan-in", "conta": c,
                          "exemplo": sorted(grafo.predecessors(c)),
                          "criterio": "3 ou mais contas de origem distintas"})
        if grafo.out_degree(c) >= 3:
            casos.append({"tipo": "Fan-out", "conta": c,
                          "exemplo": sorted(grafo.successors(c)),
                          "criterio": "3 ou mais contas de destino distintas"})
    # Cadeia de 4 contas/3 arestas, apenas exemplos (não exaustivo).
    exemplos_cadeia = []
    for a in ids:
        for b in sorted(grafo.successors(a)):
            for c in sorted(grafo.successors(b)):
                for d in sorted(grafo.successors(c)):
                    caminho = [a, b, c, d]
                    if len(set(caminho)) == 4:
                        exemplos_cadeia.append(caminho)
                        if len(exemplos_cadeia) >= 5:
                            break
                if len(exemplos_cadeia) >= 5:
                    break
            if len(exemplos_cadeia) >= 5:
                break
        if len(exemplos_cadeia) >= 5:
            break
    for caminho in exemplos_cadeia:
        casos.append({"tipo": "Cadeia de repasse", "conta": caminho[1],
                      "exemplo": caminho,
                      "criterio": "sequência simples de 3 transferências; valores/tempo não comparados"})
    for conta in sorted(ranking, key=lambda c: (-c["degree"], c["id"]))[:3]:
        casos.append({"tipo": "Hub", "conta": conta["id"],
                      "exemplo": conta["degree"],
                      "criterio": "entre as 3 maiores contagens de conexões"})
    for conta in sorted(ranking, key=lambda c: (-c["betw"], c["id"]))[:3]:
        casos.append({"tipo": "Ponte", "conta": conta["id"],
                      "exemplo": round(conta["betw"], 6),
                      "criterio": "entre as 3 maiores Betweenness dirigidas"})
    return casos


def calcular(contas_origem, transacoes):
    """Executa todas as etapas em memória, sem ler nem gravar arquivos.

    Usado por python -m nucleo e pelo simulador web (app/servidor.py). As listas recebidas
    não são alteradas.
    """
    transacoes = [dict(t) for t in transacoes]
    ids = [c["id_conta"] for c in contas_origem]
    grafo, simetrico = construir_grafos(contas_origem, transacoes)
    matrizes = calcular_matrizes(grafo, simetrico, ids)
    metricas = calcular_metricas(grafo, transacoes)
    comunidades, modularidade = descobrir_comunidades(simetrico, metricas)
    espectral = analise_espectral(matrizes, simetrico, ids)
    ranking = score_e_ranking(contas_origem, metricas, espectral)
    por_id = {c["id"]: c for c in ranking}
    padroes = detectar_padroes(grafo, ranking)

    # Cada transação é preservada; a indicação de status usa a maior
    # classificação das DUAS CONTAS, não prova nada sobre a transação.
    for t in transacoes:
        nota = max(por_id[t["de"]]["score"], por_id[t["para"]]["score"])
        t["status"] = "Alta relevância" if nota >= LIMIAR_ALTA else "Em análise" if nota >= LIMIAR_ANALISE else "Normal"
        del t["centavos"]

    resumo_comunidades = []
    for numero, membros in enumerate(comunidades, start=1):
        grupo = set(membros)
        incidentes = [t for t in transacoes if t["de"] in grupo or t["para"] in grupo]
        internas = [t for t in transacoes if t["de"] in grupo and t["para"] in grupo]
        principal = sorted((por_id[c] for c in membros), key=lambda x: (-x["degree"], x["id"]))[0]
        resumo_comunidades.append({
            "id": numero, "contas": membros, "quantidade_contas": len(membros),
            "quantidade_transacoes_incidentes": len(incidentes),
            "quantidade_transacoes_internas": len(internas),
            "volume_incidente": round(sum(t["valor"] for t in incidentes), 2),
            "volume_interno": round(sum(t["valor"] for t in internas), 2),
            "conta_mais_conectada": principal["id"],
        })

    dados = {
        "projeto": "NEXO — protótipo backend matemático",
        "fonte": "Nexo - Base de dados(1).xlsx (abas Contas e Transacoes, exportadas para CSV)",
        "provisorio": True,
        "parametros": {
            "pesos_score": PESOS, "formula_score": "100 * soma(peso * minmax(metrica))",
            "limiares_ilustrativos": {"em_analise": LIMIAR_ANALISE, "alta_relevancia": LIMIAR_ALTA},
            "grafo_centralidades": "dirigido, arestas distintas e caminhos por numero de saltos",
            "grafo_louvain": "nao dirigido, peso = quantidade de transacoes por par",
            "closeness": "direcao de saida e correcao para vertices nao alcancaveis",
            "matriz_D": "grau de saida no grafo dirigido",
        },
        "dashboard": {
            "total_contas": len(contas_origem), "total_transacoes": len(transacoes),
            "total_arestas_dirigidas_distintas": grafo.number_of_edges(),
            "total_comunidades": len(comunidades),
            "contas_em_analise": sum(c["status"] in ("Em análise", "Alta relevância") for c in ranking),
            "volume_total": round(sum(t["valor"] for t in transacoes), 2),
            "modularidade_louvain": round(modularidade, 6),
        },
        "contas": ranking,
        "transacoes": transacoes,
        "rede": {"nos": [{"id": c["id"], "com": c["com"], "degree": c["degree"],
                           "score": c["score"], "status": c["status"]} for c in ranking],
                 "arestas": [{"de": u, "para": v, "quantidade": a["quantidade"],
                              "valor_total": round(a["centavos"] / 100, 2)}
                             for u, v, a in sorted(grafo.edges(data=True))]},
        "matrizes": {"ordem_contas": ids,
                     **{nome: matriz.tolist() for nome, matriz in matrizes.items()}},
        "espectral": espectral,
        "comunidades": resumo_comunidades,
        "padroes": padroes,
        "observacoes": [
            "Dados ficticios e resultados de natureza academica.",
            "Comunidades reais do Louvain podem ser diferentes das comunidades planejadas no Excel ou simuladas no HTML.",
            "Score, pesos, classificacoes e deteccao de padroes sao ilustrativos e precisam de validacao.",
            "Nao concluir fraude ou irregularidade a partir destas metricas.",
            "Matrizes/centralidades usam conexoes dirigidas distintas; 160 transferencias brutas continuam preservadas.",
        ],
    }
    return dados
