"""NEXO — dados bancários fictícios e regras por modalidade (Fase 4).

Dados bancários (4.5): instituição FICTÍCIA, tipo de conta e tipo de chave PIX, gerados por
regras fixas (sempre os mesmos). Nenhum nome ou código de banco real, nenhum número de chave.
Contas ligadas por "Transferência" ficam na mesma instituição, porque transferência entre
contas pressupõe o mesmo banco: assim a base continua coerente com a regra.

Regras por modalidade: cada regra diz de onde vem —
  "Regulamentação"                    norma do Banco Central (confirmem a fonte antes de citar)
  "Prática de mercado (configurável)" varia de banco para banco
  "Parâmetro do administrador"        decisão interna
— e tem uma ação: "bloquear", "alertar" ou "desligada". Valem para as transações SIMULADAS;
na base (histórica e fictícia) servem só como conferência informativa.
"""

import copy
import hashlib
from collections import Counter
from datetime import date, time

INSTITUICOES = ["Banco Fictício A", "Banco Fictício B", "Banco Fictício C", "Banco Fictício D"]
TIPO_CONTA = {"Pessoa Física": "Conta corrente", "Pessoa Jurídica": "Conta empresarial",
              "Conta Digital": "Conta de pagamento"}
CHAVES_PIX = {"Pessoa Física": ["CPF", "E-mail", "Telefone", "Aleatória"],
              "Pessoa Jurídica": ["CNPJ", "E-mail", "Aleatória"],
              "Conta Digital": ["Aleatória", "E-mail", "Telefone"]}

ORIGENS = ["Regulamentação", "Prática de mercado (configurável)", "Parâmetro do administrador"]
ACOES = ["bloquear", "alertar", "desligada"]

REGRAS_PADRAO = {
    "pix_24h": {
        "nome": "PIX disponível 24 horas, todos os dias", "modalidade": "PIX", "origem": "Regulamentação",
        "acao": "alertar", "parametros": {},
        "descricao": "O PIX funciona a qualquer hora, inclusive em fins de semana e feriados. Regra informativa: "
                     "nunca bloqueia.",
        "fonte": "Banco Central do Brasil — regulamento do PIX (confirmar a versão vigente)"},
    "pix_noturno_pf": {
        "nome": "Limite noturno do PIX para pessoa física", "modalidade": "PIX", "origem": "Regulamentação",
        "acao": "alertar", "parametros": {"limite": 1000.0, "inicio": "20:00", "fim": "06:00"},
        "descricao": "Transferência de pessoa física no período noturno acima do limite padrão. O cliente pode "
                     "ajustar o limite com o banco, por isso a ação padrão é alertar.",
        "fonte": "Banco Central do Brasil — limites de PIX no período noturno (2021; confirmar a norma vigente)"},
    "ted_dia_util": {
        "nome": "TED só em dias úteis", "modalidade": "TED", "origem": "Prática de mercado (configurável)",
        "acao": "bloquear", "parametros": {},
        "descricao": "A TED é processada em dias úteis. Sábados e domingos são recusados; feriados não são "
                     "considerados nesta versão.",
        "fonte": "Funcionamento do sistema de pagamentos; cada banco define seus prazos"},
    "ted_horario": {
        "nome": "Horário de envio da TED", "modalidade": "TED", "origem": "Prática de mercado (configurável)",
        "acao": "bloquear", "parametros": {"inicio": "06:30", "fim": "17:00"},
        "descricao": "Janela de envio da TED. O horário limite é definido por cada banco.",
        "fonte": "Definido por cada instituição"},
    "transferencia_mesma_instituicao": {
        "nome": "Transferência entre contas da mesma instituição", "modalidade": "Transferência",
        "origem": "Parâmetro do administrador", "acao": "bloquear", "parametros": {},
        "descricao": "\"Transferência\" é a operação entre contas do mesmo banco. Entre bancos diferentes, use PIX "
                     "ou TED.",
        "fonte": "Regra interna da instituição"},
}


def _semente(texto):
    return int(hashlib.sha256(texto.encode()).hexdigest(), 16)


