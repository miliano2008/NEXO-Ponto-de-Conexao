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
        vencida = time.monotonic() - _base["lida_em"] > RECARGA_SEGUNDOS
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


def calcular(dias=0, simuladas=()):
    """Resultado da análise para o período e as transações simuladas do usuário.

    Retorna (resultado, info). O resultado é compartilhado pelo cache: quem chama
    não deve alterá-lo (servidor.py monta a resposta em cópias rasas).
    """
    contas, base, base_assinatura = obter_base()
    simuladas = list(simuladas)
    chave = repositorio.assinatura(base_assinatura, simuladas, dias, analise.VERSAO_MOTOR)
    with _trava:
        if chave in _cache:
            _cache.move_to_end(chave)
            resultado, info = _cache[chave]
            return resultado, {**info, "origem": "memória"}

    linhas = [repositorio.linha_csv(t) for t in base] + simuladas
    contas, transacoes = analise.validar_dados(contas, linhas)   # ValueError se a simulação for inválida
    referencia = max(date.fromisoformat(t["data"]) for t in transacoes)
    if dias:
        inicio = referencia - timedelta(days=dias - 1)
        transacoes = [t for t in transacoes if date.fromisoformat(t["data"]) >= inicio]
    inicio_calculo = time.perf_counter()
    resultado = analise.calcular(contas, transacoes)
    duracao_ms = round((time.perf_counter() - inicio_calculo) * 1000)

    analise_id = None
    if not simuladas:  # só a base é guardada no banco; simulações ficam no rascunho do usuário
        try:
            analise_id = repositorio.guardar_analise(chave, base_assinatura, dias, resultado, duracao_ms)
        except db.ErroBanco:
            analise_id = None  # não impede a análise de ser exibida
    info = {"id": analise_id, "assinatura": chave[:12], "versao_motor": analise.VERSAO_MOTOR,
            "duracao_ms": duracao_ms, "data_referencia": referencia.isoformat(),
            "total_base_original": len(base), "tipos_transacao": sorted({t["tipo"] for t in base})}
    with _trava:
        _cache[chave] = (resultado, info)
        while len(_cache) > MAX_EM_MEMORIA:
            _cache.popitem(last=False)
    return resultado, {**info, "origem": "cálculo"}


def limpar_cache():
    with _trava:
        _cache.clear()
        _base.update(contas=None, transacoes=None, assinatura=None, lida_em=0.0)
