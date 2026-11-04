"""NEXO — conexão com o banco de dados.

Se DB_HOST estiver configurado (.env ou config.ini), tudo usa o MySQL (ex.: Aiven):
contas, transações, usuários, simulações, análises e auditoria. Sem ele, o projeto
usa os CSVs para os dados e o SQLite local (banco/dados/nexo.db) para o resto.

O resto do código escreve SQL com "?" (estilo SQLite); aqui ele é convertido
para "%s" quando o banco é MySQL.
"""

import os
import sqlite3
import ssl as ssl_lib
import threading
from contextlib import contextmanager
from pathlib import Path

from nucleo import configuracao

SQLITE = configuracao.PASTA_DADOS / "nexo.db"
CA_PADRAO = configuracao.PASTA_DADOS / "ca.pem"

try:
    import pymysql
    import pymysql.cursors
    ErroIntegridade = (sqlite3.IntegrityError, pymysql.err.IntegrityError)
except ImportError:  # PyMySQL só é obrigatório quando o MySQL está configurado
    pymysql = None
    ErroIntegridade = (sqlite3.IntegrityError,)


class ErroBanco(RuntimeError):
    pass


def config_mysql():
    """Dados de conexão do MySQL (DB_* no .env ou [mysql] no config.ini), ou None."""
    if os.environ.get("NEXO_BANCO") == "local":  # usado pelos testes: nunca tocar no banco real
        return None
    v = configuracao.valores()
    if not v.get("DB_HOST", "").strip():
        return None
    ca = configuracao.caminho(v.get("DB_SSL_CA", ""))
    try:
        porta = int(v.get("DB_PORT") or 3306)
    except ValueError as erro:
        raise ErroBanco(f"DB_PORT inválida: {v.get('DB_PORT')!r}. Use só o número do 'Port' do Aiven.") from erro
    return {"host": v["DB_HOST"].strip(), "porta": porta,
            "usuario": v.get("DB_USER", "").strip(), "senha": v.get("DB_PASSWORD", ""),
            "banco": os.environ.get("NEXO_MYSQL_BANCO") or v.get("DB_NAME", "").strip() or "nexo",
            "ssl_ca": str(ca) if ca else ""}


def usando_mysql():
    return config_mysql() is not None


def descricao():
    c = config_mysql()
    return f"MySQL {c['host']}:{c['porta']}/{c['banco']}" if c else "SQLite local + CSV"


def conectar_mysql(com_banco=True):
    """Conexão PyMySQL direta (usada também pelo script de migração)."""
    c = config_mysql()
    if pymysql is None:
        raise ErroBanco("PyMySQL não instalado. Rode: python -m pip install -r requirements.txt")
    if c["ssl_ca"] and not Path(c["ssl_ca"]).exists():
        raise ErroBanco(f"Certificado CA não encontrado: {c['ssl_ca']}. Baixe o 'CA certificate' no console do Aiven.")
    # Aiven exige SSL; com o ca.pem o certificado do servidor é verificado.
    ssl = {"ca": c["ssl_ca"]} if c["ssl_ca"] else {"check_hostname": False}
    try:
        return pymysql.connect(host=c["host"], port=c["porta"], user=c["usuario"], password=c["senha"],
                               database=c["banco"] if com_banco else None, ssl=ssl,
                               charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                               connect_timeout=15, autocommit=False)
    except ssl_lib.SSLError as erro:
        raise ErroBanco(f"Certificado {c['ssl_ca']} inválido ou não é o do seu serviço. "
                        "Baixe de novo: Aiven → Overview → CA certificate → Download.") from erro
    except pymysql.err.OperationalError as erro:
        codigo = erro.args[0] if erro.args else None
        dica = {1045: "usuário ou senha incorretos", 1049: f"o banco '{c['banco']}' não existe — rode scripts\\MIGRAR_MYSQL.bat",
                2003: "servidor inacessível: confira host/porta e se o serviço está 'Running' no Aiven"}.get(codigo, "")
        raise ErroBanco(f"Não foi possível conectar ao MySQL ({dica or erro}).") from erro


class _Conexao:
    """Adapta a conexão para aceitar SQL com '?' nos dois bancos."""

    def __init__(self, bruta, mysql):
        self.bruta, self.mysql = bruta, mysql

    def execute(self, sql, parametros=()):
        if self.mysql:
            cursor = self.bruta.cursor()
            cursor.execute(sql.replace("?", "%s"), parametros)
            return cursor
        return self.bruta.execute(sql, parametros)

    def executar_script(self, script):
        for comando in (c.strip() for c in script.split(";")):
            if comando:
                self.execute(comando)


# Uma conexão MySQL por thread, reaproveitada: abrir TLS com o Aiven a cada
# pedido deixaria cada clique centenas de milissegundos mais lento.
_local = threading.local()


def _mysql_reutilizavel():
    conexao = getattr(_local, "mysql", None)
    if conexao is not None:
        try:
            conexao.ping(reconnect=True)
            return conexao
        except Exception:  # noqa: BLE001 — conexão perdida: abre outra
            _local.mysql = None
    _local.mysql = conectar_mysql()
    return _local.mysql


@contextmanager
def conectar():
    """Abre uma transação: confirma no fim, desfaz em caso de erro."""
    if usando_mysql():
        bruta = _mysql_reutilizavel()
        try:
            yield _Conexao(bruta, True)
            bruta.commit()
        except Exception:
            try:
                bruta.rollback()
            except Exception:  # noqa: BLE001
                _local.mysql = None
            raise
        return
    SQLITE.parent.mkdir(parents=True, exist_ok=True)
    bruta = sqlite3.connect(SQLITE, timeout=10)
    bruta.row_factory = sqlite3.Row
    bruta.execute("PRAGMA foreign_keys = ON")
    try:
        yield _Conexao(bruta, False)
        bruta.commit()
    except Exception:
        bruta.rollback()
        raise
    finally:
        bruta.close()


# ---------------------------------------------------------------- esquemas

# Tipos das tabelas de dados conforme a aba Dicionario_Dados do Excel.
ESQUEMA_DADOS_MYSQL = """
CREATE TABLE IF NOT EXISTS contas (
    id_conta VARCHAR(10) NOT NULL PRIMARY KEY,
    tipo_titular VARCHAR(20) NOT NULL,
    data_abertura DATE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS transacoes (
    id_transacao VARCHAR(10) NOT NULL PRIMARY KEY,
    conta_origem VARCHAR(10) NOT NULL,
    conta_destino VARCHAR(10) NOT NULL,
    valor DECIMAL(12,2) NOT NULL,
    data DATE NOT NULL,
    hora TIME NOT NULL,
    tipo_transacao VARCHAR(20) NOT NULL,
    CONSTRAINT fk_tx_origem FOREIGN KEY (conta_origem) REFERENCES contas(id_conta),
    CONSTRAINT fk_tx_destino FOREIGN KEY (conta_destino) REFERENCES contas(id_conta),
    CONSTRAINT ck_tx_valor CHECK (valor > 0),
    CONSTRAINT ck_tx_contas CHECK (conta_origem <> conta_destino),
    INDEX ix_tx_data (data)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
