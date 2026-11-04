"""Testes do login, cadastro, confirmação de e-mail, recuperação, convites e permissões.

Executar (na raiz do projeto): python -m testes.test_login
Usa um banco temporário (não toca em banco/dados/nexo.db nem no MySQL) e captura os
e-mails em vez de enviá-los pelo SMTP.
"""
import os
import re
import tempfile
from pathlib import Path

os.environ['NEXO_BANCO'] = 'local'   # testes usam CSV + SQLite temporário
from banco import conexao as db

db.SQLITE = Path(tempfile.mkdtemp()) / "teste.db"
from app import auth  # noqa: E402
from app import envio_email  # noqa: E402
from app import servidor  # noqa: E402  (importa depois de trocar o banco)

auth.iniciar_banco()
H = {"X-Requested-With": "NEXO"}
enviados = []
envio_email.enviar = lambda destino, assunto, texto, html=None: enviados.append((destino, assunto, texto))
envio_email.configurado = lambda: True


def gerar_cpf(base):
    d = [int(x) for x in base]
    for _ in range(2):
        r = sum(v * p for v, p in zip(d, range(len(d) + 1, 1, -1))) % 11
        d.append(0 if r < 2 else 11 - r)
    return "".join(map(str, d))


def link(tipo):
    """Último link enviado por e-mail do tipo pedido ('confirmar' ou 'redefinir')."""
    for _, _, texto in reversed(enviados):
        achado = re.search(rf"/{tipo}\?token=([\w-]+)", texto)
        if achado:
            return achado.group(1)
    raise AssertionError(f"nenhum link /{tipo} enviado")


CPF_ADMIN, CPF_ANA, CPF_VIS, CPF_CONV = (gerar_cpf("529982247"), gerar_cpf("111444777"),
                                         gerar_cpf("123456789"), gerar_cpf("987654321"))
CNPJ = "11222333000181"
INVALIDO = auth.MENSAGEM_LOGIN_INVALIDO

# ---- validações de documento e telefone
assert auth.cpf_valido("52998224725") and not auth.cpf_valido("52998224724")
assert auth.cnpj_valido(CNPJ) and not auth.cnpj_valido("11222333000180")
assert auth.validar_telefone("(11) 91234-5678") == "11912345678"
assert auth.validar_telefone("+55 11 3456-7890") == "1134567890"
for ruim in ("1234", "(00) 91234-5678", "(11) 81234-5678"):  # curto, DDD 00, celular sem 9
    try:
        auth.validar_telefone(ruim)
        raise AssertionError(f"telefone aceito: {ruim}")
    except auth.ErroAuth:
        pass

admin = auth.cadastrar(CPF_ADMIN, "Admin Teste", "admin@nexo.test", "11912345678", "Senha123", "Senha123",
                       cargo="administrador", email_confirmado=True)


def cliente():
    servidor._tentativas_ip.clear()   # cada cenário começa sem o limite por IP
    return servidor.app.test_client()


# ---- página protegida, CSRF e rota antiga que revelava cadastros
c = cliente()
assert c.get("/").status_code == 302 and "/login" in c.get("/").headers["Location"]
assert c.get("/api/resultados").status_code == 401
assert c.post("/auth/entrar", json={"documento": CPF_ADMIN, "senha": "Senha123"}).status_code == 400
assert c.post("/auth/verificar", headers=H, json={"documento": CPF_ADMIN}).status_code in (404, 405)
for pagina in ("/login", "/cadastro", "/redefinir", "/confirmar"):
    assert c.get(pagina).status_code == 200, pagina

# ---- 1. login com MENSAGEM ÚNICA: não revela se o CPF existe
inexistente = c.post("/auth/entrar", headers=H, json={"documento": CNPJ, "senha": "Qualquer1"})
senha_errada = c.post("/auth/entrar", headers=H, json={"documento": CPF_ADMIN, "senha": "Errada123"})
formato_ruim = c.post("/auth/entrar", headers=H, json={"documento": "123", "senha": "Errada123"})
assert inexistente.get_json() == senha_errada.get_json() == formato_ruim.get_json() == {"erro": INVALIDO}
assert inexistente.status_code == senha_errada.status_code == 401
assert c.post("/auth/entrar", headers=H, json={"documento": CPF_ADMIN, "senha": "Senha123"}).status_code == 200
c.post("/auth/sair", headers=H)

# ---- 2. cadastro: telefone obrigatório, sem login automático, e-mail de confirmação
base = {"documento": CNPJ, "nome": "Empresa X Ltda", "email": "contato@empresa.test",
        "senha": "Empresa2026", "confirmacao": "Empresa2026"}
