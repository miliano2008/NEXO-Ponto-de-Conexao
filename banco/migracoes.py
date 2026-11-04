"""NEXO — migrações do banco de dados (MySQL/Aiven e SQLite local).

Cada migração tem um número e é aplicada UMA vez, em ordem, quando o sistema
inicia. As aplicadas ficam registradas na tabela `versao_esquema`.

Regras para criar uma migração nova:
  1. acrescente uma função ao final de MIGRACOES (nunca altere uma já publicada);
  2. ela precisa ser idempotente (CREATE ... IF NOT EXISTS, checar coluna antes de criar);
  3. escreva o SQL para os dois bancos (o parâmetro `mysql` diz qual está em uso);
  4. faça backup antes de rodar no Aiven: scripts/BACKUP.bat.
"""

from datetime import datetime

from banco import conexao as db


class ErroVersao(RuntimeError):
    """O banco foi migrado por uma versão mais nova do NEXO do que a instalada."""


# ---------------------------------------------------------------- utilitários

def _colunas(c, mysql, tabela):
    if mysql:
        linhas = c.execute("SELECT COLUMN_NAME AS nome FROM information_schema.columns "
                           "WHERE table_schema = DATABASE() AND table_name = ?", (tabela,)).fetchall()
        return {l["nome"] for l in linhas}
    return {l["name"] for l in c.execute(f"PRAGMA table_info({tabela})").fetchall()}


def _adicionar_coluna(c, mysql, tabela, coluna, tipo_mysql, tipo_sqlite):
    if coluna not in _colunas(c, mysql, tabela):
        c.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo_mysql if mysql else tipo_sqlite}")


# ---------------------------------------------------------------- 1. acesso (v0.3)

_ACESSO_MYSQL = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    documento VARCHAR(14) NOT NULL UNIQUE,
    tipo_documento ENUM('CPF','CNPJ') NOT NULL,
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(190) NOT NULL UNIQUE,
    telefone VARCHAR(11) NULL,
    email_confirmado TINYINT(1) NOT NULL DEFAULT 1,
    senha_hash VARCHAR(255) NOT NULL,
    cargo ENUM('administrador','analista','auditor','visualizador') NOT NULL DEFAULT 'visualizador',
    ativo TINYINT(1) NOT NULL DEFAULT 1,
    tentativas_falhas INT NOT NULL DEFAULT 0,
    bloqueado_ate DATETIME NULL,
    criado_em DATETIME NOT NULL,
    ultimo_login DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS tokens_recuperacao (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    tipo VARCHAR(10) NOT NULL DEFAULT 'senha',
    token_hash CHAR(64) NOT NULL UNIQUE,
    expira_em DATETIME NOT NULL,
    usado TINYINT(1) NOT NULL DEFAULT 0,
    criado_em DATETIME NOT NULL,
    CONSTRAINT fk_token_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS convites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo_hash CHAR(64) NOT NULL UNIQUE,
    prefixo CHAR(4) NOT NULL,
    cargo ENUM('administrador','analista','auditor','visualizador') NOT NULL,
    max_usos INT NOT NULL,
    usos INT NOT NULL DEFAULT 0,
    expira_em DATETIME NOT NULL,
    revogado TINYINT(1) NOT NULL DEFAULT 0,
    criado_por VARCHAR(150) NULL,
    criado_em DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS auditoria (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data DATETIME NOT NULL,
    evento VARCHAR(40) NOT NULL,
    documento VARCHAR(14) NULL,
    detalhe VARCHAR(255) NULL,
    ip VARCHAR(45) NULL,
    INDEX ix_auditoria_data (data)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

_ACESSO_SQLITE = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento TEXT NOT NULL UNIQUE,
    tipo_documento TEXT NOT NULL CHECK (tipo_documento IN ('CPF', 'CNPJ')),
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    telefone TEXT,
    email_confirmado INTEGER NOT NULL DEFAULT 1,
    senha_hash TEXT NOT NULL,
    cargo TEXT NOT NULL DEFAULT 'visualizador',
    ativo INTEGER NOT NULL DEFAULT 1,
    tentativas_falhas INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate TEXT,
    criado_em TEXT NOT NULL,
    ultimo_login TEXT
);
CREATE TABLE IF NOT EXISTS tokens_recuperacao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL DEFAULT 'senha',
    token_hash TEXT NOT NULL UNIQUE,
    expira_em TEXT NOT NULL,
    usado INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS convites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_hash TEXT NOT NULL UNIQUE,
    prefixo TEXT NOT NULL,
    cargo TEXT NOT NULL,
    max_usos INTEGER NOT NULL,
    usos INTEGER NOT NULL DEFAULT 0,
    expira_em TEXT NOT NULL,
    revogado INTEGER NOT NULL DEFAULT 0,
    criado_por TEXT,
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    evento TEXT NOT NULL,
    documento TEXT,
    detalhe TEXT,
    ip TEXT
)
"""


def m1_acesso(c, mysql):
    """Usuários, links por e-mail, convites e auditoria (estado da versão 0.3)."""
    c.executar_script(_ACESSO_MYSQL if mysql else _ACESSO_SQLITE)
    # bancos criados antes da 0.3 (ex.: o Aiven do grupo) ganham as colunas que faltavam;
    # email_confirmado entra com 1: quem já usava o sistema continua entrando
    _adicionar_coluna(c, mysql, "usuarios", "telefone", "VARCHAR(11) NULL", "TEXT")
    _adicionar_coluna(c, mysql, "usuarios", "email_confirmado", "TINYINT(1) NOT NULL DEFAULT 1",
                      "INTEGER NOT NULL DEFAULT 1")
    _adicionar_coluna(c, mysql, "tokens_recuperacao", "tipo", "VARCHAR(10) NOT NULL DEFAULT 'senha'",
                      "TEXT NOT NULL DEFAULT 'senha'")


# ---------------------------------------------------------------- 2. simulações por usuário

def m2_simulacoes(c, mysql):
    """Cada usuário tem a própria simulação, guardada no banco (antes: lista global na memória)."""
    if mysql:
        c.executar_script("""
