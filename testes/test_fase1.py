"""Testes da Fase 1: página institucional, login por e-mail, sessões e "Entrar com Google".

Executar (na raiz do projeto): python -m testes.test_fase1
Usa CSV + SQLite temporários e simula o Google (nenhum pedido sai para a internet).
"""
import os
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

os.environ["NEXO_BANCO"] = "local"
for _chave in [k for k in os.environ if k.startswith(("DB_", "SMTP_", "APP_URL", "GOOGLE_"))]:
    del os.environ[_chave]

from banco import conexao as db  # noqa: E402

db.SQLITE = Path(tempfile.mkdtemp()) / "fase1.db"

from app import auth, envio_email, google, servidor  # noqa: E402
from banco import migracoes  # noqa: E402
from nucleo import configuracao  # noqa: E402

H = {"X-Requested-With": "NEXO"}
envio_email.enviar = lambda *a, **k: None
envio_email.configurado = lambda: True
INVALIDO = auth.MENSAGEM_LOGIN_INVALIDO


def cliente():
    servidor._tentativas_ip.clear()
    return servidor.app.test_client()


def entrar(c, login, senha):
    return c.post("/auth/entrar", headers=H, json={"login": login, "senha": senha})


auth.iniciar_banco()
ADM = auth.cadastrar("52998224725", "Ana Admin", "Ana@Empresa.com.br", "11912345678", "Senha123", "Senha123",
                     cargo="administrador", email_confirmado=True)

# ------------------------------------------------------------------ 1. migração 4
assert 4 in migracoes.versoes_aplicadas() and migracoes.VERSAO_ATUAL >= 4
linha = auth.buscar_por_id(ADM["id"])
assert auth.versao_sessao(linha) == 0
print("ok — migração 4 (versão da sessão e identidades externas)")

# ------------------------------------------------------------------ 2. páginas: institucional pública, sistema em /app
c = cliente()
r = c.get("/")
html = r.get_data(as_text=True)
assert r.status_code == 200 and "Enxergue a estrutura" in html and "formAcesso" in html
assert "Relevância estrutural não é acusação" in html and 'id="faq"' in html
assert ">40<" in html and ">160<" in html                              # números reais da base
assert "/auth/google" not in html                                      # Google não configurado: sem botão
assert c.get("/app").status_code == 302 and "/login" in c.get("/app").headers["Location"]
assert c.get("/auth/google").status_code == 404
print("ok — página institucional pública e sistema protegido em /app")

# ------------------------------------------------------------------ 3. login por e-mail OU CPF/CNPJ
c = cliente()
assert entrar(c, "ana@empresa.com.br", "Senha123").status_code == 200      # e-mail (sem diferenciar maiúsculas)
assert c.get("/app").status_code == 200
assert "Abrir o NEXO" in c.get("/").get_data(as_text=True)                 # página inicial reconhece quem entrou
assert c.get("/login").status_code == 302                                 # já logado → sistema
c = cliente()
assert entrar(c, "  ANA@empresa.com.br ", "Senha123").status_code == 200
c = cliente()
assert entrar(c, "529.982.247-25", "Senha123").status_code == 200          # CPF continua valendo
assert c.post("/auth/entrar", headers=H, json={"documento": "52998224725", "senha": "Senha123"}).status_code == 200
# mesma mensagem para e-mail inexistente, CPF inexistente, texto qualquer e senha errada
for login, senha in (("ninguem@x.com", "Senha123"), ("11144477735", "Senha123"), ("abc", "Senha123"),
                     ("ana@empresa.com.br", "Errada123")):
    r = entrar(cliente(), login, senha)
    assert r.status_code == 401 and r.get_json()["erro"] == INVALIDO, (login, r.get_json())
# bloqueio por tentativas vale também para quem tenta pelo e-mail
for _ in range(auth.MAX_TENTATIVAS):
    entrar(cliente(), "ana@empresa.com.br", "Errada123")
assert entrar(cliente(), "ana@empresa.com.br", "Senha123").get_json()["erro"] == INVALIDO
with db.conectar() as cx:
    cx.execute("UPDATE usuarios SET bloqueado_ate = NULL, tentativas_falhas = 0")
# "esqueci a senha" pelo e-mail
enviados = []
envio_email.enviar_recuperacao = lambda destino, *a: enviados.append(destino)
r = cliente().post("/auth/esqueci", headers=H, json={"login": "ana@empresa.com.br"})
assert r.status_code == 200 and enviados == ["ana@empresa.com.br"]
r2 = cliente().post("/auth/esqueci", headers=H, json={"login": "ninguem@x.com"})
assert r2.get_json() == r.get_json()                                       # mesma resposta: não revela cadastro
print("ok — login por e-mail ou CPF/CNPJ, mensagem única, bloqueio e recuperação por e-mail")

