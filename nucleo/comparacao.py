"""NEXO — comparação lado a lado entre duas análises (Fase 4).

Compara dois resultados do motor (dois períodos, a base e uma simulação, dois cenários):
mudanças por conta (score, ranking, prioridade de risco, comunidade, degree, betweenness,
fluxo), conexões que surgiram ou sumiram e os indicadores gerais.

Comunidades: o número que o Louvain dá a cada comunidade muda de uma análise para outra.
Por isso "mudou de comunidade" é medido pelo GRUPO, não pelo número: a conta mudou se o
conjunto de contas que estava com ela é diferente (a maioria dos antigos colegas saiu).
"""

INDICADORES = ["total_transacoes", "volume_total", "total_comunidades", "total_arestas_dirigidas_distintas",
               "contas_em_analise", "modularidade_louvain"]


def _grupos(resultado):
    """{conta: conjunto de contas da mesma comunidade}."""
    por_com = {}
    for c in resultado["contas"]:
        por_com.setdefault(c["com"], set()).add(c["id"])
    return {c["id"]: por_com[c["com"]] for c in resultado["contas"]}


def _comunidades_vizinhas(resultado):
    """{conta: comunidades (diferentes da própria) com que ela transaciona}."""
    com = {c["id"]: c["com"] for c in resultado["contas"]}
    viz = {cid: set() for cid in com}
    for a in resultado["rede"]["arestas"]:
        if com[a["de"]] != com[a["para"]]:
            viz[a["de"]].add(com[a["para"]])
            viz[a["para"]].add(com[a["de"]])
    return viz


def comparar(a, b):
    """Diferenças de b em relação a a (a = "antes"/esquerda, b = "depois"/direita)."""
    ca, cb = {c["id"]: c for c in a["contas"]}, {c["id"]: c for c in b["contas"]}
    ga, gb = _grupos(a), _grupos(b)
    va, vb = _comunidades_vizinhas(a), _comunidades_vizinhas(b)
    arestas_a = {(x["de"], x["para"]): x for x in a["rede"]["arestas"]}
    arestas_b = {(x["de"], x["para"]): x for x in b["rede"]["arestas"]}

    contas = []
    for cid in sorted(set(ca) | set(cb)):
        x, y = ca.get(cid), cb.get(cid)
        if x is None or y is None:
            contas.append({"id": cid, "so_em": "a" if y is None else "b"})
            continue
        antigos, novos = ga[cid] - {cid}, gb[cid] - {cid}
        mudou_grupo = bool(antigos or novos) and len(antigos & novos) < max(len(antigos), len(novos)) / 2
        contas.append({
            "id": cid,
            "score": [x["score"], y["score"]], "delta_score": round(y["score"] - x["score"], 2),
            "ranking": [x["ranking"], y["ranking"]], "delta_ranking": x["ranking"] - y["ranking"],
            "risco": [x.get("risco", 0), y.get("risco", 0)], "nivel": [x.get("nivel_risco"), y.get("nivel_risco")],
            "comunidade": [x["com"], y["com"]], "mudou_comunidade": mudou_grupo,
            "degree": [x["degree"], y["degree"]], "betweenness": [round(x["betw"], 6), round(y["betw"], 6)],
            "flow": [x["flow"], y["flow"]],
            "comunidades_vizinhas": [len(va[cid]), len(vb[cid])],
            "indicios_novos": sorted(set(y.get("indicios", [])) - set(x.get("indicios", []))),
            "indicios_saiu": sorted(set(x.get("indicios", [])) - set(y.get("indicios", []))),
        })

    comparaveis = [c for c in contas if "so_em" not in c]

    def top(chave, n=5):
        return [c["id"] for c in sorted(comparaveis, key=lambda c: (-abs(c[chave]), c["id"])) if c[chave]][:n]

    return {
        "indicadores": {k: [a["dashboard"].get(k), b["dashboard"].get(k)] for k in INDICADORES},
        "risco_por_nivel": [a.get("risco", {}).get("resumo", {}).get("por_nivel", {}),
                            b.get("risco", {}).get("resumo", {}).get("por_nivel", {})],
        "contas": contas,
        "arestas_novas": [{"de": k[0], "para": k[1], "quantidade": v["quantidade"], "valor": v["valor_total"]}
                          for k, v in sorted(arestas_b.items()) if k not in arestas_a],
        "arestas_removidas": [{"de": k[0], "para": k[1], "quantidade": v["quantidade"], "valor": v["valor_total"]}
                              for k, v in sorted(arestas_a.items()) if k not in arestas_b],
        "destaques": {
            "score": top("delta_score"),
            "ranking": top("delta_ranking"),
            "mudaram_comunidade": [c["id"] for c in comparaveis if c["mudou_comunidade"]],
            "mudaram_prioridade": [c["id"] for c in comparaveis if c["nivel"][0] != c["nivel"][1]],
            "mais_pontes": [c["id"] for c in sorted(comparaveis, key=lambda c: (c["comunidades_vizinhas"][0] - c["comunidades_vizinhas"][1], c["id"]))
                            if c["comunidades_vizinhas"][1] > c["comunidades_vizinhas"][0]][:5],
        },
    }


def compacto(resultado):
    """O que a tela de histórico e comparação precisa de um resultado (sem matrizes nem transações)."""
    campos = ("id", "com", "degree", "inDeg", "outDeg", "score", "ranking", "status", "betw", "flow",
              "risco", "nivel_risco", "indicios")
    return {"dashboard": resultado["dashboard"],
            "contas": [{k: c.get(k) for k in campos} for c in resultado["contas"]],
            "rede": {"arestas": resultado["rede"]["arestas"]},
            "risco": {"resumo": resultado.get("risco", {}).get("resumo", {})},
            "comunidades": [{"id": g["id"], "contas": g["contas"]} for g in resultado.get("comunidades", [])]}
