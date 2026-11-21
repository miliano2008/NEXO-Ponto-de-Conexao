"""NEXO — conteúdo dos relatórios (Fase 5), independente do formato do arquivo.

Um relatório é um DOCUMENTO com identificação e seções; cada seção tem BLOCOS:
  paragrafo · aviso · lista · indicadores · tabela · grafico
Os renderizadores (app/exportacao/) transformam o mesmo documento em PDF, Excel, CSV,
Word e PowerPoint. Assim os números são sempre os mesmos em todos os formatos.

Tabelas guardam os valores BRUTOS (números de verdade) e o formato de cada coluna:
o Excel recebe números somáveis; o PDF e o Word recebem o texto já formatado.
Gráficos guardam categorias e séries: cada formato desenha o gráfico nativo dele
(nada de capturas de tela).

Rastreabilidade: o documento leva o número e a assinatura da análise, a versão do motor,
os limites usados e, em cada indício, o identificador da regra de origem.
As conclusões são montadas por modelos de texto a partir das regras, sem afirmar fraude.
"""

from collections import Counter, defaultdict
from datetime import date

NIVEIS = ["Alta", "Moderada", "Baixa", "Sem indícios"]
AVISO = ("Relevância estrutural e indícios de risco NÃO são prova de irregularidade: indicam onde a "
         "verificação humana deve começar. Score, pesos e limites são provisórios (protótipo acadêmico).")


# ---------------------------------------------------------------- formatação (padrão brasileiro)

def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def num(v, casas=0):
    if v is None:
        return "—"
    texto = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto


def data_br(iso):
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def celula(valor, fmt):
    """(valor, formato) de uma célula: a célula pode trazer o próprio formato como (valor, fmt)."""
    if isinstance(valor, tuple):
        return valor
    return valor, fmt


def formatar(valor, fmt):
    """Texto de uma célula conforme o formato da coluna."""
    valor, fmt = celula(valor, fmt)
    if valor is None or valor == "":
        return "—"
    if fmt == "brl":
        return brl(valor)
    if fmt == "int":
        return num(valor)
    if fmt.startswith("dec"):
        return num(valor, int(fmt[3:] or 2))
    if fmt == "pct":
        return f"{num(valor * 100, 1)}%"
    if fmt == "data":
        return data_br(valor)
    if fmt == "delta":
        return f"{'+' if valor > 0 else ''}{num(valor, 1)}"
    return str(valor)


# ---------------------------------------------------------------- blocos

def paragrafo(texto):
    return {"tipo": "paragrafo", "texto": texto}


def aviso(texto):
    return {"tipo": "aviso", "texto": texto}


def lista(itens):
    return {"tipo": "lista", "itens": list(itens)}


def indicadores(itens):
    """itens: (rótulo, texto do valor, nota opcional)."""
    return {"tipo": "indicadores", "itens": [{"rotulo": r, "valor": v, "nota": n} for r, v, n in itens]}


def tabela(titulo, nome, colunas, linhas, *, so_dados=False, nota=""):
    """colunas: (nome, formato); nome: nome curto (aba do Excel / arquivo do CSV).
    so_dados=True: tabela completa que só vai para Excel e CSV (no PDF/Word/PPT fica a versão resumida)."""
    return {"tipo": "tabela", "titulo": titulo, "nome": nome, "colunas": [{"nome": c, "fmt": f} for c, f in colunas],
            "linhas": [list(l) for l in linhas], "so_dados": so_dados, "nota": nota}


def grafico(titulo, forma, categorias, series, fmt="int", nota=""):
    """forma: colunas · barras (horizontais) · pizza · colunas_agrupadas · linha.
    series: [(nome, [valores])]. fmt: formato dos números (int, brl, dec1...)."""
    return {"tipo": "grafico", "titulo": titulo, "forma": forma, "categorias": [str(c) for c in categorias],
            "series": [{"nome": n, "valores": [float(v) for v in vals]} for n, vals in series], "fmt": fmt, "nota": nota}


def secao(titulo, *blocos):
    return {"titulo": titulo, "blocos": [b for b in blocos if b]}


# ---------------------------------------------------------------- relatório da análise