r = c.post("/auth/cadastrar", headers=H, json=base)
assert r.status_code == 400 and "telefone" in r.get_json()["erro"]
r = c.post("/auth/cadastrar", headers=H, json={**base, "telefone": "(11) 3456-7890", "cargo": "administrador"})
assert r.status_code == 201, r.get_json()
dados = r.get_json()
assert dados["enviado"] is True and dados["cargo_nome"] == "Visualizador"   # "cargo" do pedido é ignorado
assert dados["email"] == "co*****@empresa.test"
assert enviados[-1][0] == "contato@empresa.test" and "Confirme" in enviados[-1][1]
assert c.get("/").status_code == 302                                         # não entrou sozinho
dup = c.post("/auth/cadastrar", headers=H, json={**base, "telefone": "11912345678", "email": "outro@x.com"})
assert dup.status_code == 400 and "Esqueci minha senha" in dup.get_json()["erro"]

# ---- 3. e-mail pendente: senha certa → aviso; senha errada → mensagem única
r = c.post("/auth/entrar", headers=H, json={"documento": CNPJ, "senha": "Empresa2026"})
assert r.status_code == 403 and r.get_json()["codigo"] == "email_nao_confirmado"
assert c.post("/auth/entrar", headers=H, json={"documento": CNPJ, "senha": "Errada999"}).get_json() == {"erro": INVALIDO}
assert c.post("/auth/reenviar-confirmacao", headers=H,
              json={"documento": CNPJ, "senha": "Errada999"}).get_json() == {"erro": INVALIDO}
assert c.post("/auth/reenviar-confirmacao", headers=H,
              json={"documento": CNPJ, "senha": "Empresa2026"}).status_code == 429   # 1 por minuto
token_conf = link("confirmar")
assert c.post("/auth/confirmar", headers=H, json={"token": "falso"}).status_code == 400
assert c.post("/auth/confirmar", headers=H, json={"token": token_conf}).get_json()["nome"] == "Empresa X Ltda"
assert c.post("/auth/confirmar", headers=H, json={"token": token_conf}).status_code == 400   # uso único
assert c.post("/auth/entrar", headers=H, json={"documento": CNPJ, "senha": "Empresa2026"}).status_code == 200
assert c.get("/api/exportar").status_code == 403                             # visualizador
c.post("/auth/sair", headers=H)

# ---- 4. bloqueio após 5 erros, sempre com a mesma mensagem
auth.cadastrar(CPF_VIS, "Visu Bloqueio", "vis@nexo.test", "11987654321", "Senha123", "Senha123", email_confirmado=True)
for _ in range(5):
    assert c.post("/auth/entrar", headers=H, json={"documento": CPF_VIS, "senha": "errada1"}).get_json() == {"erro": INVALIDO}
r = c.post("/auth/entrar", headers=H, json={"documento": CPF_VIS, "senha": "Senha123"})
assert r.status_code == 401 and r.get_json() == {"erro": INVALIDO}          # bloqueado, mesmo com a senha certa

# ---- 5. esqueci a senha: resposta idêntica exista ou não o cadastro
r_existe = c.post("/auth/esqueci", headers=H, json={"documento": CPF_VIS})
qtd = len(enviados)
r_nao = c.post("/auth/esqueci", headers=H, json={"documento": gerar_cpf("222333444")})
r_rapido = c.post("/auth/esqueci", headers=H, json={"documento": CPF_VIS})    # dentro de 1 min: não reenvia
assert r_existe.get_json() == r_nao.get_json() == r_rapido.get_json() and r_existe.status_code == 200
assert len(enviados) == qtd                                                   # nada enviado nos dois últimos
token = link("redefinir")
assert c.get(f"/auth/token?token={token}").get_json()["nome"] == "Visu Bloqueio"
assert c.post("/auth/redefinir", headers=H, json={"token": token, "senha": "NovaSenha9",
                                                  "confirmacao": "Outra999"}).status_code == 400
assert c.post("/auth/redefinir", headers=H, json={"token": token, "senha": "NovaSenha9",
                                                  "confirmacao": "NovaSenha9"}).status_code == 200
assert c.post("/auth/redefinir", headers=H, json={"token": token, "senha": "NovaSenha9",
                                                  "confirmacao": "NovaSenha9"}).status_code == 400
assert c.post("/auth/entrar", headers=H, json={"documento": CPF_VIS, "senha": "NovaSenha9"}).status_code == 200
assert c.post("/auth/confirmar", headers=H, json={"token": token}).status_code == 400   # tipos não se misturam
c.post("/auth/sair", headers=H)

# ---- 6. e-mail não configurado: recuperação avisa (sem revelar nada)
envio_email.configurado = lambda: False
assert c.post("/auth/esqueci", headers=H, json={"documento": CPF_VIS}).status_code == 503
envio_email.configurado = lambda: True

# ---- 7. códigos de convite
adm = cliente()
assert adm.post("/auth/entrar", headers=H, json={"documento": CPF_ADMIN, "senha": "Senha123"}).status_code == 200
codigo = adm.post("/api/convites", headers=H, json={"cargo": "analista", "dias": 7, "max_usos": 1}).get_json()["codigo"]
assert re.fullmatch(r"NEXO-[A-Z2-9]{4}-[A-Z2-9]{4}", codigo)
assert adm.post("/api/convites", headers=H, json={"cargo": "analista", "dias": 99, "max_usos": 1}).status_code == 400
convidado = {"documento": CPF_CONV, "nome": "Carla Convidada", "email": "carla@nexo.test",
             "telefone": "21998765432", "senha": "Carla2026", "confirmacao": "Carla2026"}
