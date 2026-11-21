"""NEXO — acesso aos dados: base de transações, simulações por usuário e análises guardadas.

Toda leitura/escrita de dados de negócio passa por aqui; as rotas (app/servidor.py)
não montam SQL. Funciona no MySQL (Aiven) e no modo local (CSV + SQLite).
"""

import csv
import hashlib
import json
import zlib
from datetime import date, datetime, timedelta
from decimal import Decimal

from banco import conexao as db
from nucleo import analise
from nucleo.configuracao import PASTA_DADOS

LIMITE_SIMULADAS = 200  # por usuário: mantém o cálculo rápido (base + simuladas ≤ ~360 transações)


def agora():
    return datetime.now().replace(microsecond=0)


# ---------------------------------------------------------------- base de transações

def ler_csv(nome):
    with (PASTA_DADOS / nome).open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def carregar_csv():
    return analise.validar_dados(ler_csv("contas.csv"), ler_csv("transacoes.csv"))


def _hora(valor):
    """PyMySQL devolve TIME como timedelta; o SQLite/CSV, como texto."""
    if isinstance(valor, timedelta):
        minutos = int(valor.total_seconds()) // 60
        return f"{minutos // 60:02d}:{minutos % 60:02d}"
    return str(valor)[:5]


def _texto(valor):
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()[:10]
    if isinstance(valor, Decimal):
        return f"{valor:.2f}"
    return str(valor)


def carregar_mysql():
    """Lê as tabelas contas/transacoes do MySQL no mesmo formato dos CSVs."""
    with db.conectar() as c:
        contas = c.execute("SELECT id_conta, tipo_titular, data_abertura FROM contas ORDER BY id_conta").fetchall()
        linhas = c.execute("SELECT id_transacao, conta_origem, conta_destino, valor, data, hora, tipo_transacao "
                           "FROM transacoes ORDER BY id_transacao").fetchall()
    if not contas:
        raise ValueError("As tabelas do MySQL estão vazias. Rode: scripts\\MIGRAR_MYSQL.bat")
    contas = [{**c, "data_abertura": _texto(c["data_abertura"])} for c in contas]
    linhas = [{**t, "valor": _texto(t["valor"]), "data": _texto(t["data"]), "hora": _hora(t["hora"])} for t in linhas]
    return analise.validar_dados(contas, linhas)


def carregar_dados():
    """Base validada: MySQL se configurado, senão os CSVs de banco/dados/."""
    return carregar_mysql() if db.usando_mysql() else carregar_csv()


def linha_csv(t):
    """Transação validada → formato de linha do CSV (o que validar_dados recebe)."""
    return {"id_transacao": t["id"], "conta_origem": t["de"], "conta_destino": t["para"],
            "valor": f"{t['centavos'] / 100:.2f}", "data": t["data"], "hora": t["hora"],
            "tipo_transacao": t["tipo"]}


