"""Testes da Fase 0: configuração, migrações, simulação por usuário, cache, matrizes,
compressão e backup.

Executar (na raiz do projeto): python -m testes.test_fase0
Usa CSV + SQLite temporários: nunca toca no banco do grupo nem no .env real.
"""
import gzip
import os
import sqlite3
import tempfile
from pathlib import Path

os.environ["NEXO_BANCO"] = "local"

# variáveis de configuração do computador (DB_*, SMTP_*...) não podem interferir nos testes
for _chave in [k for k in os.environ if k.startswith(("DB_", "SMTP_", "APP_URL"))]:
    del os.environ[_chave]

from banco import conexao as db  # noqa: E402

TEMP = Path(tempfile.mkdtemp())
db.SQLITE = TEMP / "teste.db"

from nucleo import configuracao  # noqa: E402

# ------------------------------------------------------------------ 1. configuração
original = (configuracao.ARQUIVO_ENV, configuracao.CONFIG_INI)
configuracao.ARQUIVO_ENV = TEMP / ".env"
configuracao.CONFIG_INI = [TEMP / "config.ini"]
try:
    assert configuracao.valores() == {} and configuracao.origem() is None

    # config.ini antigo (v0.3), salvo pelo Bloco de Notas (BOM) e com '%' na senha
    (TEMP / "config.ini").write_bytes("﻿[mysql]\nhost = h-antigo\nporta = 21345\nsenha = AVNS_a%b\n"
                                      "ssl_ca = dados/ca.pem\n[smtp]\nhost = smtp.gmail.com\n".encode("utf-8"))
    v = configuracao.valores()
    assert v["DB_HOST"] == "h-antigo" and v["DB_PORT"] == "21345" and v["DB_PASSWORD"] == "AVNS_a%b", v
    assert v["SMTP_HOST"] == "smtp.gmail.com"

    # o .env vence o config.ini; variável de ambiente vence os dois
    configuracao.salvar_env({"DB_HOST": "h-env", "DB_PASSWORD": "segredo=com=igual"})
    assert configuracao.valores()["DB_HOST"] == "h-env"
    assert configuracao.valores()["DB_PASSWORD"] == "segredo=com=igual"
    assert configuracao.valores()["DB_PORT"] == "21345"            # o que o .env não tem vem do config.ini
    os.environ["DB_HOST"] = "h-ambiente"
    assert configuracao.valores()["DB_HOST"] == "h-ambiente"
    del os.environ["DB_HOST"]
    assert configuracao.origem().endswith(".env")

    # caminho antigo dados/ca.pem passa a apontar para banco/dados/ca.pem
    assert configuracao.caminho("dados/ca.pem") == configuracao.RAIZ / "banco" / "dados" / "ca.pem"
    assert configuracao.caminho("") is None

    # NEXO_BANCO=local sempre ignora o MySQL (proteção dos testes)
    assert db.config_mysql() is None
    del os.environ["NEXO_BANCO"]
    cfg = db.config_mysql()
    assert cfg["host"] == "h-env" and cfg["porta"] == 21345 and cfg["banco"] == "nexo"
    os.environ["NEXO_BANCO"] = "local"
finally:
    configuracao.ARQUIVO_ENV, configuracao.CONFIG_INI = original
    configuracao._cache["chave"] = None
print("ok — configuração (.env, config.ini antigo, BOM, '%', prioridades, caminho antigo)")

# ------------------------------------------------------------------ 2. migrações
from banco import migracoes  # noqa: E402

