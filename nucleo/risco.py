"""NEXO — indícios de risco com regras explicáveis (Fase 2).

Cada regra mede algo concreto nos dados e devolve a EVIDÊNCIA: o número que disparou,
o limite usado e as transações envolvidas. Nenhuma regra afirma fraude: o resultado é
uma PRIORIDADE DE VERIFICAÇÃO para a análise humana.

Os limites que dependem da base são relativos a ela (percentis e desvio robusto), para
funcionar em qualquer recorte: período, tipo de transação, faixa de valor ou simulação.

Validação: os cenários planejados na aba "Leia-me" da planilha servem de gabarito em
testes/test_fase2.py (fan-in em C001, fan-out em C006 e C031, cadeia C011→C015, ciclos
C016→C019 e C026→C030, hub C021, contas-ponte e o volume de C025).
"""

import statistics
from collections import defaultdict
from datetime import datetime, timedelta

import networkx as nx

# Parâmetros PADRÃO das regras: exibidos no Painel de risco. O administrador ajusta em
# Configurações (Fase 5); os valores efetivos vêm de parametros_efetivos().
PARAMETROS = {
    "volume_z": 2.5,                 # desvio robusto mínimo do fluxo (mediana/MAD)
    "repasse_horas": 24,             # janela entre receber e reenviar
    "repasse_fracao": 0.8,           # fração do valor recebido que é reenviada
    "cadeia_min_transferencias": 4,  # tamanho mínimo da cadeia cronológica
    "cadeia_janela_dias": 7,         # tempo máximo entre uma transferência e a seguinte
    "ciclo_max_contas": 5,           # tamanho máximo do circuito
    "ciclo_min_repeticoes": 2,       # cada ligação do circuito aparece em pelo menos N datas
    "fan_min_contas": 4,             # contrapartes distintas para fan-in / fan-out
    "fan_proporcao": 2.0,            # recebe de N vezes mais contas do que envia (e vice-versa)
    "intermediacao_percentil": 90,   # betweenness entre as 10% maiores
    "concentracao_horas": 24,        # janela da concentração temporal
    "concentracao_min": 3,           # transações da conta dentro da janela
    "valor_percentil": 95,           # transação acima do percentil 95 da base
    "comunidade_min_contas": 2,      # contas com prioridade moderada ou alta na comunidade
}

# Como cada parâmetro aparece e pode ser ajustado na tela Configurações (faixas seguras).
# tipo: "int" ou "float"; regras: quais regras usam o parâmetro.
PARAMETROS_INFO = {
    "volume_z": {"nome": "Desvio robusto mínimo do fluxo", "tipo": "float", "min": 1.0, "max": 10.0, "unidade": "× MAD", "regras": ["volume"]},
    "repasse_horas": {"nome": "Janela do repasse", "tipo": "int", "min": 1, "max": 168, "unidade": "horas", "regras": ["repasse"]},
    "repasse_fracao": {"nome": "Fração reenviada no repasse", "tipo": "float", "min": 0.1, "max": 1.0, "unidade": "do valor recebido (0 a 1)", "regras": ["repasse"]},
    "cadeia_min_transferencias": {"nome": "Tamanho mínimo da cadeia", "tipo": "int", "min": 2, "max": 10, "unidade": "transferências", "regras": ["cadeia"]},
    "cadeia_janela_dias": {"nome": "Intervalo máximo na cadeia", "tipo": "int", "min": 1, "max": 60, "unidade": "dias", "regras": ["cadeia"]},
    "ciclo_max_contas": {"nome": "Tamanho máximo do circuito", "tipo": "int", "min": 3, "max": 8, "unidade": "contas", "regras": ["ciclo"]},
    "ciclo_min_repeticoes": {"nome": "Repetições de cada ligação do circuito", "tipo": "int", "min": 1, "max": 10, "unidade": "datas", "regras": ["ciclo"]},
    "fan_min_contas": {"nome": "Contrapartes distintas (fan-in/fan-out)", "tipo": "int", "min": 2, "max": 30, "unidade": "contas", "regras": ["fan_in", "fan_out"]},
    "fan_proporcao": {"nome": "Proporção entre origens e destinos", "tipo": "float", "min": 1.0, "max": 10.0, "unidade": "×", "regras": ["fan_in", "fan_out"]},
    "intermediacao_percentil": {"nome": "Percentil da intermediação", "tipo": "int", "min": 50, "max": 99, "unidade": "percentil", "regras": ["intermediacao"]},
    "concentracao_horas": {"nome": "Janela da concentração no tempo", "tipo": "int", "min": 1, "max": 168, "unidade": "horas", "regras": ["concentracao"]},
    "concentracao_min": {"nome": "Transações na janela", "tipo": "int", "min": 2, "max": 50, "unidade": "transações", "regras": ["concentracao"]},
    "valor_percentil": {"nome": "Percentil do valor atípico", "tipo": "int", "min": 50, "max": 99, "unidade": "percentil", "regras": ["valor"]},
    "comunidade_min_contas": {"nome": "Contas sinalizadas para destacar a comunidade", "tipo": "int", "min": 1, "max": 20, "unidade": "contas", "regras": []},
}