CREATE TABLE IF NOT EXISTS simulacoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    situacao VARCHAR(12) NOT NULL DEFAULT 'rascunho',
    criado_em DATETIME NOT NULL,
    atualizado_em DATETIME NOT NULL,
    INDEX ix_simulacao_usuario (usuario_id, situacao),
    CONSTRAINT fk_simulacao_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS simulacao_transacoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    simulacao_id INT NOT NULL,
    id_transacao VARCHAR(10) NOT NULL,
    conta_origem VARCHAR(10) NOT NULL,
    conta_destino VARCHAR(10) NOT NULL,
    valor DECIMAL(12,2) NOT NULL,
    data DATE NOT NULL,
    hora TIME NOT NULL,
    tipo_transacao VARCHAR(20) NOT NULL,
    criado_em DATETIME NOT NULL,
    UNIQUE KEY uq_simulacao_transacao (simulacao_id, id_transacao),
    CONSTRAINT ck_sim_valor CHECK (valor > 0),
    CONSTRAINT ck_sim_contas CHECK (conta_origem <> conta_destino),
    CONSTRAINT fk_sim_transacao FOREIGN KEY (simulacao_id) REFERENCES simulacoes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    else:
        c.executar_script("""
CREATE TABLE IF NOT EXISTS simulacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    situacao TEXT NOT NULL DEFAULT 'rascunho',
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_simulacao_usuario ON simulacoes (usuario_id, situacao);
CREATE TABLE IF NOT EXISTS simulacao_transacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulacao_id INTEGER NOT NULL REFERENCES simulacoes(id) ON DELETE CASCADE,
    id_transacao TEXT NOT NULL,
    conta_origem TEXT NOT NULL,
    conta_destino TEXT NOT NULL,
    valor TEXT NOT NULL,
    data TEXT NOT NULL,
    hora TEXT NOT NULL,
    tipo_transacao TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    UNIQUE (simulacao_id, id_transacao)
)""")


# ---------------------------------------------------------------- 3. análises guardadas