# banco criado pela versão 0.2 (sem telefone, e-mail confirmado, tipo de token, convites, simulações)
db.SQLITE = TEMP / "antigo.db"
antigo = sqlite3.connect(db.SQLITE)
antigo.executescript("""
CREATE TABLE usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, documento TEXT NOT NULL UNIQUE,
  tipo_documento TEXT NOT NULL, nome TEXT NOT NULL, email TEXT NOT NULL UNIQUE, senha_hash TEXT NOT NULL,
  cargo TEXT NOT NULL DEFAULT 'visualizador', ativo INTEGER NOT NULL DEFAULT 1,
  tentativas_falhas INTEGER NOT NULL DEFAULT 0, bloqueado_ate TEXT, criado_em TEXT NOT NULL, ultimo_login TEXT);
CREATE TABLE tokens_recuperacao (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER NOT NULL,
  token_hash TEXT NOT NULL UNIQUE, expira_em TEXT NOT NULL, usado INTEGER NOT NULL DEFAULT 0, criado_em TEXT NOT NULL);
CREATE TABLE auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, evento TEXT NOT NULL,
  documento TEXT, detalhe TEXT, ip TEXT);
INSERT INTO usuarios (documento, tipo_documento, nome, email, senha_hash, cargo, criado_em)
  VALUES ('52998224725', 'CPF', 'Usuário Antigo', 'antigo@nexo.test', 'hash-antigo', 'administrador', '2026-10-01T10:00:00');
""")
antigo.commit()
antigo.close()
assert migracoes.aplicar(registrar=None) == [1, 2, 3]
assert migracoes.aplicar(registrar=None) == []                       # idempotente
with db.conectar() as c:
    u = c.execute("SELECT * FROM usuarios WHERE documento = '52998224725'").fetchone()
    assert u["nome"] == "Usuário Antigo" and u["senha_hash"] == "hash-antigo"   # dados preservados
    assert u["email_confirmado"] == 1 and u["telefone"] is None                  # quem já usava continua entrando
    tabelas = {l["name"] for l in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
assert {"convites", "simulacoes", "simulacao_transacoes", "analises", "versao_esquema"} <= tabelas

# banco migrado por uma versão mais nova: esta versão se recusa a usar
with db.conectar() as c:
    c.execute("INSERT INTO versao_esquema (versao, descricao, aplicado_em) VALUES (99, 'futura', '2030-01-01')")
try:
    migracoes.aplicar(registrar=None)
    raise AssertionError("aceitou banco de versão mais nova")
except migracoes.ErroVersao as erro:
    assert "versão 99" in str(erro)
print("ok — migrações (banco 0.2 atualizado sem perder dados, idempotência, proteção de versão)")

# ------------------------------------------------------------------ 3. servidor: simulação por usuário, cache, matrizes
db.SQLITE = TEMP / "servidor.db"
from app import analises, auth  # noqa: E402
from app import servidor  # noqa: E402
from banco import repositorio  # noqa: E402

auth.iniciar_banco()
H = {"X-Requested-With": "NEXO"}
for doc, nome, email in [("52998224725", "Ana", "ana@nexo.test"), ("11144477735", "Beto", "beto@nexo.test")]:
    auth.cadastrar(doc, nome, email, "11912345678", "Senha123", "Senha123", cargo="analista", email_confirmado=True)


def entrar(doc):
    servidor._tentativas_ip.clear()
    c = servidor.app.test_client()
    assert c.post("/auth/entrar", headers=H, json={"documento": doc, "senha": "Senha123"}).status_code == 200
    return c


ana, beto = entrar("52998224725"), entrar("11144477735")
nova = {"de": "C001", "para": "C030", "valor": "45000", "data": "2026-09-15", "hora": "12:00", "tipo": "PIX"}
assert ana.post("/api/transacoes", headers=H, json=nova).status_code == 201

r_ana, r_beto = ana.get("/api/resultados").get_json(), beto.get("/api/resultados").get_json()
assert r_ana["simulacao"]["transacoes_simuladas"] == 1 and r_ana["dashboard"]["total_transacoes"] == 161
assert r_beto["simulacao"]["transacoes_simuladas"] == 0 and r_beto["dashboard"]["total_transacoes"] == 160
assert beto.delete("/api/transacoes/S0001", headers=H).status_code == 404       # não desfaz a simulação da Ana
assert beto.post("/api/simulacao/restaurar", headers=H).status_code == 200
assert ana.get("/api/resultados").get_json()["simulacao"]["transacoes_simuladas"] == 1

# a simulação sobrevive ao "reinício" do servidor (fica no banco, não na memória)
analises.limpar_cache()
assert entrar("52998224725").get("/api/resultados").get_json()["simulacao"]["lista_simuladas"][0]["id_transacao"] == "S0001"

# transação inválida não é gravada
for ruim in [{**nova, "para": "C001"}, {**nova, "valor": "-5"}, {**nova, "de": "X999"}, {**nova, "hora": "25:00"}]:
    assert ana.post("/api/transacoes", headers=H, json=ruim).status_code == 400
assert len(repositorio.listar_simuladas(1)) == 1

# limite de transações simuladas por usuário
limite_original = repositorio.LIMITE_SIMULADAS
repositorio.LIMITE_SIMULADAS = 2
assert ana.post("/api/transacoes", headers=H, json={**nova, "valor": "10"}).status_code == 201
r = ana.post("/api/transacoes", headers=H, json={**nova, "valor": "11"})
assert r.status_code == 400 and "Limite" in r.get_json()["erro"]
repositorio.LIMITE_SIMULADAS = limite_original
assert ana.post("/api/simulacao/restaurar", headers=H).status_code == 200

# cache e rastreabilidade: a análise da base tem número e assinatura fixos
analises.limpar_cache()
r1 = beto.get("/api/resultados").get_json()["analise"]
r2 = beto.get("/api/resultados").get_json()["analise"]
assert r1["origem"] == "cálculo" and r2["origem"] == "memória"
assert r1["id"] == r2["id"] and r1["id"] is not None and r1["assinatura"] == r2["assinatura"]
guardada = repositorio.buscar_analise(next(iter(analises._cache)))
assert guardada and guardada[1]["dashboard"]["total_transacoes"] == 160
r7 = beto.get("/api/resultados?dias=7").get_json()["analise"]
assert r7["assinatura"] != r1["assinatura"]                         # outro período, outra análise

# matrizes só sob demanda
resposta = beto.get("/api/resultados").get_json()
assert "matrizes" not in resposta
m = beto.get("/api/matrizes").get_json()["matrizes"]
assert len(m["ordem_contas"]) == 40 and len(m["A"]) == 40 and len(m["L_simetrica"][0]) == 40
assert "matrizes" in beto.get("/api/exportar").get_json()          # exportação continua completa

# a base é relida do banco: uma mudança na fonte aparece sem reiniciar
carregar_original = repositorio.carregar_dados
contas, transacoes = carregar_original()
repositorio.carregar_dados = lambda: (contas, transacoes[:150])
analises.RECARGA_SEGUNDOS = 0
assert beto.get("/api/resultados").get_json()["dashboard"]["total_transacoes"] == 150
repositorio.carregar_dados = carregar_original
assert beto.get("/api/resultados").get_json()["dashboard"]["total_transacoes"] == 160
analises.RECARGA_SEGUNDOS = 60
print("ok — simulação por usuário (isolada, persistente, validada, com limite), cache, matrizes e recarga da base")

# ------------------------------------------------------------------ 4. compressão e arquivos estáticos
sem = beto.get("/api/resultados")
com = beto.get("/api/resultados", headers={"Accept-Encoding": "gzip"})
assert com.headers["Content-Encoding"] == "gzip" and "Accept-Encoding" in com.headers["Vary"]
assert len(com.data) < len(sem.data) / 4
assert gzip.decompress(com.data) == sem.data
js = beto.get("/static/js/app.js", headers={"Accept-Encoding": "gzip"})
assert js.status_code == 200 and js.headers["Content-Encoding"] == "gzip"
etag = js.headers["ETag"]
assert etag.startswith("W/")
assert "max-age=0" in js.headers["Cache-Control"]                    # o navegador sempre revalida
assert beto.get("/static/js/app.js", headers={"If-None-Match": etag}).status_code == 304
for arquivo in ["css/tokens.css", "css/base.css", "css/componentes.css", "css/paginas.css", "css/responsivo.css",
                "js/nucleo/roteador.js", "js/paginas/rede.js", "js/login.js"]:
    assert beto.get(f"/static/{arquivo}").status_code == 200, arquivo
print("ok — compressão gzip, revalidação (304) e arquivos estáticos")

# ------------------------------------------------------------------ 5. backup (modo local)
from banco import backup  # noqa: E402

backup.PASTA_BACKUPS = TEMP / "backups"
arquivo, _ = backup.fazer_backup()
copia = sqlite3.connect(arquivo)
assert copia.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 2
copia.close()
print("ok — backup do banco local")

print("TESTES OK: Fase 0 — configuração, migrações, simulação por usuário, cache, matrizes, compressão e backup.")