def validar_parametro(chave, valor):
    """Converte e confere o valor de um parâmetro. ValueError com mensagem clara se estiver fora da faixa."""
    info = PARAMETROS_INFO.get(chave)
    if info is None:
        raise ValueError(f"Parâmetro desconhecido: {chave}.")
    try:
        texto = str(valor).strip().replace(",", ".")
        numero = float(texto)
        if info["tipo"] == "int":
            if numero != int(numero):
                raise ValueError
            numero = int(numero)
    except (TypeError, ValueError) as erro:
        raise ValueError(f"{info['nome']}: informe um número{' inteiro' if info['tipo'] == 'int' else ''}.") from erro
    if not info["min"] <= numero <= info["max"]:
        minimo, maximo = (f"{v:g}".replace(".", ",") for v in (info["min"], info["max"]))
        raise ValueError(f"{info['nome']}: use um valor de {minimo} a {maximo}.")
    return numero


def parametros_efetivos(ajustes=None):
    """Padrão + ajustes do administrador ({chave: valor}); valores inválidos gravados antes são ignorados."""
    efetivos = dict(PARAMETROS)
    for chave, valor in (ajustes or {}).items():
        try:
            efetivos[chave] = validar_parametro(chave, valor)
        except ValueError:
            continue
    return efetivos


REGRAS = [
    {"id": "volume", "nome": "Volume atípico", "peso": 20,
     "mede": "Fluxo financeiro (entradas + saídas) muito acima do padrão da base.",
     "limite": "desvio robusto (mediana/MAD) ≥ {volume_z}"},
    {"id": "repasse", "nome": "Repasse rápido", "peso": 20,
     "mede": "Recebe um valor e reenvia a maior parte logo em seguida.",
     "limite": "reenvia ≥ {repasse_pct}% do valor recebido em até {repasse_horas} h"},
    {"id": "cadeia", "nome": "Cadeia de repasse", "peso": 15,
     "mede": "Participa de uma sequência de transferências em que cada conta repassa para a seguinte, em ordem cronológica.",
     "limite": "≥ {cadeia_min_transferencias} transferências encadeadas, até {cadeia_janela_dias} dias entre elas"},
    {"id": "ciclo", "nome": "Circuito recorrente", "peso": 15,
     "mede": "Participa de um circuito de transferências que volta à conta de origem, formado por ligações que se repetem.",
     "limite": "circuito de 3 a {ciclo_max_contas} contas; cada ligação em ≥ {ciclo_min_repeticoes} datas"},
    {"id": "fan_in", "nome": "Recebimentos concentrados (fan-in)", "peso": 15,
     "mede": "Recebe de muitas contas diferentes e envia para poucas.",
     "limite": "≥ {fan_min_contas} origens distintas e ≥ {fan_proporcao}× o número de destinos"},
    {"id": "fan_out", "nome": "Envios dispersos (fan-out)", "peso": 15,
     "mede": "Envia para muitas contas diferentes e recebe de poucas.",
     "limite": "≥ {fan_min_contas} destinos distintos e ≥ {fan_proporcao}× o número de origens"},
    {"id": "intermediacao", "nome": "Intermediação", "peso": 15,
     "mede": "Está no caminho entre muitas outras contas (betweenness alta): atua como hub ou ponte.",
     "limite": "betweenness entre as {intermediacao_top}% maiores da base"},
    {"id": "ponte", "nome": "Ponte entre comunidades", "peso": 10,
     "mede": "Transaciona com contas de outra comunidade: é por ela que o dinheiro entra ou sai do grupo.",
     "limite": "≥ 1 transação com outra comunidade (Louvain)"},
    {"id": "concentracao", "nome": "Concentração no tempo", "peso": 10,
     "mede": "Muitas transações num intervalo curto.",
     "limite": "≥ {concentracao_min} transações em {concentracao_horas} h"},
    {"id": "valor", "nome": "Transação de valor atípico", "peso": 10,
     "mede": "Envia ou recebe uma transação de valor muito acima do padrão da base.",
     "limite": "valor acima do percentil {valor_percentil} das transações"},
]
REGRA = {r["id"]: r for r in REGRAS}