def assinatura(*partes):
    """Hash estável (SHA-256) de qualquer conjunto de dados serializável em JSON."""
    texto = json.dumps(partes, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- simulações por usuário

def _rascunho(c, usuario_id, criar):
    linha = c.execute("SELECT id FROM simulacoes WHERE usuario_id = ? AND situacao = 'rascunho' "
                      "ORDER BY id LIMIT 1", (usuario_id,)).fetchone()
    if linha or not criar:
        return linha["id"] if linha else None
    cursor = c.execute("INSERT INTO simulacoes (usuario_id, situacao, criado_em, atualizado_em) "
                       "VALUES (?, 'rascunho', ?, ?)", (usuario_id, agora().isoformat(), agora().isoformat()))
    return cursor.lastrowid


def listar_simuladas(usuario_id):
    """Transações da simulação em andamento do usuário, no formato de linha do CSV."""
    with db.conectar() as c:
        sid = _rascunho(c, usuario_id, criar=False)
        if sid is None:
            return []
        linhas = c.execute("SELECT id_transacao, conta_origem, conta_destino, valor, data, hora, tipo_transacao "
                           "FROM simulacao_transacoes WHERE simulacao_id = ? ORDER BY id", (sid,)).fetchall()
    return [{"id_transacao": l["id_transacao"], "conta_origem": l["conta_origem"],
             "conta_destino": l["conta_destino"], "valor": _texto(l["valor"]), "data": _texto(l["data"]),
             "hora": _hora(l["hora"]), "tipo_transacao": l["tipo_transacao"]} for l in linhas]


def proximo_id_simulado(simuladas):
    usados = {s["id_transacao"] for s in simuladas}
    n = len(simuladas) + 1
    while f"S{n:04d}" in usados:
        n += 1
    return f"S{n:04d}"


def adicionar_simulada(usuario_id, linha):
    """Grava uma transação já validada na simulação do usuário."""
    with db.conectar() as c:
        sid = _rascunho(c, usuario_id, criar=True)
        total = c.execute("SELECT COUNT(*) AS n FROM simulacao_transacoes WHERE simulacao_id = ?",
                          (sid,)).fetchone()["n"]
        if total >= LIMITE_SIMULADAS:
            raise ValueError(f"Limite de {LIMITE_SIMULADAS} transações simuladas atingido. "
                             "Use 'Restaurar base original' para começar de novo.")
        c.execute("INSERT INTO simulacao_transacoes (simulacao_id, id_transacao, conta_origem, conta_destino, "
                  "valor, data, hora, tipo_transacao, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (sid, linha["id_transacao"], linha["conta_origem"], linha["conta_destino"], linha["valor"],
                   linha["data"], linha["hora"], linha["tipo_transacao"], agora().isoformat()))
        c.execute("UPDATE simulacoes SET atualizado_em = ? WHERE id = ?", (agora().isoformat(), sid))


def adicionar_simuladas(usuario_id, linhas):
    """Grava várias transações já validadas de uma vez (simulação recorrente): tudo ou nada."""
    with db.conectar() as c:
        sid = _rascunho(c, usuario_id, criar=True)
        total = c.execute("SELECT COUNT(*) AS n FROM simulacao_transacoes WHERE simulacao_id = ?",
                          (sid,)).fetchone()["n"]
        if total + len(linhas) > LIMITE_SIMULADAS:
            raise ValueError(f"Limite de {LIMITE_SIMULADAS} transações simuladas: já há {total} e a simulação "
                             f"criaria mais {len(linhas)}. Reduza as repetições ou restaure a base.")
        for linha in linhas:
            c.execute("INSERT INTO simulacao_transacoes (simulacao_id, id_transacao, conta_origem, conta_destino, "
                      "valor, data, hora, tipo_transacao, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (sid, linha["id_transacao"], linha["conta_origem"], linha["conta_destino"], linha["valor"],
                       linha["data"], linha["hora"], linha["tipo_transacao"], agora().isoformat()))
        c.execute("UPDATE simulacoes SET atualizado_em = ? WHERE id = ?", (agora().isoformat(), sid))


def remover_simulada(usuario_id, id_transacao):
    with db.conectar() as c:
        sid = _rascunho(c, usuario_id, criar=False)
        if sid is None:
            return False
        return c.execute("DELETE FROM simulacao_transacoes WHERE simulacao_id = ? AND id_transacao = ?",
                         (sid, id_transacao)).rowcount == 1


def limpar_simulacao(usuario_id):
    with db.conectar() as c:
        sid = _rascunho(c, usuario_id, criar=False)
        if sid is not None:
            c.execute("DELETE FROM simulacao_transacoes WHERE simulacao_id = ?", (sid,))


# ---------------------------------------------------------------- análises guardadas

def buscar_analise(chave):
    """Resultado guardado com esta assinatura, ou None."""
    with db.conectar() as c:
        linha = c.execute("SELECT id, resultado, criado_em, duracao_ms FROM analises WHERE assinatura = ?",
                          (chave,)).fetchone()
        if linha is None:
            return None
        c.execute("UPDATE analises SET ultimo_uso = ? WHERE id = ?", (agora().isoformat(), linha["id"]))
    dados = json.loads(zlib.decompress(bytes(linha["resultado"])).decode("utf-8"))
    return linha["id"], dados, _texto(linha["criado_em"]), linha["duracao_ms"]