def dados_bancarios(contas, transacoes):
    """{conta: {instituicao, tipo_conta, chave_pix}} — determinístico e coerente com a base.

    contas: [{id_conta, tipo_titular}]; transacoes validadas: [{de, para, tipo}].
    """
    pai = {c["id_conta"]: c["id_conta"] for c in contas}

    def raiz(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x
    for t in transacoes:
        if t["tipo"] == "Transferência" and t["de"] in pai and t["para"] in pai:
            a, b = sorted((raiz(t["de"]), raiz(t["para"])))
            pai[b] = a
    grupos = {}
    for c in sorted(pai):
        grupos.setdefault(raiz(c), []).append(c)
    # grupos maiores primeiro, cada um para a instituição com menos contas (equilibra os bancos)
    carga = Counter({i: 0 for i in INSTITUICOES})
    instituicao = {}
    for membros in sorted(grupos.values(), key=lambda g: (-len(g), g[0])):
        alvo = min(INSTITUICOES, key=lambda i: (carga[i], i))
        carga[alvo] += len(membros)
        for c in membros:
            instituicao[c] = alvo
    resultado = {}
    for c in contas:
        tipo = c.get("tipo_titular", "Pessoa Física")
        chaves = CHAVES_PIX.get(tipo, CHAVES_PIX["Pessoa Física"])
        resultado[c["id_conta"]] = {"instituicao": instituicao[c["id_conta"]],
                                    "tipo_conta": TIPO_CONTA.get(tipo, "Conta corrente"),
                                    "chave_pix": chaves[_semente(c["id_conta"]) % len(chaves)]}
    return resultado


# ---------------------------------------------------------------- regras

def regras_com_ajustes(ajustes=None):
    """Regras padrão + o que o administrador alterou ({id: {acao, parametros}})."""
    regras = copy.deepcopy(REGRAS_PADRAO)
    for rid, ajuste in (ajustes or {}).items():
        if rid in regras:
            if ajuste.get("acao") in ACOES:
                regras[rid]["acao"] = ajuste["acao"]
            regras[rid]["parametros"].update({k: v for k, v in (ajuste.get("parametros") or {}).items()
                                              if k in regras[rid]["parametros"]})
    return regras


def validar_parametros(rid, parametros):
    """Confere os parâmetros que o administrador quer gravar. Lança ValueError com a mensagem."""
    if rid not in REGRAS_PADRAO:
        raise ValueError("Regra inexistente.")
    limpos = {}
    for chave, padrao in REGRAS_PADRAO[rid]["parametros"].items():
        if chave not in parametros:
            continue
        valor = parametros[chave]
        if isinstance(padrao, float):
            try:
                valor = round(float(valor), 2)
            except (TypeError, ValueError) as erro:
                raise ValueError(f"Valor inválido para {chave}.") from erro
            if valor <= 0:
                raise ValueError("O limite precisa ser maior que zero.")
        else:
            try:
                valor = time.fromisoformat(str(valor)).strftime("%H:%M")
            except ValueError as erro:
                raise ValueError(f"Horário inválido para {chave}: use HH:MM.") from erro
        limpos[chave] = valor
    return limpos


def _no_intervalo(hora, inicio, fim):
    """Intervalo de horário que pode atravessar a meia-noite (ex.: 20:00 a 06:00)."""
    return (inicio <= hora < fim) if inicio <= fim else (hora >= inicio or hora < fim)


def _brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def avaliar_transacao(t, titular_origem, bancos, regras):
    """Confere uma transação (de, para, valor, data, hora, tipo) com as regras da modalidade dela.

    Retorna a lista de verificações: {regra, nome, origem, acao, resultado, mensagem}, em que
    resultado é "ok", "alerta" ou "bloqueio". Regras desligadas e de outras modalidades não aparecem.
    """
    hora = str(t["hora"])[:5]
    dia = date.fromisoformat(str(t["data"]))
    valor = float(t["valor"])
    tipo = t["tipo"]
    mesma = bancos.get(t["de"], {}).get("instituicao") == bancos.get(t["para"], {}).get("instituicao")
    saida = []
    for rid, r in regras.items():
        if r["modalidade"] != tipo or r["acao"] == "desligada":
            continue
        p, violou, msg = r["parametros"], False, ""
        if rid == "pix_24h":
            msg = "PIX aceito em qualquer dia e horário."
        elif rid == "pix_noturno_pf":
            if titular_origem == "Pessoa Física" and _no_intervalo(hora, p["inicio"], p["fim"]) and valor > p["limite"]:
                violou, msg = True, (f"{_brl(valor)} às {hora}: acima do limite noturno de {_brl(p['limite'])} "
                                     f"para pessoa física ({p['inicio']} às {p['fim']}).")
            else:
                msg = "Dentro do limite noturno (ou fora do período noturno, ou não é pessoa física)."
        elif rid == "ted_dia_util":
            if dia.weekday() >= 5:
                violou, msg = True, f"{dia.strftime('%d/%m/%Y')} é {'sábado' if dia.weekday() == 5 else 'domingo'}: TED só em dias úteis."
            else:
                msg = "Dia útil."
        elif rid == "ted_horario":
            if not (p["inicio"] <= hora <= p["fim"]):
                violou, msg = True, f"{hora} está fora da janela da TED ({p['inicio']} às {p['fim']})."
            else:
                msg = f"Dentro da janela da TED ({p['inicio']} às {p['fim']})."
        elif rid == "transferencia_mesma_instituicao":
            a, b = bancos.get(t["de"], {}).get("instituicao"), bancos.get(t["para"], {}).get("instituicao")
            if not mesma:
                violou, msg = True, f"{t['de']} é do {a} e {t['para']} é do {b}: use PIX ou TED entre instituições."
            else:
                msg = f"As duas contas são do {a}."
        resultado = ("bloqueio" if r["acao"] == "bloquear" else "alerta") if violou else "ok"
        saida.append({"regra": rid, "nome": r["nome"], "origem": r["origem"], "acao": r["acao"],
                      "resultado": resultado, "mensagem": msg})
    return saida


def conferir_base(transacoes, titulares, bancos, regras):
    """Quantas transações da base ficariam fora de cada regra (informativo: a base é fictícia)."""
    contagem = Counter()
    for t in transacoes:
        for v in avaliar_transacao(t, titulares.get(t["de"]), bancos, regras):
            if v["resultado"] != "ok":
                contagem[v["regra"]] += 1
    return dict(contagem)