def _descrever_recorte(recorte):
    partes = [f"{data_br(recorte['inicio_efetivo'])} a {data_br(recorte['fim_efetivo'])}"]
    if recorte.get("dias") and not (recorte.get("inicio") or recorte.get("fim")):
        partes.append(f"últimos {recorte['dias']} dias")
    if recorte.get("tipos"):
        partes.append("tipos: " + ", ".join(recorte["tipos"]))
    if recorte.get("valor_min") is not None:
        partes.append(f"valor ≥ {brl(recorte['valor_min'])}")
    if recorte.get("valor_max") is not None:
        partes.append(f"valor ≤ {brl(recorte['valor_max'])}")
    return " · ".join(partes)


def _conclusoes(dados):
    """Modelos de texto preenchidos com os resultados. Nunca afirmam fraude."""
    risco, contas = dados["risco"], dados["contas"]
    altas = sorted((c for c in contas if c["nivel_risco"] == "Alta"), key=lambda c: -c["risco"])
    moderadas = [c for c in contas if c["nivel_risco"] == "Moderada"]
    frases = []
    rec = dados["simulacao"]["recorte"]
    frases.append(f"Foram analisadas {num(rec['transacoes'])} transações entre {num(len(contas))} contas, de "
                  f"{data_br(rec['inicio_efetivo'])} a {data_br(rec['fim_efetivo'])}, somando {brl(dados['dashboard']['volume_total'])}.")
    if altas:
        nomes = ", ".join(f"{c['id']} ({c['risco']} pontos)" for c in altas[:5])
        frases.append(f"{len(altas)} conta(s) ficaram com prioridade ALTA de verificação: {nomes}. "
                      "Recomenda-se começar a análise humana por elas, conferindo as evidências listadas na seção de contas priorizadas.")
    elif moderadas:
        frases.append(f"Nenhuma conta ficou com prioridade alta; {len(moderadas)} ficaram com prioridade moderada.")
    else:
        frases.append("Nenhuma conta atingiu prioridade moderada ou alta com os limites atuais.")
    regras = sorted(risco["regras"], key=lambda r: -len(r["contas"]))
    if regras and regras[0]["contas"]:
        r = regras[0]
        frases.append(f"O indício mais frequente foi “{r['nome']}” (regra {r['id']}), presente em {len(r['contas'])} conta(s).")
    if risco["circuitos"]:
        frases.append(f"Foram encontrados {len(risco['circuitos'])} circuito(s) recorrente(s) de transferências que voltam à origem: "
                      + "; ".join(" → ".join(c + [c[0]]) for c in risco["circuitos"][:3]) + ".")
    destaque = [c for c in risco["comunidades"] if c["destaque"]]
    if destaque:
        frases.append(f"{len(destaque)} comunidade(s) concentram contas sinalizadas: "
                      + ", ".join(f"comunidade {c['comunidade']} ({len(c['sinalizadas'])} de {len(c['contas'])} contas)" for c in destaque[:4]) + ".")
    frases.append(f"A rede se divide em {dados['dashboard']['total_comunidades']} comunidades (modularidade "
                  f"{num(dados['dashboard']['modularidade_louvain'], 3)}); valores acima de 0,3 indicam grupos bem definidos.")
    simuladas = dados["simulacao"]["transacoes_simuladas"]
    if simuladas:
        frases.append(f"Este resultado inclui {simuladas} transação(ões) SIMULADA(S), que não existem na base real.")
    frases.append("Estes resultados são indícios para priorizar a verificação e não constituem prova de irregularidade.")
    return frases


def _exemplo(padrao):
    """Contrapartes do padrão (lista de contas) ou a medida que o define (hub: conexões; ponte: betweenness)."""
    exemplo = padrao.get("exemplo")
    if isinstance(exemplo, list):
        return ", ".join(map(str, exemplo))
    if padrao["tipo"] == "Hub":
        return f"{exemplo} conexões"
    if isinstance(exemplo, float):
        return f"betweenness {num(exemplo, 3)}"
    return "" if exemplo is None else str(exemplo)