r = c.post("/auth/cadastrar", headers=H, json={**convidado, "convite": "NEXO-AAAA-BBBB"})
assert r.status_code == 400 and "convite" in r.get_json()["erro"]
assert auth.buscar_por_documento(CPF_CONV) is None                            # convite errado não cria usuário
r = c.post("/auth/cadastrar", headers=H, json={**convidado, "convite": codigo.lower().replace("-", " ")})
assert r.status_code == 201 and r.get_json()["cargo_nome"] == "Analista"
r = c.post("/auth/cadastrar", headers=H, json={**convidado, "documento": gerar_cpf("555666777"),
                                               "email": "x@nexo.test", "convite": codigo})
assert r.status_code == 400                                                   # esgotado (1 uso)
lista = adm.get("/api/convites").get_json()["convites"]
assert lista[0]["situacao"] == "Esgotado" and lista[0]["codigo"].endswith("-****")
codigo2 = adm.post("/api/convites", headers=H, json={"cargo": "auditor", "dias": 1, "max_usos": 3}).get_json()["codigo"]
id2 = adm.get("/api/convites").get_json()["convites"][0]["id"]
assert adm.delete(f"/api/convites/{id2}", headers=H).status_code == 200
r = c.post("/auth/cadastrar", headers=H, json={**convidado, "documento": gerar_cpf("555666777"),
                                               "email": "y@nexo.test", "convite": codigo2})
assert r.status_code == 400                                                   # revogado

# ---- 8. administrador: trocar e-mail (fica pendente), confirmar manualmente, cargos
ana = auth.cadastrar(CPF_ANA, "Ana Analista", "ana@nexo.test", "11955554444", "Senha123", "Senha123",
                     email_confirmado=True)
r = adm.patch(f"/api/usuarios/{ana['id']}", headers=H, json={"email": "ana.nova@nexo.test", "telefone": "11955550000"})
assert r.status_code == 200 and r.get_json()["confirmacao_enviada"] is True
assert r.get_json()["usuario"]["email_confirmado"] is False and r.get_json()["usuario"]["telefone"] == "(11) 95555-0000"
assert enviados[-1][0] == "ana.nova@nexo.test"
assert adm.patch(f"/api/usuarios/{ana['id']}", headers=H, json={"email": "admin@nexo.test"}).status_code == 400
u = cliente()
assert u.post("/auth/entrar", headers=H, json={"documento": CPF_ANA, "senha": "Senha123"}).status_code == 403
assert adm.patch(f"/api/usuarios/{ana['id']}", headers=H, json={"confirmar_email": True}).get_json()["usuario"]["email_confirmado"]
assert u.post("/auth/entrar", headers=H, json={"documento": CPF_ANA, "senha": "Senha123"}).status_code == 200
assert u.post("/api/simulacao/restaurar", headers=H).status_code == 403
assert adm.patch(f"/api/usuarios/{ana['id']}", headers=H, json={"cargo": "analista"}).status_code == 200
assert u.post("/api/simulacao/restaurar", headers=H).status_code == 200      # vale sem novo login
assert u.get("/api/convites").status_code == 403                             # só administrador
assert adm.patch(f"/api/usuarios/{ana['id']}", headers=H, json={"ativo": False}).status_code == 200
assert u.get("/api/resultados").status_code == 401
assert adm.patch(f"/api/usuarios/{admin['id']}", headers=H, json={"cargo": "analista"}).status_code == 400

# ---- 9. limite por IP (robôs)
servidor._tentativas_ip.clear()
maximo = servidor.LIMITES["entrar"][0]
for _ in range(maximo):
    c.post("/auth/entrar", headers=H, json={"documento": CNPJ, "senha": "x"})
assert c.post("/auth/entrar", headers=H, json={"documento": CPF_ADMIN, "senha": "Senha123"}).status_code == 429

# ---- 10. auditoria e senhas
eventos = {e["evento"] for e in adm.get("/api/auditoria").get_json()["eventos"]}
assert {"login", "login_falhou", "login_bloqueado", "login_email_pendente", "cadastro", "email_confirmado",
        "email_confirmado_manual", "recuperacao_solicitada", "senha_redefinida", "contato_alterado",
        "convite_criado", "convite_revogado", "usuario_alterado", "acesso_negado", "limite_ip"} <= eventos, eventos
with auth.conectar() as con:
    assert all(not l["senha_hash"].startswith("Senha") for l in con.execute("SELECT senha_hash FROM usuarios").fetchall())
    assert all(len(l["codigo_hash"]) == 64 for l in con.execute("SELECT codigo_hash FROM convites").fetchall())

print("TESTES OK: login com mensagem única, cadastro com telefone, confirmação de e-mail, recuperação, "
      "convites, contato pelo admin, bloqueio, limite por IP e auditoria.")