# ------------------------------------------------------------------ 4. sessões: trocar a senha desconecta os outros
pc1, pc2 = cliente(), servidor.app.test_client()
assert entrar(pc1, "ana@empresa.com.br", "Senha123").status_code == 200
assert entrar(pc2, "52998224725", "Senha123").status_code == 200
r = pc1.post("/auth/alterar-senha", headers=H, json={"atual": "Errada1", "nova": "Nova12345", "confirmacao": "Nova12345"})
assert r.status_code == 400 and "atual" in r.get_json()["erro"]
r = pc1.post("/auth/alterar-senha", headers=H, json={"atual": "Senha123", "nova": "curta", "confirmacao": "curta"})
assert r.status_code == 400
r = pc1.post("/auth/alterar-senha", headers=H, json={"atual": "Senha123", "nova": "Nova12345", "confirmacao": "Nova12345"})
assert r.status_code == 200
assert pc1.get("/api/resultados").status_code == 200                       # quem trocou continua
assert pc2.get("/api/resultados").status_code == 401                       # o outro computador saiu
assert entrar(cliente(), "ana@empresa.com.br", "Senha123").status_code == 401
assert entrar(pc2, "ana@empresa.com.br", "Nova12345").status_code == 200
# "desconectar outros computadores" sem trocar a senha
assert pc1.post("/auth/encerrar-sessoes", headers=H).status_code == 200
assert pc1.get("/auth/eu").status_code == 200 and pc2.get("/auth/eu").status_code == 401
# redefinir pelo link e a troca manual (CRIAR_ADMIN) também desconectam
entrar(pc2, "ana@empresa.com.br", "Nova12345")
auth.definir_senha_manual(ADM["id"], "Outra1234", "Outra1234", por="teste")
assert pc1.get("/auth/eu").status_code == 401 and pc2.get("/auth/eu").status_code == 401
eventos = {l["evento"] for l in auth.listar_auditoria()}
assert {"senha_alterada", "sessoes_encerradas", "senha_alteracao_falhou"} <= eventos
print("ok — trocar a senha encerra as outras sessões; desconectar outros computadores")

# ------------------------------------------------------------------ 5. Entrar com Google (simulado)
os.environ.update(GOOGLE_CLIENT_ID="cliente-teste.apps.googleusercontent.com", GOOGLE_CLIENT_SECRET="segredo")
assert google.configurado()
assert "/auth/google" in cliente().get("/").get_data(as_text=True)
assert "/auth/google" in cliente().get("/login").get_data(as_text=True)

conta_google = {}


def simular_google(codigo, verificador, url_retorno):
    """No lugar do pedido real ao Google: confere o PKCE e devolve o id_token decodificado."""
    assert codigo == "codigo-ok" and len(verificador) > 40 and url_retorno.endswith("/auth/google/retorno")
    return {"iss": "https://accounts.google.com", "aud": configuracao.obter("GOOGLE_CLIENT_ID"),
            "exp": time.time() + 300, "email_verified": True, **conta_google}


google.trocar_codigo = simular_google


def login_google(c, **conta):
    """Faz a ida ao Google e a volta. Retorna a resposta do retorno."""
    conta_google.clear()
    conta_google.update(conta)
    ida = c.get("/auth/google")
    assert ida.status_code == 302 and ida.headers["Location"].startswith(google.URL_AUTORIZACAO)
    p = parse_qs(urlparse(ida.headers["Location"]).query)
    assert p["code_challenge_method"] == ["S256"] and p["scope"] == ["openid email profile"]
    conta_google.setdefault("nonce", p["nonce"][0])
    return c.get(f"/auth/google/retorno?state={p['state'][0]}&code=codigo-ok")


# 5.1 e-mail de um cadastro confirmado → vincula e entra
c = cliente()
r = login_google(c, sub="g-111", email="ana@empresa.com.br", name="Ana")
assert r.status_code == 302 and r.headers["Location"].endswith("/app"), r.headers.get("Location")
assert c.get("/api/resultados").status_code == 200
assert auth.buscar_identidade("google", "g-111")["usuario_id"] == ADM["id"]
# na segunda vez entra pelo vínculo, mesmo se o e-mail do Google mudar
c = cliente()
assert login_google(c, sub="g-111", email="ana.nova@gmail.com").headers["Location"].endswith("/app")