def guardar_analise(chave, base_assinatura, periodo_dias, dados, duracao_ms):
    """Guarda o resultado compactado (zlib). Retorna o id da análise."""
    bruto = zlib.compress(json.dumps(dados, ensure_ascii=False, allow_nan=False).encode("utf-8"), 6)
    with db.conectar() as c:
        existente = c.execute("SELECT id FROM analises WHERE assinatura = ?", (chave,)).fetchone()
        if existente:
            return existente["id"]
        cursor = c.execute(
            "INSERT INTO analises (assinatura, base_assinatura, periodo_dias, versao_motor, qtd_contas, "
            "qtd_transacoes, duracao_ms, resultado, criado_em, ultimo_uso) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (chave, base_assinatura, periodo_dias, analise.VERSAO_MOTOR, dados["dashboard"]["total_contas"],
             dados["dashboard"]["total_transacoes"], int(duracao_ms), bruto, agora().isoformat(), agora().isoformat()))
        return cursor.lastrowid


def limpar_analises_antigas(dias=30):
    """Apaga análises sem uso há mais de `dias` (o banco do Aiven gratuito é pequeno)."""
    limite = (agora() - timedelta(days=dias)).isoformat()
    with db.conectar() as c:
        return c.execute("DELETE FROM analises WHERE ultimo_uso < ?", (limite,)).rowcount


# ---------------------------------------------------------------- regras por modalidade (Fase 4)

def ler_ajustes_regras():
    """{regra: {acao, parametros, atualizado_por, atualizado_em}} gravados pelo administrador."""
    with db.conectar() as c:
        linhas = c.execute("SELECT * FROM regras_modalidade").fetchall()
    return {l["regra"]: {"acao": l["acao"], "parametros": json.loads(l["parametros"] or "{}"),
                         "atualizado_por": l["atualizado_por"], "atualizado_em": _texto(l["atualizado_em"])}
            for l in linhas}


def salvar_ajuste_regra(regra, acao, parametros, por):
    dados = (acao, json.dumps(parametros, ensure_ascii=False), por, agora().isoformat())
    with db.conectar() as c:
        if c.execute("SELECT regra FROM regras_modalidade WHERE regra = ?", (regra,)).fetchone():
            c.execute("UPDATE regras_modalidade SET acao = ?, parametros = ?, atualizado_por = ?, atualizado_em = ? "
                      "WHERE regra = ?", (*dados, regra))
        else:
            c.execute("INSERT INTO regras_modalidade (acao, parametros, atualizado_por, atualizado_em, regra) "
                      "VALUES (?, ?, ?, ?, ?)", (*dados, regra))


def apagar_ajuste_regra(regra):
    """Volta a regra ao padrão."""
    with db.conectar() as c:
        c.execute("DELETE FROM regras_modalidade WHERE regra = ?", (regra,))


# ---------------------------------------------------------------- histórico de simulações (Fase 4)

def _compactar(dados):
    return zlib.compress(json.dumps(dados, ensure_ascii=False, allow_nan=False).encode("utf-8"), 6)


def _descompactar(bruto):
    return json.loads(zlib.decompress(bytes(bruto)).decode("utf-8")) if bruto else None