NIVEIS = [(60, "Alta"), (30, "Moderada"), (1, "Baixa"), (0, "Sem indícios")]
NIVEIS_ORDEM = ["Sem indícios", "Baixa", "Moderada", "Alta"]


def nivel(pontos):
    """Prioridade de verificação a partir dos pontos (0–100)."""
    return next(nome for minimo, nome in NIVEIS if pontos >= minimo)


def _quando(t):
    return datetime.fromisoformat(f"{t['data']}T{t['hora']}")


def _percentil(valores, p):
    """Percentil pelo método do posto mais próximo (sem interpolação: fácil de conferir à mão)."""
    if not valores:
        return 0
    ordenados = sorted(valores)
    posto = max(1, -(-p * len(ordenados) // 100))  # teto(p/100 · n)
    return ordenados[int(posto) - 1]


def _num(valor, casas=3):
    """Número no formato brasileiro (vírgula decimal), como no resto da interface."""
    return f"{valor:.{casas}f}".replace(".", ",")


def _brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def regras_formatadas(p=PARAMETROS):
    valores = {**p, "repasse_pct": round(p["repasse_fracao"] * 100),
               "intermediacao_top": 100 - p["intermediacao_percentil"],
               "fan_proporcao": f"{p['fan_proporcao']:g}".replace(".", ","),
               "volume_z": f"{p['volume_z']:g}".replace(".", ",")}
    return [{**r, "limite": r["limite"].format(**valores)} for r in REGRAS]


# ---------------------------------------------------------------- regras

def _volume(contas, p):
    fluxos = [c["flow"] for c in contas]
    mediana = statistics.median(fluxos)
    mad = statistics.median([abs(f - mediana) for f in fluxos]) * 1.4826  # comparável ao desvio padrão
    if mad == 0:
        return {}
    achados = {}
    for c in contas:
        z = (c["flow"] - mediana) / mad
        if z >= p["volume_z"]:
            achados[c["id"]] = {"evidencia": f"Fluxo de {_brl(c['flow'])}, contra mediana de {_brl(mediana)} "
                                             f"(desvio robusto {_num(z, 1)}).",
                                "valores": {"fluxo": c["flow"], "mediana": round(mediana, 2), "z_robusto": round(z, 2)}}
    return achados


def _repasse(transacoes, p):
    entradas, saidas = defaultdict(list), defaultdict(list)
    for t in transacoes:
        entradas[t["para"]].append(t)
        saidas[t["de"]].append(t)
    janela = timedelta(hours=p["repasse_horas"])
    achados = {}
    for conta, recebidas in entradas.items():
        for e in sorted(recebidas, key=_quando):
            inicio = _quando(e)
            reenvios = [s for s in saidas[conta] if inicio <= _quando(s) <= inicio + janela]
            total = sum(s["valor"] for s in reenvios)
            if reenvios and total >= p["repasse_fracao"] * e["valor"]:
                achados[conta] = {
                    "evidencia": f"Recebeu {_brl(e['valor'])} ({e['id']}, {e['data']} {e['hora']}) e reenviou "
                                 f"{_brl(total)} ({total / e['valor']:.0%}) em até {p['repasse_horas']} h.",
                    "transacoes": [e["id"]] + [s["id"] for s in reenvios],
                    "valores": {"recebido": e["valor"], "reenviado": round(total, 2)}}
                break
    return achados


def _cadeias(transacoes, p):
    """Sequências cronológicas: cada transferência sai da conta que acabou de receber."""
    saidas = defaultdict(list)
    for t in sorted(transacoes, key=_quando):
        saidas[t["de"]].append(t)
    janela = timedelta(days=p["cadeia_janela_dias"])
    minimo, maximo = p["cadeia_min_transferencias"], p["cadeia_min_transferencias"] + 2
    encontradas = []

    def estender(caminho):
        if len(caminho) >= minimo:
            encontradas.append(list(caminho))
        if len(caminho) == maximo or len(encontradas) > 200:
            return
        ultima = caminho[-1]
        visitadas = {caminho[0]["de"]} | {t["para"] for t in caminho}
        for t in saidas[ultima["para"]]:
            if _quando(ultima) < _quando(t) <= _quando(ultima) + janela and t["para"] not in visitadas:
                estender(caminho + [t])

    for t in sorted(transacoes, key=_quando):
        estender([t])
    # a cadeia mais longa de cada conta
    achados = {}
    for cadeia in sorted(encontradas, key=len, reverse=True):
        contas = [cadeia[0]["de"]] + [t["para"] for t in cadeia]
        for conta in contas:
            achados.setdefault(conta, {
                "evidencia": f"Cadeia de {len(cadeia)} transferências: {' → '.join(contas)} "
                             f"({cadeia[0]['data']} a {cadeia[-1]['data']}).",
                "transacoes": [t["id"] for t in cadeia], "contas": contas})
    return achados


def _circuitos(transacoes, p):
    datas = defaultdict(set)
    for t in transacoes:
        datas[(t["de"], t["para"])].add(t["data"])
    recorrente = nx.DiGraph([par for par, d in datas.items() if len(d) >= p["ciclo_min_repeticoes"]])
    circuitos = [c for c in nx.simple_cycles(recorrente, length_bound=p["ciclo_max_contas"]) if len(c) >= 3]
    achados = {}
    for ciclo in sorted(circuitos, key=len, reverse=True):  # o maior circuito de cada conta
        inicio = min(ciclo)
        i = ciclo.index(inicio)
        ordem = ciclo[i:] + ciclo[:i] + [inicio]
        for conta in ciclo:
            achados.setdefault(conta, {
                "evidencia": f"Circuito {' → '.join(ordem)}: cada ligação aparece em "
                             f"{p['ciclo_min_repeticoes']} ou mais datas.",
                "contas": ordem,
                "transacoes": [t["id"] for t in transacoes
                               if any(t["de"] == a and t["para"] == b for a, b in zip(ordem, ordem[1:]))]})
    return achados, [list(c) for c in circuitos]


def _fans(transacoes, p):
    origens, destinos = defaultdict(set), defaultdict(set)
    for t in transacoes:
        origens[t["para"]].add(t["de"])
        destinos[t["de"]].add(t["para"])
    fan_in, fan_out = {}, {}
    for conta in set(origens) | set(destinos):
        n_in, n_out = len(origens[conta]), len(destinos[conta])
        if n_in >= p["fan_min_contas"] and n_in >= p["fan_proporcao"] * n_out:
            fan_in[conta] = {"evidencia": f"Recebe de {n_in} contas distintas e envia para {n_out}: "
                                          f"{', '.join(sorted(origens[conta]))}.",
                             "contas": sorted(origens[conta]), "valores": {"origens": n_in, "destinos": n_out}}
        if n_out >= p["fan_min_contas"] and n_out >= p["fan_proporcao"] * n_in:
            fan_out[conta] = {"evidencia": f"Envia para {n_out} contas distintas e recebe de {n_in}: "
                                           f"{', '.join(sorted(destinos[conta]))}.",
                              "contas": sorted(destinos[conta]), "valores": {"origens": n_in, "destinos": n_out}}
    return fan_in, fan_out


def _intermediacao(contas, p):
    valores = [c["betw"] for c in contas]
    corte = _percentil(valores, p["intermediacao_percentil"])
    return {c["id"]: {"evidencia": f"Betweenness {_num(c['betw'])} (corte das {100 - p['intermediacao_percentil']}% "
                                   f"maiores: {_num(corte)}).",
                      "valores": {"betweenness": round(c["betw"], 6), "corte": round(corte, 6)}}
            for c in contas if c["betw"] > 0 and c["betw"] >= corte}


def _pontes(transacoes, comunidade):
    outras = defaultdict(set)
    for t in transacoes:
        a, b = comunidade[t["de"]], comunidade[t["para"]]
        if a != b:
            outras[t["de"]].add(b)
            outras[t["para"]].add(a)
    return {conta: {"evidencia": f"Transaciona com a(s) comunidade(s) {', '.join(map(str, sorted(cs)))}, "
                                 f"além da própria ({comunidade[conta]}).",
                    "valores": {"comunidades": sorted(cs)}}
            for conta, cs in outras.items()}


def _concentracao(transacoes, p):
    por_conta = defaultdict(list)
    for t in transacoes:
        por_conta[t["de"]].append(t)
        por_conta[t["para"]].append(t)
    janela = timedelta(hours=p["concentracao_horas"])
    achados = {}
    for conta, lista in por_conta.items():
        lista.sort(key=_quando)
        melhor = []
        for i, a in enumerate(lista):
            grupo = [t for t in lista[i:] if _quando(t) - _quando(a) <= janela]
            if len(grupo) > len(melhor):
                melhor = grupo
        if len(melhor) >= p["concentracao_min"]:
            achados[conta] = {"evidencia": f"{len(melhor)} transações entre {melhor[0]['data']} {melhor[0]['hora']} "
                                           f"e {melhor[-1]['data']} {melhor[-1]['hora']}.",
                              "transacoes": [t["id"] for t in melhor]}
    return achados


def _valores(transacoes, p):
    corte = _percentil([t["valor"] for t in transacoes], p["valor_percentil"])
    atipicas = [t for t in transacoes if t["valor"] > corte] if len(transacoes) >= 20 else []
    achados = {}
    for t in sorted(atipicas, key=lambda x: -x["valor"]):
        for conta, papel in ((t["de"], "enviou"), (t["para"], "recebeu")):
            achado = achados.setdefault(conta, {"transacoes": [], "maior": t})
            achado["transacoes"].append(t["id"])
    for conta, a in achados.items():
        t = a.pop("maior")
        a["evidencia"] = (f"{len(a['transacoes'])} transação(ões) acima de {_brl(corte)} (percentil "
                          f"{p['valor_percentil']}); a maior: {_brl(t['valor'])} ({t['id']}, {t['de']} → {t['para']}).")
        a["valores"] = {"corte": corte, "maior": t["valor"]}
    return achados, [t["id"] for t in atipicas]


# ---------------------------------------------------------------- avaliação

def avaliar(contas, transacoes, p=PARAMETROS):
    """Aplica as regras. `contas` = ranking do motor (id, flow, betw, com); `transacoes` com
    id, de, para, valor, data e hora. Retorna o bloco "risco" do resultado da análise."""
    comunidade = {c["id"]: c["com"] for c in contas}
    fan_in, fan_out = _fans(transacoes, p)
    circuitos, lista_circuitos = _circuitos(transacoes, p)
    valores, atipicas = _valores(transacoes, p)
    achados = {
        "volume": _volume(contas, p), "repasse": _repasse(transacoes, p), "cadeia": _cadeias(transacoes, p),
        "ciclo": circuitos, "fan_in": fan_in, "fan_out": fan_out, "intermediacao": _intermediacao(contas, p),
        "ponte": _pontes(transacoes, comunidade), "concentracao": _concentracao(transacoes, p), "valor": valores,
    }
    por_conta = {}
    for c in contas:
        indicios = [{"regra": rid, "nome": REGRA[rid]["nome"], "peso": REGRA[rid]["peso"], **achados[rid][c["id"]]}
                    for rid in REGRA if c["id"] in achados[rid]]
        pontos = min(100, sum(i["peso"] for i in indicios))
        por_conta[c["id"]] = {"pontos": pontos, "nivel": nivel(pontos), "indicios": indicios}

    # comunidades com indícios concentrados
    comunidades = []
    for numero in sorted(set(comunidade.values())):
        membros = [cid for cid, com in comunidade.items() if com == numero]
        sinalizadas = [cid for cid in membros if por_conta[cid]["nivel"] in ("Moderada", "Alta")]
        internas = [t for t in transacoes if comunidade[t["de"]] == numero and comunidade[t["para"]] == numero]
        possiveis = len(membros) * (len(membros) - 1)
        densidade = len({(t["de"], t["para"]) for t in internas}) / possiveis if possiveis else 0
        destaque = len(sinalizadas) >= p["comunidade_min_contas"]
        comunidades.append({
            "comunidade": numero, "contas": sorted(membros), "sinalizadas": sorted(sinalizadas),
            "pontos_medio": round(sum(por_conta[cid]["pontos"] for cid in membros) / len(membros), 1),
            "volume_interno": round(sum(t["valor"] for t in internas), 2), "densidade": round(densidade, 3),
            "destaque": destaque,
            "motivo": (f"{len(sinalizadas)} contas com prioridade moderada ou alta" if destaque else ""),
        })

    return {
        "aviso": "Indícios para priorizar a verificação humana. Não são prova de irregularidade.",
        "parametros": dict(p),
        "regras": [{**r, "contas": sorted(achados[r["id"]])} for r in regras_formatadas(p)],
        "contas": por_conta,
        "comunidades": comunidades,
        "circuitos": lista_circuitos,
        "transacoes_atipicas": atipicas,
        "resumo": {"por_nivel": {n: sum(1 for v in por_conta.values() if v["nivel"] == n) for n in NIVEIS_ORDEM},
                   "por_regra": {rid: len(achados[rid]) for rid in REGRA},
                   "comunidades_destaque": sum(c["destaque"] for c in comunidades)},
    }