def m3_analises(c, mysql):
    """Resultado de cada análise da base, compactado e identificado por uma assinatura.

    A assinatura é o hash dos dados + parâmetros: os mesmos dados nunca são
    recalculados, e cada resultado pode ser rastreado (base dos relatórios e do
    histórico de simulações das próximas fases).
    """
    if mysql:
        c.executar_script("""
CREATE TABLE IF NOT EXISTS analises (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assinatura CHAR(64) NOT NULL UNIQUE,
    base_assinatura CHAR(64) NOT NULL,
    periodo_dias INT NOT NULL,
    versao_motor VARCHAR(20) NOT NULL,
    qtd_contas INT NOT NULL,
    qtd_transacoes INT NOT NULL,
    duracao_ms INT NOT NULL,
    resultado MEDIUMBLOB NOT NULL,
    criado_em DATETIME NOT NULL,
    ultimo_uso DATETIME NOT NULL,
    INDEX ix_analise_base (base_assinatura)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    else:
        c.executar_script("""
CREATE TABLE IF NOT EXISTS analises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assinatura TEXT NOT NULL UNIQUE,
    base_assinatura TEXT NOT NULL,
    periodo_dias INTEGER NOT NULL,
    versao_motor TEXT NOT NULL,
    qtd_contas INTEGER NOT NULL,
    qtd_transacoes INTEGER NOT NULL,
    duracao_ms INTEGER NOT NULL,
    resultado BLOB NOT NULL,
    criado_em TEXT NOT NULL,
    ultimo_uso TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_analise_base ON analises (base_assinatura)""")


MIGRACOES = [
    (1, "Acesso: usuários, links por e-mail, convites e auditoria", m1_acesso),
    (2, "Simulações por usuário", m2_simulacoes),
    (3, "Análises guardadas e rastreáveis", m3_analises),
]
VERSAO_ATUAL = MIGRACOES[-1][0]


def _tabela_versao(c, mysql):
    if mysql:
        c.execute("CREATE TABLE IF NOT EXISTS versao_esquema (versao INT PRIMARY KEY, descricao VARCHAR(150) "
                  "NOT NULL, aplicado_em DATETIME NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")
    else:
        c.execute("CREATE TABLE IF NOT EXISTS versao_esquema (versao INTEGER PRIMARY KEY, "
                  "descricao TEXT NOT NULL, aplicado_em TEXT NOT NULL)")


def _existe_tabela_versao(c, mysql):
    if mysql:
        return c.execute("SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema = DATABASE() "
                         "AND table_name = 'versao_esquema'").fetchone()["n"] > 0
    return c.execute("SELECT COUNT(*) AS n FROM sqlite_master WHERE type = 'table' "
                     "AND name = 'versao_esquema'").fetchone()["n"] > 0


def versoes_aplicadas():
    """Números das migrações já aplicadas (só lê: não cria nada no banco)."""
    with db.conectar() as c:
        if not _existe_tabela_versao(c, db.usando_mysql()):
            return []
        return sorted(l["versao"] for l in c.execute("SELECT versao FROM versao_esquema").fetchall())


def aplicar(registrar=print):
    """Aplica as migrações pendentes. Retorna a lista das que foram aplicadas agora."""
    mysql = db.usando_mysql()
    with db.conectar() as c:
        _tabela_versao(c, mysql)
    aplicadas = versoes_aplicadas()
    if aplicadas and max(aplicadas) > VERSAO_ATUAL:
        raise ErroVersao(f"O banco está na versão {max(aplicadas)} do esquema, mas este NEXO conhece só até a "
                         f"{VERSAO_ATUAL}. Atualize o projeto (git pull ou o zip mais recente) antes de usar.")
    novas = []
    for numero, descricao, funcao in MIGRACOES:
        if numero in aplicadas:
            continue
        # cada migração numa transação: se falhar no meio, nada fica registrado
        with db.conectar() as c:
            funcao(c, mysql)
            insercao = "INSERT IGNORE INTO" if mysql else "INSERT OR IGNORE INTO"
            c.execute(f"{insercao} versao_esquema (versao, descricao, aplicado_em) VALUES (?, ?, ?)",
                      (numero, descricao, datetime.now().replace(microsecond=0).isoformat()))
        novas.append(numero)
        if registrar:
            registrar(f"  Banco atualizado: migração {numero} — {descricao}")
    return novas