def relatorio_analise(dados, usuario, gerado_em):
    """Documento completo da análise atual (recorte + simulação do usuário).
    `dados`: resposta de servidor.resultados(); `usuario`: {nome, cargo_nome}; `gerado_em`: datetime."""
    d, risco, contas = dados["dashboard"], dados["risco"], dados["contas"]
    sim, info = dados["simulacao"], dados["analise"]
    rec = sim["recorte"]
    por_nivel = risco["resumo"]["por_nivel"]
    n, m = d["total_contas"], d["total_arestas_dirigidas_distintas"]

    identificacao = [
        ("Relatório", "Análise da rede de transações"),
        ("Gerado em", gerado_em.strftime("%d/%m/%Y %H:%M")),
        ("Gerado por", f"{usuario['nome']} ({usuario['cargo_nome']})"),
        ("Período e filtros", _descrever_recorte(rec)),
        ("Transações simuladas", str(sim["transacoes_simuladas"]) if sim["transacoes_simuladas"] else "nenhuma (só a base)"),
        ("Análise", f"nº {info['id']}" if info.get("id") else "não guardada (inclui simulação)"),
        ("Assinatura", info["assinatura"]),
        ("Versão do motor", info["versao_motor"]),
        ("Fonte dos dados", sim["fonte_dados"]),
    ]

    # 1. indicadores
    s1 = secao("1. Indicadores gerais",
               indicadores([("Transações", num(rec["transacoes"]), ""), ("Contas", num(n), ""),
                            ("Volume total", brl(d["volume_total"]), ""),
                            ("Comunidades", num(d["total_comunidades"]), f"modularidade {num(d['modularidade_louvain'], 3)}"),
                            ("Conexões distintas", num(m), f"densidade {num(m / (n * (n - 1)), 4) if n > 1 else '—'}"),
                            ("Prioridade alta", num(por_nivel.get("Alta", 0)), f"moderada: {por_nivel.get('Moderada', 0)}")]),
               paragrafo("Cada número deste relatório vem da análise identificada acima (número e assinatura). "
                         "Os indícios citam a regra de origem pelo identificador entre parênteses."))

    # 2. gráficos
    por_tipo = defaultdict(float)
    for t in dados["transacoes"]:
        por_tipo[t["tipo"]] += t["valor"]
    semanas = defaultdict(float)
    for t in dados["transacoes"]:
        ano, sem, _ = date.fromisoformat(t["data"]).isocalendar()
        semanas[(ano, sem)] += t["valor"]
    top = sorted(contas, key=lambda c: -c["score"])[:10]
    regras_ord = sorted(risco["regras"], key=lambda r: -len(r["contas"]))
    s2 = secao("2. Gráficos",
               grafico("Contas por prioridade de verificação", "pizza", NIVEIS, [("Contas", [por_nivel.get(k, 0) for k in NIVEIS])]),
               grafico("10 contas com maior score de relevância", "barras", [c["id"] for c in top],
                       [("Score", [c["score"] for c in top])], fmt="dec1"),
               grafico("Volume por modalidade", "colunas", list(por_tipo), [("Volume (R$)", list(por_tipo.values()))], fmt="brl"),
               grafico("Volume por semana", "linha", [f"Sem. {s:02d}" for (_, s) in sorted(semanas)],
                       [("Volume (R$)", [semanas[k] for k in sorted(semanas)])], fmt="brl"),
               grafico("Contas por indício", "barras", [r["nome"] for r in regras_ord],
                       [("Contas", [len(r["contas"]) for r in regras_ord])]))

    # 3. contas priorizadas
    priorizadas = sorted((c for c in contas if c["nivel_risco"] in ("Alta", "Moderada")), key=lambda c: (-c["risco"], c["ranking"]))
    linhas = []
    evidencias = []
    for c in priorizadas:
        ind = risco["contas"][c["id"]]["indicios"]
        linhas.append([c["id"], c["nivel_risco"], c["risco"], c["score"], c["ranking"], c["com"],
                       ", ".join(f"{i['nome']} ({i['regra']})" for i in ind)])
        evidencias.extend([c["id"], i["nome"], i["regra"], i["peso"], i["evidencia"]] for i in ind)
    s3 = secao("3. Contas priorizadas",
               paragrafo(f"{len(priorizadas)} conta(s) com prioridade alta ou moderada. Pontos = soma dos pesos dos indícios (máximo 100)."),
               tabela("Contas priorizadas", "Priorizadas",
                      [("Conta", "txt"), ("Prioridade", "txt"), ("Pontos", "int"), ("Score", "dec1"), ("Ranking", "int"),
                       ("Comunidade", "int"), ("Indícios (regra)", "txt")], linhas),
               tabela("Evidências de cada indício", "Evidencias",
                      [("Conta", "txt"), ("Indício", "txt"), ("Regra", "txt"), ("Peso", "int"), ("Evidência", "txt")], evidencias))

    # 4. padrões
    linhas_padroes = [[" → ".join(c + [c[0]]), len(c), "Circuito recorrente (ciclo)"] for c in risco["circuitos"]]
    contagem = Counter(p["tipo"] for p in dados["padroes"])
    s4 = secao("4. Padrões identificados",
               paragrafo("Padrões estruturais encontrados na rede: " + (", ".join(f"{k}: {v}" for k, v in contagem.items()) or "nenhum") + "."),
               tabela("Circuitos recorrentes", "Circuitos", [("Circuito", "txt"), ("Contas", "int"), ("Padrão", "txt")], linhas_padroes)
               if linhas_padroes else paragrafo("Nenhum circuito recorrente com os limites atuais."),
               tabela("Padrões estruturais", "Padroes", [("Padrão", "txt"), ("Conta", "txt"), ("Contrapartes ou medida", "txt"), ("Critério", "txt")],
                      [[p["tipo"], p.get("conta", ""), _exemplo(p), p.get("criterio", "")] for p in dados["padroes"]]))

    # 5. comunidades
    risco_com = {c["comunidade"]: c for c in risco["comunidades"]}
    linhas_com = [[c["id"], c["quantidade_contas"], len(risco_com[c["id"]]["sinalizadas"]), c["quantidade_transacoes_internas"],
                   c["volume_interno"], risco_com[c["id"]]["densidade"], c["conta_mais_conectada"],
                   "Sim" if risco_com[c["id"]]["destaque"] else "Não"] for c in dados["comunidades"]]
    s5 = secao("5. Comunidades (Louvain)",
               tabela("Comunidades", "Comunidades",
                      [("Comunidade", "int"), ("Contas", "int"), ("Sinalizadas", "int"), ("Transações internas", "int"),
                       ("Volume interno", "brl"), ("Densidade", "pct"), ("Mais conectada", "txt"), ("Em destaque", "txt")], linhas_com),
               grafico("Volume interno por comunidade", "colunas", [f"Com. {c['id']}" for c in dados["comunidades"]],
                       [("Volume interno (R$)", [c["volume_interno"] for c in dados["comunidades"]])], fmt="brl"))

    # 6. regras e limites (rastreabilidade)
    s6 = secao("6. Regras de risco e limites usados",
               tabela("Regras e limites", "Regras", [("Regra", "txt"), ("Identificador", "txt"), ("O que mede", "txt"),
                                                      ("Limite usado", "txt"), ("Peso", "int"), ("Contas", "int")],
                      [[r["nome"], r["id"], r["mede"], r["limite"], r["peso"], len(r["contas"])] for r in risco["regras"]]),
               paragrafo("Os limites podem ser ajustados pelo administrador em Configurações; o relatório registra os limites "
                         "em vigor no momento em que foi gerado."))

    # 7. conclusões
    s7 = secao("7. Conclusões", lista(_conclusoes(dados)), aviso(AVISO))

    # anexos: tabelas completas (Excel e CSV)
    s8 = secao("Anexo — dados completos",
               tabela("Todas as contas", "Contas",
                      [("Conta", "txt"), ("Titular", "txt"), ("Ranking", "int"), ("Score", "dec2"), ("Status", "txt"),
                       ("Prioridade", "txt"), ("Pontos de risco", "int"), ("Comunidade", "int"), ("Grau", "int"),
                       ("Entradas (R$)", "brl"), ("Saídas (R$)", "brl"), ("Fluxo (R$)", "brl"), ("Betweenness", "dec4"),
                       ("Closeness", "dec4"), ("Instituição (fictícia)", "txt")],
                      [[c["id"], c["tipo_titular"], c["ranking"], c["score"], c["status"], c["nivel_risco"], c["risco"],
                        c["com"], c["degree"], c["entrada"], c["saida"], c["flow"], c["betw"], c["close"],
                        dados.get("bancario", {}).get(c["id"], {}).get("instituicao", "")]
                       for c in sorted(contas, key=lambda c: c["ranking"])], so_dados=True),
               tabela("Todas as transações", "Transacoes",
                      [("Transação", "txt"), ("Data", "data"), ("Hora", "txt"), ("Origem", "txt"), ("Destino", "txt"),
                       ("Modalidade", "txt"), ("Valor (R$)", "brl"), ("Valor atípico", "txt"), ("Simulada", "txt")],
                      [[t["id"], t["data"], t["hora"], t["de"], t["para"], t["tipo"], t["valor"],
                        "Sim" if t.get("atipica") else "Não", "Sim" if t.get("simulada") else "Não"]
                       for t in dados["transacoes"]], so_dados=True),
               tabela("Limites das regras de risco", "Parametros", [("Parâmetro", "txt"), ("Valor", "txt")],
                      [[k, str(v).replace(".", ",")] for k, v in risco["parametros"].items()], so_dados=True))
    return {"titulo": "NEXO — Relatório de análise da rede", "subtitulo": _descrever_recorte(rec),
            "identificacao": identificacao, "secoes": [s1, s2, s3, s4, s5, s6, s7, s8], "aviso": AVISO,
            "arquivo": f"nexo_analise_{gerado_em.strftime('%Y%m%d_%H%M')}"}


