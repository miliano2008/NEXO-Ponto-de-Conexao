"""Teste de integração com o MySQL (Aiven) usando um banco TEMPORÁRIO.

Executar (na raiz do projeto): python -m testes.test_mysql
Cria o banco 'nexo_teste', migra os dados, testa login/cadastro/recuperação/cargos
e a API do simulador, e apaga o banco no final. O banco real ('nexo') não é tocado.
"""
import os
import random
import re
import subprocess
import sys

os.environ["NEXO_MYSQL_BANCO"] = "nexo_teste"
from banco import conexao as db  # noqa: E402
from nucleo.configuracao import RAIZ  # noqa: E402

if not db.usando_mysql():
    print("Banco MySQL não configurado (DB_HOST vazio); nada a testar.")
    raise SystemExit(0)

r = subprocess.run([sys.executable, "-m", "banco.migrar_mysql", "--recriar"], capture_output=True, text=True,
                   env=os.environ, cwd=RAIZ)
print(r.stdout[-400:])
assert r.returncode == 0, r.stdout + r.stderr

try:
    from app import auth
    from banco import repositorio
    contas, transacoes = repositorio.carregar_dados()
    assert (len(contas), len(transacoes)) == (40, 160)
    assert repositorio.carregar_csv() == (contas, transacoes), "MySQL diferente do CSV"

    from app import envio_email
    from app import servidor
    enviados = []
    envio_email.enviar = lambda destino, assunto, texto, html=None: enviados.append(texto)
    envio_email.configurado = lambda: True
    H = {"X-Requested-With": "NEXO"}
    c = servidor.app.test_client()
    def gerar_cpf():
        # CPF válido aleatório: o banco temporário recebe cópias dos usuários locais, então não usar um fixo
        d = [random.randint(0, 9) for _ in range(9)]
        for _ in range(2):
            r = sum(v * p for v, p in zip(d, range(len(d) + 1, 1, -1))) % 11
            d.append(0 if r < 2 else 11 - r)
        return "".join(map(str, d))

    doc, doc_convite = gerar_cpf(), gerar_cpf()
    dados = {"documento": doc, "nome": "Teste MySQL", "email": f"mysql{doc}@nexo.test", "telefone": "11912345678",
             "senha": "Mysql2026", "confirmacao": "Mysql2026"}
    assert c.post("/auth/entrar", headers=H, json={"documento": doc, "senha": "x"}).get_json() == \
        {"erro": auth.MENSAGEM_LOGIN_INVALIDO}
    r = c.post("/auth/cadastrar", headers=H, json=dados)
    assert r.status_code == 201 and r.get_json()["enviado"], r.get_json()
    assert c.post("/auth/cadastrar", headers=H, json={**dados, "email": "d@d.com"}).status_code == 400
    assert c.post("/auth/entrar", headers=H, json={"documento": doc, "senha": "Mysql2026"}).status_code == 403
    token = re.search(r"/confirmar\?token=([\w-]+)", enviados[-1]).group(1)
    assert c.post("/auth/confirmar", headers=H, json={"token": token}).status_code == 200
    assert c.post("/auth/entrar", headers=H, json={"documento": doc, "senha": "Mysql2026"}).status_code == 200
    assert c.get("/api/resultados").get_json()["dashboard"]["total_transacoes"] == 160
    c.post("/auth/sair", headers=H)
    r = c.post("/auth/entrar", headers=H, json={"documento": doc, "senha": "errada1"})
    assert r.get_json() == {"erro": auth.MENSAGEM_LOGIN_INVALIDO}
    assert c.post("/auth/esqueci", headers=H, json={"documento": doc}).status_code == 200
    token = re.search(r"/redefinir\?token=([\w-]+)", enviados[-1]).group(1)
    assert c.post("/auth/redefinir", headers=H, json={"token": token, "senha": "Nova2026x",
                                                      "confirmacao": "Nova2026x"}).status_code == 200
    assert c.post("/auth/entrar", headers=H, json={"documento": doc, "senha": "Nova2026x"}).status_code == 200
    assert c.post("/api/simulacao/restaurar", headers=H).status_code == 403          # visualizador
    codigo = auth.criar_convite("analista", 1, 1, por="teste")
    r = c.post("/auth/cadastrar", headers=H, json={**dados, "documento": doc_convite, "email": f"conv{doc_convite}@nexo.test",
                                                   "convite": codigo})
    assert r.status_code == 201 and r.get_json()["cargo_nome"] == "Analista"
    assert auth.listar_convites()[0]["situacao"] == "Esgotado"
    uid = auth.buscar_por_documento(doc)["id"]
    auth.alterar_usuario(uid, cargo="analista", por="teste")
    assert c.post("/api/transacoes", headers=H, json={"de": "C001", "para": "C030", "valor": "1000",
                                                      "data": "2026-09-15", "hora": "10:30"}).status_code == 201
    assert c.post("/api/simulacao/restaurar", headers=H).status_code == 200
    eventos = {e["evento"] for e in auth.listar_auditoria()}
    assert {"cadastro", "email_confirmado", "login_email_pendente", "login_falhou", "recuperacao_solicitada",
            "senha_redefinida", "convite_criado", "login"} <= eventos
    print("TESTES OK: MySQL — migração, dados idênticos ao CSV, login, cadastro com confirmação, recuperação, convites, cargos e auditoria.")
finally:
    conexao = db.conectar_mysql(com_banco=False)
    with conexao.cursor() as cur:
        cur.execute("DROP DATABASE IF EXISTS nexo_teste")
    conexao.close()
    print("Banco temporário 'nexo_teste' removido.")
