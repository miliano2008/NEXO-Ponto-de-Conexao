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