# ---------------------------------------------------------------- relatório da comparação

def relatorio_comparacao(a, b, rotulo_a, rotulo_b, diff, usuario, gerado_em):
    """Documento da comparação lado a lado. a, b: resultados compactos; diff: comparacao.comparar(a, b)."""
    ind = diff["indicadores"]
    nomes_ind = [("total_transacoes", "Transações", "int"), ("volume_total", "Volume total", "brl"),
                 ("total_comunidades", "Comunidades", "int"), ("total_arestas_dirigidas_distintas", "Conexões distintas", "int"),
                 ("contas_em_analise", "Contas em análise", "int"), ("modularidade_louvain", "Modularidade", "dec3")]
    linhas_ind = [[nome, ind[k][0], ind[k][1], ind[k][1] - ind[k][0]] for k, nome, _ in nomes_ind]
    fmt_ind = {nome: f for _, nome, f in nomes_ind}
    from nucleo.risco import REGRA
    nomes_regra = {rid: r["nome"] for rid, r in REGRA.items()}

    contas = [c for c in diff["contas"] if "so_em" not in c]
    mudancas = sorted(contas, key=lambda c: -abs(c["delta_score"]))
    linhas = [[c["id"], c["score"][0], c["score"][1], c["delta_score"], c["ranking"][0], c["ranking"][1],
               f"{c['nivel'][0]} → {c['nivel'][1]}", f"{c['comunidade'][0]} → {c['comunidade'][1]}",
               "Sim" if c["mudou_comunidade"] else "Não", c["comunidades_vizinhas"][0], c["comunidades_vizinhas"][1],
               ", ".join(nomes_regra.get(i, i) for i in c["indicios_novos"])] for c in mudancas]
    colunas = [("Conta", "txt"), ("Score A", "dec1"), ("Score B", "dec1"), ("Variação", "delta"), ("Ranking A", "int"),
               ("Ranking B", "int"), ("Prioridade", "txt"), ("Comunidade", "txt"), ("Mudou de grupo", "txt"),
               ("Com. vizinhas A", "int"), ("Com. vizinhas B", "int"), ("Indícios novos", "txt")]
    top = mudancas[:10]
    des = diff["destaques"]
    frases = [f"Comparação entre “{rotulo_a}” (A) e “{rotulo_b}” (B).",
              f"Transações: {num(ind['total_transacoes'][0])} → {num(ind['total_transacoes'][1])}; volume: "
              f"{brl(ind['volume_total'][0])} → {brl(ind['volume_total'][1])}.",
              f"Contas com prioridade alta: {diff['risco_por_nivel'][0].get('Alta', 0)} → {diff['risco_por_nivel'][1].get('Alta', 0)}."]
    if mudancas and mudancas[0]["delta_score"]:
        c = mudancas[0]
        frases.append(f"A maior variação de score foi de {c['id']}: {num(c['score'][0], 1)} → {num(c['score'][1], 1)} "
                      f"(ranking {c['ranking'][0]}º → {c['ranking'][1]}º).")
    if des["mudaram_comunidade"]:
        frases.append(f"{len(des['mudaram_comunidade'])} conta(s) mudaram de grupo (comparado pelos membros, não pelo número): "
                      + ", ".join(des["mudaram_comunidade"][:8]) + ".")
    if des["mais_pontes"]:
        frases.append("Contas que passaram a ligar mais comunidades: " + ", ".join(des["mais_pontes"][:5]) + ".")
    frases.append(f"Conexões novas em B: {len(diff['arestas_novas'])}; conexões que deixaram de existir: {len(diff['arestas_removidas'])}.")
    frases.append("Diferenças entre períodos ou cenários orientam a verificação; não são prova de irregularidade.")

    return {"titulo": "NEXO — Relatório de comparação", "subtitulo": f"A: {rotulo_a}  ×  B: {rotulo_b}",
            "identificacao": [("Relatório", "Comparação lado a lado"), ("A", rotulo_a), ("B", rotulo_b),
                              ("Gerado em", gerado_em.strftime("%d/%m/%Y %H:%M")),
                              ("Gerado por", f"{usuario['nome']} ({usuario['cargo_nome']})")],
            "secoes": [
                secao("1. Indicadores A × B",
                      tabela("Indicadores", "Indicadores", [("Indicador", "txt"), ("A", "auto"), ("B", "auto"), ("Diferença", "auto")],
                             [[n, *[(v, fmt_ind[n]) for v in vals]] for n, *vals in linhas_ind]),
                      grafico("Contas por prioridade de verificação", "colunas_agrupadas", NIVEIS,
                              [("A", [diff["risco_por_nivel"][0].get(k, 0) for k in NIVEIS]),
                               ("B", [diff["risco_por_nivel"][1].get(k, 0) for k in NIVEIS])])),
                secao("2. Maiores mudanças",
                      grafico("Variação de score (10 maiores)", "barras", [c["id"] for c in top],
                              [("Variação", [c["delta_score"] for c in top])], fmt="dec1"),
                      tabela("Contas que mais mudaram", "Mudancas",
                             [("Conta", "txt"), ("Score A → B", "txt"), ("Variação", "delta"), ("Ranking A → B", "txt"),
                              ("Prioridade A → B", "txt"), ("Grupo", "txt"), ("Com. vizinhas", "txt"), ("Indícios novos", "txt")],
                             [[c["id"], f"{num(c['score'][0], 1)} → {num(c['score'][1], 1)}", c["delta_score"],
                               f"{c['ranking'][0]}º → {c['ranking'][1]}º", f"{c['nivel'][0]} → {c['nivel'][1]}",
                               "mudou" if c["mudou_comunidade"] else "manteve",
                               f"{c['comunidades_vizinhas'][0]} → {c['comunidades_vizinhas'][1]}",
                               ", ".join(nomes_regra.get(i, i) for i in c["indicios_novos"]) or "—"] for c in mudancas[:15]],
                             nota="A lista completa, com todas as colunas, está no Excel e no CSV.")),
                secao("3. Conexões", tabela("Conexões novas e removidas", "Conexoes",
                                            [("Origem", "txt"), ("Destino", "txt"), ("Situação", "txt"), ("Transações", "int"), ("Valor", "brl")],
                                            [[x["de"], x["para"], "Nova em B", x["quantidade"], x["valor"]] for x in diff["arestas_novas"]]
                                            + [[x["de"], x["para"], "Removida em B", x["quantidade"], x["valor"]] for x in diff["arestas_removidas"]])),
                secao("4. Conclusões", lista(frases), aviso(AVISO)),
                secao("Anexo — dados completos", tabela("Todas as contas (A × B)", "Contas", colunas, linhas, so_dados=True)),
            ],
            "aviso": AVISO, "arquivo": f"nexo_comparacao_{gerado_em.strftime('%Y%m%d_%H%M')}"}