def salvar_cenario(usuario_id, nome, descricao, transacoes, recorte, resumo, resultado, resultado_base):
    """Guarda a execução da simulação como cenário: transações, recorte e os DOIS resultados
    daquela execução (com e sem a simulação). O cenário nunca é recalculado depois: o grafo do
    histórico é sempre o daquele momento, mesmo que a base mude."""
    instante = agora().isoformat()
    with db.conectar() as c:
        sid = c.execute(
            "INSERT INTO simulacoes (usuario_id, situacao, criado_em, atualizado_em, nome, descricao, salvo_em, "
            "recorte, resumo, resultado, resultado_base) VALUES (?, 'salva', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (usuario_id, instante, instante, nome, descricao, instante, json.dumps(recorte, ensure_ascii=False),
             json.dumps(resumo, ensure_ascii=False), _compactar(resultado), _compactar(resultado_base))).lastrowid
        for linha in transacoes:
            c.execute("INSERT INTO simulacao_transacoes (simulacao_id, id_transacao, conta_origem, conta_destino, "
                      "valor, data, hora, tipo_transacao, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (sid, linha["id_transacao"], linha["conta_origem"], linha["conta_destino"], linha["valor"],
                       linha["data"], linha["hora"], linha["tipo_transacao"], instante))
    return sid


def listar_cenarios(usuario_id):
    with db.conectar() as c:
        linhas = c.execute("SELECT s.id, s.nome, s.descricao, s.salvo_em, s.recorte, s.resumo, "
                           "(SELECT COUNT(*) FROM simulacao_transacoes t WHERE t.simulacao_id = s.id) AS qtd "
                           "FROM simulacoes s WHERE s.usuario_id = ? AND s.situacao = 'salva' ORDER BY s.id DESC",
                           (usuario_id,)).fetchall()
    return [{"id": l["id"], "nome": l["nome"], "descricao": l["descricao"] or "", "salvo_em": _texto(l["salvo_em"]),
             "recorte": json.loads(l["recorte"] or "{}"), "resumo": json.loads(l["resumo"] or "{}"),
             "transacoes": l["qtd"]} for l in linhas]


def obter_cenario(usuario_id, cenario_id, com_resultados=True):
    """Cenário do próprio usuário (None se não existe ou é de outra pessoa)."""
    with db.conectar() as c:
        linha = c.execute("SELECT * FROM simulacoes WHERE id = ? AND usuario_id = ? AND situacao = 'salva'",
                          (cenario_id, usuario_id)).fetchone()
        if linha is None:
            return None
        transacoes = c.execute("SELECT id_transacao, conta_origem, conta_destino, valor, data, hora, tipo_transacao "
                               "FROM simulacao_transacoes WHERE simulacao_id = ? ORDER BY id", (cenario_id,)).fetchall()
    cenario = {"id": linha["id"], "nome": linha["nome"], "descricao": linha["descricao"] or "",
               "salvo_em": _texto(linha["salvo_em"]), "recorte": json.loads(linha["recorte"] or "{}"),
               "resumo": json.loads(linha["resumo"] or "{}"),
               "transacoes": [{"id_transacao": l["id_transacao"], "conta_origem": l["conta_origem"],
                               "conta_destino": l["conta_destino"], "valor": _texto(l["valor"]), "data": _texto(l["data"]),
                               "hora": _hora(l["hora"]), "tipo_transacao": l["tipo_transacao"]} for l in transacoes]}
    if com_resultados:
        cenario["resultado"] = _descompactar(linha["resultado"])
        cenario["resultado_base"] = _descompactar(linha["resultado_base"])
    return cenario


def excluir_cenario(usuario_id, cenario_id):
    with db.conectar() as c:
        if not c.execute("SELECT id FROM simulacoes WHERE id = ? AND usuario_id = ? AND situacao = 'salva'",
                         (cenario_id, usuario_id)).fetchone():
            return False
        c.execute("DELETE FROM simulacao_transacoes WHERE simulacao_id = ?", (cenario_id,))
        c.execute("DELETE FROM simulacoes WHERE id = ?", (cenario_id,))
    return True


def restaurar_cenario(usuario_id, cenario_id):
    """Copia as transações do cenário para a simulação em andamento (substitui o que estava lá)."""
    cenario = obter_cenario(usuario_id, cenario_id, com_resultados=False)
    if cenario is None:
        return None
    limpar_simulacao(usuario_id)
    if cenario["transacoes"]:
        adicionar_simuladas(usuario_id, cenario["transacoes"])
    return cenario
