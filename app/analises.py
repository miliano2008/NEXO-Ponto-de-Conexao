"""NEXO — serviço de análise: base atual, cache de resultados e rastreabilidade.

- A base (contas + transações) é relida do banco no máximo a cada RECARGA_SEGUNDOS:
  mudanças feitas no MySQL aparecem sem reiniciar o sistema.
- Cada resultado é identificado por uma assinatura (hash de base + simulação +
  período + versão do motor). Mesma assinatura → mesmo resultado, sem recalcular.
- Análises da base (sem simulação) são guardadas na tabela `analises` e recebem
  um número de identificação, usado depois em relatórios e no histórico.
"""

import threading
import time
from collections import OrderedDict
from datetime import date, timedelta

from banco import conexao as db
from banco import repositorio
from nucleo import analise

RECARGA_SEGUNDOS = 60
MAX_EM_MEMORIA = 32

_trava = threading.Lock()
_base = {"contas": None, "transacoes": None, "assinatura": None, "lida_em": 0.0}
_cache = OrderedDict()  # assinatura → (resultado, info)


def obter_base(forcar=False):
    """(contas, transacoes, assinatura) da base atual."""
    with _trava:
        # ">=": no Windows o relógio anda em passos de ~16 ms, e com RECARGA_SEGUNDOS = 0 a diferença pode dar 0
        vencida = time.monotonic() - _base["lida_em"] >= RECARGA_SEGUNDOS
        if forcar or _base["contas"] is None or vencida:
            try:
                contas, transacoes = repositorio.carregar_dados()
            except (db.ErroBanco, ValueError):
                if _base["contas"] is None:
                    raise
                # banco fora do ar por um momento: segue com a última base lida
                _base["lida_em"] = time.monotonic()
            else:
                _base.update(contas=contas, transacoes=transacoes, lida_em=time.monotonic(),
                             assinatura=repositorio.assinatura(contas, [repositorio.linha_csv(t) for t in transacoes]))
        return _base["contas"], _base["transacoes"], _base["assinatura"]


def normalizar_recorte(recorte=None):
    """Recorte da análise: quais transações formam a rede.

    Aceita um número (últimos N dias, como antes) ou um dicionário com:
      dias, inicio, fim (AAAA-MM-DD), tipos (lista), valor_min, valor_max.
    Devolve sempre o mesmo formato, que entra na assinatura do cache.
    """
    if recorte is None or isinstance(recorte, int):
        recorte = {"dias": recorte or 0}
    r = {"dias": int(recorte.get("dias") or 0), "inicio": recorte.get("inicio") or None,
         "fim": recorte.get("fim") or None, "tipos": sorted(set(recorte.get("tipos") or [])),
         "valor_min": recorte.get("valor_min"), "valor_max": recorte.get("valor_max")}
    for chave in ("inicio", "fim"):
        if r[chave]:
            try:
                r[chave] = date.fromisoformat(str(r[chave])).isoformat()
            except ValueError as erro:
                raise ValueError(f"Data inválida: {r[chave]}. Use o formato AAAA-MM-DD.") from erro
    if r["inicio"] and r["fim"] and r["inicio"] > r["fim"]:
        raise ValueError("A data inicial é depois da data final.")
    for chave in ("valor_min", "valor_max"):
        if r[chave] in ("", None):
            r[chave] = None
        else:
            try:
                r[chave] = round(float(r[chave]), 2)
            except (TypeError, ValueError) as erro:
                raise ValueError("Valor mínimo/máximo inválido.") from erro
            if r[chave] < 0:
                raise ValueError("Os valores do filtro não podem ser negativos.")
    if r["valor_min"] is not None and r["valor_max"] is not None and r["valor_min"] > r["valor_max"]:
        raise ValueError("O valor mínimo é maior que o valor máximo.")
    if r["dias"] < 0:
        raise ValueError("Período inválido.")
    return r


def aplicar_recorte(transacoes, r):
    """Filtra as transações validadas pelo recorte. Retorna (transações, referência, início, fim)."""
    referencia = max(date.fromisoformat(t["data"]) for t in transacoes)
    inicio = date.fromisoformat(r["inicio"]) if r["inicio"] else None
    fim = date.fromisoformat(r["fim"]) if r["fim"] else None
    if r["dias"] and not (inicio or fim):
        inicio = referencia - timedelta(days=r["dias"] - 1)
    filtradas = [t for t in transacoes
                 if (inicio is None or date.fromisoformat(t["data"]) >= inicio)
                 and (fim is None or date.fromisoformat(t["data"]) <= fim)
                 and (not r["tipos"] or t["tipo"] in r["tipos"])
                 and (r["valor_min"] is None or t["valor"] >= r["valor_min"])
                 and (r["valor_max"] is None or t["valor"] <= r["valor_max"])]
    return filtradas, referencia, inicio, fim


def calcular(recorte=0, simuladas=()):
    """Resultado da análise para o recorte e as transações simuladas do usuário.

    `recorte`: últimos N dias (número) ou dicionário (ver normalizar_recorte).
    Retorna (resultado, info). O resultado é compartilhado pelo cache: quem chama
    não deve alterá-lo (servidor.py monta a resposta em cópias rasas).
    Lança ValueError se a simulação for inválida ou se o recorte não tiver transações.
    """
    r = normalizar_recorte(recorte)
    contas, base, base_assinatura = obter_base()
    simuladas = list(simuladas)
    chave = repositorio.assinatura(base_assinatura, simuladas, r, analise.VERSAO_MOTOR)
    with _trava:
        if chave in _cache:
            _cache.move_to_end(chave)
            resultado, info = _cache[chave]
            return resultado, {**info, "origem": "memória"}

    linhas = [repositorio.linha_csv(t) for t in base] + simuladas
    contas, transacoes = analise.validar_dados(contas, linhas)   # ValueError se a simulação for inválida
    datas = sorted(t["data"] for t in transacoes)
    transacoes, referencia, inicio, fim = aplicar_recorte(transacoes, r)
    if not transacoes:
        raise ValueError("Nenhuma transação no recorte escolhido. Amplie o período ou os filtros de valor e tipo.")
    inicio_calculo = time.perf_counter()
    resultado = analise.calcular(contas, transacoes)
    duracao_ms = round((time.perf_counter() - inicio_calculo) * 1000)

    analise_id = None
    if not simuladas:  # só a base é guardada no banco; simulações ficam no rascunho do usuário
        try:
            analise_id = repositorio.guardar_analise(chave, base_assinatura, r["dias"], resultado, duracao_ms)
        except db.ErroBanco:
            analise_id = None  # não impede a análise de ser exibida
    info = {"id": analise_id, "assinatura": chave[:12], "versao_motor": analise.VERSAO_MOTOR,
            "duracao_ms": duracao_ms, "data_referencia": referencia.isoformat(),
            "total_base_original": len(base), "tipos_transacao": sorted({t["tipo"] for t in base}),
            "recorte": {**r, "inicio_efetivo": (inicio.isoformat() if inicio else datas[0]),
                        "fim_efetivo": (fim.isoformat() if fim else datas[-1]),
                        "transacoes": len(transacoes)},
            "datas_base": {"primeira": datas[0], "ultima": datas[-1]}}
    with _trava:
        _cache[chave] = (resultado, info)
        while len(_cache) > MAX_EM_MEMORIA:
            _cache.popitem(last=False)
    return resultado, {**info, "origem": "cálculo"}


def limpar_cache():
    with _trava:
        _cache.clear()
        _base.update(contas=None, transacoes=None, assinatura=None, lida_em=0.0)