# 5.2 state errado, nonce errado, e-mail não verificado, cancelado → volta ao login com o motivo
c = cliente()
c.get("/auth/google")
r = c.get("/auth/google/retorno?state=forjado&code=codigo-ok")
assert r.status_code == 302 and "/login?erro=" in r.headers["Location"] and c.get("/auth/eu").status_code == 401
r = login_google(cliente(), sub="g-111", email="ana@empresa.com.br", nonce="outro")
assert "/login?erro=" in r.headers["Location"]
r = login_google(cliente(), sub="g-222", email="x@y.com", email_verified=False)
assert "/login?erro=" in r.headers["Location"]
c = cliente()
c.get("/auth/google")
assert "/login?erro=" in c.get("/auth/google/retorno?error=access_denied").headers["Location"]
# sem pedido iniciado (link antigo ou aberto em outro navegador)
assert "/login?erro=" in cliente().get("/auth/google/retorno?state=x&code=codigo-ok").headers["Location"]

# 5.3 cadastro com o e-mail ainda NÃO confirmado → não vincula (evita tomada de conta)
auth.cadastrar("11144477735", "Bia Pendente", "bia@empresa.com.br", "11955554444", "Senha123", "Senha123")
r = login_google(cliente(), sub="g-333", email="bia@empresa.com.br")
assert "/login?erro=" in r.headers["Location"] and "confirmado" in r.headers["Location"]
assert auth.buscar_identidade("google", "g-333") is None

# 5.4 pessoa nova → completa o cadastro (CPF e telefone), sem senha, e-mail já confirmado
c = cliente()
r = login_google(c, sub="g-444", email="caio@gmail.com", name="Caio Novo")
assert r.headers["Location"].endswith("/cadastro?google=1")
assert c.get("/auth/google/pendente").get_json() == {"email": "caio@gmail.com", "nome": "Caio Novo"}
r = c.post("/auth/google/concluir", headers=H, json={"documento": "123", "telefone": "11912345678"})
assert r.status_code == 400                                              # CPF inválido
r = c.post("/auth/google/concluir", headers=H, json={"documento": "390.533.447-05", "telefone": "(11) 98888-7777"})
assert r.status_code == 201 and r.get_json()["usuario"]["cargo"] == "visualizador"
assert r.get_json()["usuario"]["email_confirmado"] is True
assert c.get("/api/resultados").status_code == 200
assert c.post("/auth/google/concluir", headers=H, json={}).status_code == 400   # não dá para repetir
assert entrar(cliente(), "caio@gmail.com", "qualquer1").status_code == 401       # não há senha conhecida
assert login_google(cliente(), sub="g-444", email="caio@gmail.com").headers["Location"].endswith("/app")
# sem passar pelo Google, não há cadastro pendente
assert cliente().post("/auth/google/concluir", headers=H, json={"documento": "39053344705"}).status_code == 400

# 5.5 usuário desativado não entra pelo Google
caio = auth.buscar_por_email("caio@gmail.com")
auth.alterar_usuario(caio["id"], ativo=False, por="teste")
assert "/login?erro=" in login_google(cliente(), sub="g-444", email="caio@gmail.com").headers["Location"]

# 5.6 restrição de domínio
os.environ["GOOGLE_DOMINIOS"] = "empresa.com.br"
c = cliente()
ida = c.get("/auth/google")
assert "hd=empresa.com.br" in ida.headers["Location"]
r = login_google(cliente(), sub="g-555", email="fora@gmail.com")
assert "/login?erro=" in r.headers["Location"] and "empresa.com.br" in r.headers["Location"]
del os.environ["GOOGLE_DOMINIOS"]

eventos = {l["evento"] for l in auth.listar_auditoria()}
assert {"login_google", "google_vinculado", "cadastro_google", "login_google_falhou", "login_google_negado"} <= eventos
print("ok — Google: vínculo, segunda entrada, state/nonce/PKCE, e-mail não verificado, conta pendente, "
      "cadastro novo, usuário desativado e domínio")

# ------------------------------------------------------------------ 6. senha do Google nunca aparece para o navegador
for nome in ("inicio.html", "login.html"):
    assert "segredo" not in cliente().get("/" if nome == "inicio.html" else "/login").get_data(as_text=True)
# ------------------------------------------------------------------ 7. CONFIGURAR com config.ini.bak já existente (erro no Windows)
from app import configurar  # noqa: E402

pasta = Path(tempfile.mkdtemp())
for n in range(3):
    (pasta / "config.ini").write_text(f"[app]\nurl_base = http://127.0.0.1:5000\n; rodada {n}\n")
    destino = configurar.guardar_config_antigo(pasta / "config.ini")
    assert not (pasta / "config.ini").exists() and f"rodada {n}" in destino.read_text()
assert sorted(a.name for a in pasta.iterdir()) == ["config.ini.bak", "config.ini.bak2", "config.ini.bak3"]
print("ok — CONFIGURAR guarda o config.ini antigo sem apagar cópias anteriores")
print("TESTES OK: Fase 1 — página institucional, login por e-mail, sessões e Entrar com Google.")
