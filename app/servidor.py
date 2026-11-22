"""NEXO — servidor web (Flask): páginas, login e API da análise.

Executar (na raiz do projeto): python -m app  →  abrir http://127.0.0.1:5000

Camadas: rotas (este arquivo) → app/analises.py (cache e base) → nucleo/analise.py
(matemática) e banco/repositorio.py (dados). Usuários e cargos: app/auth.py.
Cada usuário tem a própria simulação, guardada no banco; a base oficial nunca é alterada.
"""

import gzip
import json
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from functools import wraps
from urllib.parse import quote as url_quote

from flask import (Flask, Response, jsonify, redirect, render_template, request,
                   session, url_for)

from app import analises, auth, casos, envio_email, google, preferencias, simulacao
from banco import conexao as db
from banco import migracoes, repositorio
from nucleo import analise, configuracao


def chave_secreta():
    """Chave das sessões: gerada uma vez e guardada fora do código (fora do GitHub)."""
    arquivo = configuracao.PASTA_DADOS / ".chave_secreta"
    if not arquivo.exists():
        arquivo.write_text(secrets.token_hex(32))
    return arquivo.read_text().strip()


def url_base():
    return (configuracao.obter("APP_URL_BASE") or request.host_url).rstrip("/")


app = Flask(__name__)
app.config.update(SECRET_KEY=chave_secreta(), SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
                  # o navegador revalida os arquivos (resposta 304, sem baixar de novo se não mudaram):
                  # uma versão nova do NEXO aparece sem precisar de Ctrl+F5
                  SEND_FILE_MAX_AGE_DEFAULT=0,
                  # importação de bases (Fase 6): arquivos de até 2 MB, mais a margem do envio
                  MAX_CONTENT_LENGTH=3 * 1024 * 1024)


@app.errorhandler(413)
def arquivo_grande(_erro):
    return jsonify({"erro": "Arquivo grande demais: o limite é 2 MB."}), 413
trava = threading.Lock()

try:
    auth.iniciar_banco()
    analises.obter_base()
    repositorio.limpar_analises_antigas()
except (db.ErroBanco, ValueError, migracoes.ErroVersao) as erro_inicial:
    raise SystemExit(f"\n[ERRO] Não foi possível iniciar com a base ({db.descricao()}): {erro_inicial}\n"
                     "Rode: scripts\\DIAGNOSTICO.bat") from erro_inicial
FONTE_DADOS = db.descricao()


# ---------------------------------------------------------------- compressão

COMPACTAVEIS = {"application/json", "text/html", "text/css", "application/javascript", "text/javascript",
                "image/svg+xml"}


@app.after_request
def compactar(resposta):
    """gzip nas respostas de texto: a análise com 300 contas cai de ~2,4 MB para ~55 KB."""
    if ("gzip" not in request.headers.get("Accept-Encoding", "") or resposta.status_code != 200
            or resposta.mimetype not in COMPACTAVEIS or "Content-Encoding" in resposta.headers):
        return resposta
    resposta.direct_passthrough = False  # arquivos estáticos chegam como fluxo
    dados = resposta.get_data()
    if len(dados) < 1024:
        return resposta
    resposta.set_data(gzip.compress(dados, compresslevel=6))
    resposta.headers["Content-Encoding"] = "gzip"
    resposta.headers["Content-Length"] = str(len(resposta.get_data()))
    resposta.vary.add("Accept-Encoding")
    if resposta.headers.get("ETag") and not resposta.headers["ETag"].startswith("W/"):
        resposta.headers["ETag"] = "W/" + resposta.headers["ETag"]  # o conteúdo enviado não é byte a byte o original
    return resposta


# ---------------------------------------------------------------- análise

def resultados(usuario, recorte=0, com_matrizes=False):
    """Resposta da análise para o usuário: base + a simulação dele, no recorte pedido."""
    simuladas = repositorio.listar_simuladas(usuario["id"])
    calculado, info = analises.calcular(recorte, simuladas)
    ids_simulados = {s["id_transacao"] for s in simuladas}
    # cópias rasas: o resultado em cache é compartilhado entre usuários e não pode ser alterado
    dados = {k: v for k, v in calculado.items() if com_matrizes or k != "matrizes"}
    dados["transacoes"] = [{**t, "simulada": t["id"] in ids_simulados} for t in calculado["transacoes"]]
    dados["analise"] = {k: info[k] for k in ("id", "assinatura", "versao_motor", "duracao_ms", "origem")}
    dados["bancario"] = simulacao.dados_bancarios()   # instituição fictícia, tipo de conta e chave PIX
    dados["base"] = analises.info_base()               # nome e origem da base em uso (Fase 6)
    dados["simulacao"] = {
        "periodo_dias": info["recorte"]["dias"], "data_referencia": info["data_referencia"],
        "recorte": info["recorte"], "datas_base": info["datas_base"],
        "transacoes_simuladas": len(simuladas),
        "lista_simuladas": simuladas,
        "total_base_original": info["total_base_original"],
        "tipos_transacao": info["tipos_transacao"],
        "pesos": analise.PESOS,
        "fonte_dados": FONTE_DADOS, "mysql": db.usando_mysql(),
        "limiares": {"analise": analise.LIMIAR_ANALISE, "alta": analise.LIMIAR_ALTA},
    }
    return dados


def recorte_param():
    """Recorte pedido na URL: ?dias=N ou ?inicio=&fim=&tipos=PIX,TED&valor_min=&valor_max=."""
    a = request.args
    try:
        dias = max(0, int(a.get("dias", 0) or 0))
    except ValueError:
        dias = 0
    tipos = [x.strip() for x in a.get("tipos", "").split(",") if x.strip()]
    return analises.normalizar_recorte({"dias": dias, "inicio": a.get("inicio"), "fim": a.get("fim"), "tipos": tipos,
                                        "valor_min": a.get("valor_min"), "valor_max": a.get("valor_max")})


def com_recorte(funcao):
    """Recorte inválido ou sem transações vira 400 com a mensagem pronta para a tela."""
    @wraps(funcao)
    def interna(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except ValueError as erro:
            return jsonify({"erro": str(erro)}), 400
    return interna


def resumo_contas(dados):
    return {c["id"]: {"score": c["score"], "status": c["status"], "ranking": c["ranking"],
                      "com": c["com"], "degree": c["degree"]} for c in dados["contas"]}


# ---------------------------------------------------------------- sessão e permissões

def usuario_atual():
    """Relê o usuário do banco a cada pedido: mudança de cargo, desativação ou troca de
    senha (versão da sessão) vale na hora."""
    uid = session.get("uid")
    linha = auth.buscar_por_id(uid) if uid else None
    if linha is None:
        return None
    if not linha["ativo"] or session.get("v", 0) != auth.versao_sessao(linha):
        session.clear()
        return None
    return auth.publico(linha)


def exige(permissao):
    def decorador(funcao):
        @wraps(funcao)
        def interna(*args, **kwargs):
            usuario = usuario_atual()
            if usuario is None:
                return jsonify({"erro": "Sessão expirada. Faça login novamente."}), 401
            if not auth.tem_permissao(usuario, permissao):
                auth.registrar("acesso_negado", None, f"{usuario['nome']} → {request.path}", request.remote_addr)
                return jsonify({"erro": f"O cargo {usuario['cargo_nome']} não tem permissão para esta ação."}), 403
            return funcao(*args, **kwargs)
        return interna
    return decorador


@app.before_request
def protecao_csrf():
    # Pedidos que alteram dados precisam deste cabeçalho, que só o nosso JavaScript envia.
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("X-Requested-With") != "NEXO":
        return jsonify({"erro": "Requisição inválida."}), 400


def iniciar_sessao(usuario):
    session.clear()
    session.permanent = True
    session["uid"] = usuario["id"]
    session["v"] = auth.versao_sessao(auth.buscar_por_id(usuario["id"]))


def identificador(dados):
    """E-mail ou CPF/CNPJ informado ("login"; "documento" ainda aceito por compatibilidade)."""
    return dados.get("login") or dados.get("documento")


def corpo():
    return request.get_json(silent=True) or {}


def erro_auth(erro, status=400):
    return jsonify({"erro": str(erro)}), status


# ---------------------------------------------------------------- limite por IP

# Janela deslizante em memória: freia robôs testando senhas ou criando contas em massa.
# (bloqueio por conta continua em auth.py: 5 erros → 15 min)
LIMITES = {"entrar": (30, 600), "cadastrar": (10, 3600), "esqueci": (10, 900)}
_tentativas_ip = defaultdict(deque)
_trava_limite = threading.Lock()


def excedeu_limite(acao):
    maximo, janela = LIMITES[acao]
    chave, instante = (acao, request.remote_addr), time.monotonic()
    with _trava_limite:
        fila = _tentativas_ip[chave]
        while fila and fila[0] <= instante - janela:
            fila.popleft()
        if len(fila) >= maximo:
            return True
        fila.append(instante)
    return False


def resposta_limite():
    auth.registrar("limite_ip", None, request.path, request.remote_addr)
    return erro_auth("Muitas tentativas a partir deste computador. Aguarde alguns minutos e tente novamente.", 429)


# ---------------------------------------------------------------- páginas

_resumo_publico = {}


def resumo_publico():
    """Números da base de demonstração para a página inicial (sem dados de contas)."""
    if not _resumo_publico:
        try:
            calculado, _ = analises.calcular(0, [])
            _resumo_publico.update(contas=calculado["dashboard"]["total_contas"],
                                   transacoes=len(calculado["transacoes"]),
                                   comunidades=len({c["com"] for c in calculado["contas"]}))
        except Exception:  # noqa: BLE001 — a página inicial abre mesmo sem a base
            return {}
    return _resumo_publico


@app.get("/")
def inicio():
    """Página institucional pública. Quem já entrou vê o atalho para o sistema."""
    return render_template("inicio.html", usuario=usuario_atual(), google=google.configurado(),
                           resumo=resumo_publico())


@app.get("/app")
def index():
    if usuario_atual() is None:
        return redirect(url_for("pagina_login"))
    return render_template("index.html")


@app.get("/login")
def pagina_login():
    if usuario_atual() is not None:
        return redirect(url_for("index"))
    return render_template("login.html", google=google.configurado())


@app.get("/cadastro")
@app.get("/redefinir")
@app.get("/confirmar")
def pagina_acesso():
    # mesma página de login; o login.js escolhe a etapa pelo endereço
    return render_template("login.html", google=google.configurado())


@app.get("/favicon.ico")
def favicon():
    return "", 204


# ---------------------------------------------------------------- autenticação

def enviar_confirmacao(usuario_id, email, nome):
    """Envia o link de confirmação. Retorna True se o e-mail saiu."""
    try:
        token = auth.criar_token_confirmacao(usuario_id)
        envio_email.enviar_confirmacao(email, nome, f"{url_base()}/confirmar?token={token}",
                                       auth.VALIDADE_CONFIRMACAO_HORAS)
        return True
    except envio_email.ErroEmail as erro:
        auth.registrar("email_falhou", None, f"confirmação para {auth.mascarar_email(email)}: {erro}",
                       request.remote_addr)
        return False


@app.post("/auth/entrar")
def auth_entrar():
    if excedeu_limite("entrar"):
        return resposta_limite()
    dados = corpo()
    try:
        usuario = auth.autenticar(identificador(dados), dados.get("senha"), request.remote_addr)
    except auth.EmailNaoConfirmado as erro:
        return jsonify({"erro": str(erro), "codigo": "email_nao_confirmado"}), 403
    except auth.ErroAuth as erro:
        return erro_auth(erro, 401)
    iniciar_sessao(usuario)
    return jsonify({"usuario": usuario})


@app.post("/auth/cadastrar")
def auth_cadastrar():
    if excedeu_limite("cadastrar"):
        return resposta_limite()
    d = corpo()
    try:
        usuario = auth.cadastrar(d.get("documento"), d.get("nome"), d.get("email"), d.get("telefone"),
                                 d.get("senha", ""), d.get("confirmacao", ""), convite=d.get("convite"),
                                 ip=request.remote_addr)
    except auth.ErroAuth as erro:
        return erro_auth(erro)
    # sem sessão: só entra depois de confirmar o e-mail
    enviado = enviar_confirmacao(usuario["id"], usuario["email"], usuario["nome"])
    return jsonify({"email": auth.mascarar_email(usuario["email"]), "enviado": enviado,
                    "cargo_nome": usuario["cargo_nome"],
                    "validade_horas": auth.VALIDADE_CONFIRMACAO_HORAS}), 201


@app.post("/auth/reenviar-confirmacao")
def auth_reenviar_confirmacao():
    if excedeu_limite("entrar"):
        return resposta_limite()
    d = corpo()
    try:
        linha, token = auth.preparar_reenvio_confirmacao(identificador(d), d.get("senha"), request.remote_addr)
        envio_email.enviar_confirmacao(linha["email"], linha["nome"], f"{url_base()}/confirmar?token={token}",
                                       auth.VALIDADE_CONFIRMACAO_HORAS)
    except auth.ErroAuth as erro:
        return erro_auth(erro, 429 if "Aguarde" in str(erro) else 401)
    except envio_email.ErroEmail as erro:
        auth.registrar("email_falhou", linha["documento"], str(erro), request.remote_addr)
        return erro_auth("Não foi possível enviar o e-mail agora. Peça ao administrador para confirmar seu "
                         "e-mail manualmente.", 503)
    auth.registrar("confirmacao_reenviada", linha["documento"], ip=request.remote_addr)
    return jsonify({"email": auth.mascarar_email(linha["email"])})


@app.post("/auth/confirmar")
def auth_confirmar():
    try:
        usuario = auth.confirmar_email(corpo().get("token"), request.remote_addr)
    except auth.ErroAuth as erro:
        return erro_auth(erro)
    return jsonify({"nome": usuario["nome"]})


@app.post("/auth/esqueci")
def auth_esqueci():
    if excedeu_limite("esqueci"):
        return resposta_limite()
    if not envio_email.configurado():
        return erro_auth("O envio de e-mail ainda não foi configurado. Procure o administrador.", 503)
    linha, token = auth.criar_token_recuperacao(identificador(corpo()))
    if linha is not None:
        try:
            envio_email.enviar_recuperacao(linha["email"], linha["nome"], f"{url_base()}/redefinir?token={token}",
                                           auth.VALIDADE_TOKEN_MINUTOS)
            auth.registrar("recuperacao_solicitada", linha["documento"], ip=request.remote_addr)
        except envio_email.ErroEmail as erro:
            auth.registrar("email_falhou", linha["documento"], str(erro), request.remote_addr)
    # mesma resposta exista ou não o cadastro: não revela quem é usuário
    return jsonify({"mensagem": "Se houver um cadastro ativo com estes dados, enviamos um link para o "
                                f"e-mail cadastrado. Ele vale por {auth.VALIDADE_TOKEN_MINUTOS} minutos e só "
                                "pode ser usado uma vez. Verifique também a caixa de spam."})


@app.get("/auth/token")
def auth_token():
    try:
        usuario = auth.verificar_token(request.args.get("token"))
    except auth.ErroAuth as erro:
        return erro_auth(erro)
    return jsonify({"nome": usuario["nome"], "documento": usuario["documento"]})


@app.post("/auth/redefinir")
def auth_redefinir():
    d = corpo()
    try:
        auth.redefinir_senha(d.get("token"), d.get("senha", ""), d.get("confirmacao", ""), request.remote_addr)
    except auth.ErroAuth as erro:
        return erro_auth(erro)
    session.clear()
    return jsonify({"ok": True})


@app.post("/auth/sair")
def auth_sair():
    usuario = usuario_atual()
    if usuario:
        auth.registrar("logout", None, usuario["nome"], request.remote_addr)
    session.clear()
    return jsonify({"ok": True})


@app.post("/auth/alterar-senha")
@exige("consultar")
def auth_alterar_senha():
    """O próprio usuário troca a senha; as outras sessões dele são encerradas."""
    if excedeu_limite("entrar"):
        return resposta_limite()
    d, usuario = corpo(), usuario_atual()
    try:
        session["v"] = auth.alterar_minha_senha(usuario["id"], d.get("atual", ""), d.get("nova", ""),
                                                d.get("confirmacao", ""), request.remote_addr)
    except auth.ErroAuth as erro:
        return erro_auth(erro)
    return jsonify({"ok": True})


@app.post("/auth/encerrar-sessoes")
@exige("consultar")
def auth_encerrar_sessoes():
    """Desconecta o usuário dos outros computadores e mantém esta sessão."""
    usuario = usuario_atual()
    session["v"] = auth.encerrar_sessoes(usuario["id"], por=usuario["nome"], ip=request.remote_addr)
    return jsonify({"ok": True})


# ---------------------------------------------------------------- entrar com Google

def retorno_google():
    return f"{url_base()}/auth/google/retorno"


@app.get("/auth/google")
def auth_google():
    if not google.configurado():
        return "", 404
    if excedeu_limite("entrar"):
        return redirect("/login?erro=" + url_quote("Muitas tentativas a partir deste computador. Aguarde alguns minutos."))
    destino, pedido = google.iniciar(retorno_google())
    session["google_pedido"] = pedido
    return redirect(destino)


@app.get("/auth/google/retorno")
def auth_google_retorno():
    if not google.configurado():
        return "", 404
    pedido = session.pop("google_pedido", None)
    try:
        conta = google.concluir(request.args, pedido, retorno_google())
        usuario = auth.entrar_externo("google", conta["sujeito"], conta["email"], request.remote_addr)
    except (google.ErroGoogle, auth.ErroAuth) as erro:
        auth.registrar("login_google_falhou", None, str(erro)[:200], request.remote_addr)
        return redirect("/login?erro=" + url_quote(str(erro)))
    if usuario is None:
        # primeira vez: completa o cadastro (CPF/CNPJ e telefone) sem criar senha
        session["google_cadastro"] = {**conta, "criado": int(time.time())}
        return redirect("/cadastro?google=1")
    iniciar_sessao(usuario)
    return redirect(url_for("index"))


def cadastro_google_pendente():
    pendente = session.get("google_cadastro")
    if not pendente or int(time.time()) - pendente["criado"] > google.VALIDADE_PEDIDO_SEGUNDOS:
        session.pop("google_cadastro", None)
        return None
    return pendente


@app.get("/auth/google/pendente")
def auth_google_pendente():
    pendente = cadastro_google_pendente()
    if pendente is None:
        return erro_auth("O tempo para concluir o cadastro com Google acabou. Entre com Google de novo.", 404)
    return jsonify({"email": pendente["email"], "nome": pendente["nome"]})


@app.post("/auth/google/concluir")
def auth_google_concluir():
    if excedeu_limite("cadastrar"):
        return resposta_limite()
    pendente = cadastro_google_pendente()
    if pendente is None:
        return erro_auth("O tempo para concluir o cadastro com Google acabou. Entre com Google de novo.", 400)
    d = corpo()
    try:
        usuario = auth.cadastrar_externo("google", pendente["sujeito"], pendente["email"], d.get("documento"),
                                         d.get("nome") or pendente["nome"], d.get("telefone"),
                                         convite=d.get("convite"), ip=request.remote_addr)
    except auth.ErroAuth as erro:
        return erro_auth(erro)
    session.pop("google_cadastro", None)
    iniciar_sessao(usuario)
    return jsonify({"usuario": usuario}), 201


@app.get("/auth/eu")
@exige("consultar")
def auth_eu():
    return jsonify({"usuario": usuario_atual(), "cargos": auth.CARGOS, "google": google.configurado(),
                    "permissoes": {p: sorted(c) for p, c in auth.PERMISSOES.items()},
                    "email_configurado": envio_email.configurado()})


# ---------------------------------------------------------------- administração

@app.get("/api/usuarios")
@exige("gerenciar_usuarios")
def api_usuarios():
    return jsonify({"usuarios": auth.listar_usuarios(), "cargos": auth.CARGOS})


@app.patch("/api/usuarios/<int:uid>")
@exige("gerenciar_usuarios")
def api_alterar_usuario(uid):
    d = corpo()
    eu = usuario_atual()
    if uid == eu["id"] and ("cargo" in d or d.get("ativo") is False):
        return erro_auth("Você não pode alterar o próprio cargo nem se desativar.")
    usuario, enviado = None, None
    try:
        if "cargo" in d or "ativo" in d:
            usuario = auth.alterar_usuario(uid, d.get("cargo"), d.get("ativo"), por=eu["nome"])
        if "email" in d or "telefone" in d:
            usuario, email_mudou = auth.alterar_contato(uid, d.get("email"), d.get("telefone"), por=eu["nome"])
            if email_mudou:
                enviado = enviar_confirmacao(uid, usuario["email"], usuario["nome"])
        if d.get("confirmar_email"):
            usuario = auth.confirmar_email_manual(uid, por=eu["nome"])
    except auth.ErroAuth as erro:
        return erro_auth(erro)
    if usuario is None:
        return erro_auth("Nada para alterar.")
    return jsonify({"usuario": usuario, "confirmacao_enviada": enviado})


@app.get("/api/convites")
@exige("gerenciar_usuarios")
def api_convites():
    return jsonify({"convites": auth.listar_convites()})


@app.post("/api/convites")
@exige("gerenciar_usuarios")
def api_criar_convite():
    d = corpo()
    try:
        codigo = auth.criar_convite(d.get("cargo"), d.get("dias", 7), d.get("max_usos", 5),
                                    por=usuario_atual()["nome"])
    except (auth.ErroAuth, ValueError, TypeError) as erro:
        return erro_auth(erro if isinstance(erro, auth.ErroAuth) else "Valores inválidos.")
    return jsonify({"codigo": codigo}), 201


@app.delete("/api/convites/<int:id_convite>")
@exige("gerenciar_usuarios")
def api_revogar_convite(id_convite):
    try:
        auth.revogar_convite(id_convite, por=usuario_atual()["nome"])
    except auth.ErroAuth as erro:
        return erro_auth(erro, 404)
    return jsonify({"ok": True})


@app.get("/api/auditoria")
@exige("ver_auditoria")
def api_auditoria():
    return jsonify({"eventos": auth.listar_auditoria()})


# ---------------------------------------------------------------- rotas da análise

@app.get("/api/resultados")
@exige("consultar")
@com_recorte
def api_resultados():
    """Análise completa, sem as matrizes n×n (essas vêm sob demanda em /api/matrizes)."""
    return jsonify(resultados(usuario_atual(), recorte_param()))


@app.get("/api/matrizes")
@exige("consultar")
@com_recorte
def api_matrizes():
    dados = resultados(usuario_atual(), recorte_param(), com_matrizes=True)
    return jsonify({"matrizes": dados["matrizes"], "analise": dados["analise"]})


def transacao_do_corpo(d, simuladas):
    return {
        "id_transacao": repositorio.proximo_id_simulado(simuladas),
        "conta_origem": str(d.get("de", "")).strip().upper(),
        "conta_destino": str(d.get("para", "")).strip().upper(),
        "valor": str(d.get("valor", "")).replace(",", "."),
        "data": str(d.get("data", "")),
        "hora": str(d.get("hora", "")),
        "tipo_transacao": str(d.get("tipo", "PIX")).strip() or "PIX",
    }


@app.post("/api/transacoes/validar")
@exige("simular")
def api_validar_transacao():
    """Prévia: as datas das repetições e o que cada regra da modalidade diz, sem gravar nada."""
    d = corpo()
    try:
        linhas = simulacao.expandir(transacao_do_corpo(d, []), d.get("repetir"))
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400
    verificacoes, bloqueios, alertas = simulacao.verificar(linhas)
    bancos = simulacao.dados_bancarios()
    de, para = linhas[0]["conta_origem"], linhas[0]["conta_destino"]
    return jsonify({"transacoes": verificacoes, "bloqueios": bloqueios, "alertas": alertas,
                    "origem": bancos.get(de), "destino": bancos.get(para),
                    "mesma_instituicao": bool(bancos.get(de) and bancos.get(para)
                                              and bancos[de]["instituicao"] == bancos[para]["instituicao"])})


@app.post("/api/transacoes")
@exige("simular")
def api_nova_transacao():
    d = corpo()
    usuario = usuario_atual()
    with trava:
        simuladas = repositorio.listar_simuladas(usuario["id"])
        antes = resumo_contas(resultados(usuario))
        try:
            novas = simulacao.expandir(transacao_do_corpo(d, simuladas), d.get("repetir"))
        except ValueError as erro:
            return jsonify({"erro": str(erro)}), 400
        ids = []
        for nova in novas:   # cada repetição recebe o próprio identificador (S0001, S0002...)
            nova["id_transacao"] = repositorio.proximo_id_simulado(simuladas + [{"id_transacao": i} for i in ids])
            ids.append(nova["id_transacao"])
        verificacoes, bloqueios, alertas = simulacao.verificar(novas)
        if bloqueios:
            motivos = sorted({v["mensagem"] for r in verificacoes for v in r["verificacoes"] if v["resultado"] == "bloqueio"})
            return jsonify({"erro": "Bloqueada pelas regras da modalidade: " + " ".join(motivos[:3]),
                            "verificacoes": verificacoes}), 400
        try:
            # valida e calcula ANTES de gravar: uma transação inválida não entra na simulação
            calculado, _ = analises.calcular(0, simuladas + novas)
            repositorio.adicionar_simuladas(usuario["id"], novas)
        except ValueError as erro:
            return jsonify({"erro": str(erro)}), 400
        depois = resumo_contas(calculado)
    impacto = []
    for id_conta, novo in depois.items():
        velho = antes[id_conta]
        if (novo["score"] != velho["score"] or novo["status"] != velho["status"]
                or novo["com"] != velho["com"]):
            impacto.append({"id": id_conta, "antes": velho, "depois": novo,
                            "delta_score": round(novo["score"] - velho["score"], 2)})
    impacto.sort(key=lambda x: -abs(x["delta_score"]))
    return jsonify({"transacao": novas[0], "transacoes": [n["id_transacao"] for n in novas],
                    "alertas": [v for r in verificacoes for v in r["verificacoes"] if v["resultado"] == "alerta"],
                    "impacto": impacto}), 201


@app.delete("/api/transacoes/<tid>")
@exige("simular")
def api_remover_transacao(tid):
    if repositorio.remover_simulada(usuario_atual()["id"], tid):
        return jsonify({"removida": tid})
    return jsonify({"erro": "Somente transações simuladas podem ser removidas."}), 404


@app.post("/api/simulacao/restaurar")
@exige("simular")
def api_restaurar():
    repositorio.limpar_simulacao(usuario_atual()["id"])
    return jsonify({"ok": True})


# ---------------------------------------------------------------- investigação

@app.get("/api/casos")
@exige("consultar")
def api_casos():
    return jsonify({"casos": casos.listar(), "situacoes": casos.SITUACOES})


@app.get("/api/casos/<conta>")
@exige("consultar")
def api_caso(conta):
    return jsonify(casos.detalhe(conta.upper()))


@app.post("/api/casos/<conta>")
@exige("investigar")
def api_atualizar_caso(conta):
    d = corpo()
    contas_validas = {c["id_conta"] for c in analises.obter_base()[0]}
    try:
        caso = casos.atualizar(conta.upper(), d.get("situacao"), d.get("comentario"), usuario_atual(),
                               contas_validas, request.remote_addr)
    except auth.ErroAuth as erro:
        return erro_auth(erro)
    return jsonify(caso)


# ---------------------------------------------------------------- modalidades (Fase 4)

@app.get("/api/modalidades")
@exige("consultar")
def api_modalidades():
    return jsonify({"regras": simulacao.regras_para_tela(), "origens": simulacao.bancario.ORIGENS,
                    "acoes": simulacao.bancario.ACOES, "instituicoes": simulacao.bancario.INSTITUICOES})


@app.post("/api/modalidades/<regra>")
@exige("administrar_regras")
def api_ajustar_regra(regra):
    d, usuario = corpo(), usuario_atual()
    if regra not in simulacao.bancario.REGRAS_PADRAO:
        return erro_auth("Regra inexistente.", 404)
    if d.get("padrao"):
        repositorio.apagar_ajuste_regra(regra)
        auth.registrar("regra_modalidade", None, f"{regra}: voltou ao padrão por {usuario['nome']}", request.remote_addr)
        return jsonify({"regras": simulacao.regras_para_tela()})
    acao = d.get("acao")
    if acao not in simulacao.bancario.ACOES:
        return erro_auth("Ação inválida: use bloquear, alertar ou desligada.")
    if regra == "pix_24h" and acao == "bloquear":
        return erro_auth("Esta regra é informativa: não pode bloquear.")
    try:
        parametros = simulacao.bancario.validar_parametros(regra, d.get("parametros") or {})
    except ValueError as erro:
        return erro_auth(erro)
    atual = simulacao.regras()[regra]["parametros"]
    repositorio.salvar_ajuste_regra(regra, acao, {**atual, **parametros}, usuario["nome"])
    auth.registrar("regra_modalidade", None, f"{regra}: {acao} {parametros or ''} por {usuario['nome']}"[:255],
                   request.remote_addr)
    return jsonify({"regras": simulacao.regras_para_tela()})


# ---------------------------------------------------------------- limites das regras de risco (Fase 5)

def parametros_risco_para_tela():
    from nucleo import risco
    efetivos, ajustes = analises.parametros_risco(), repositorio.ler_parametros_risco()
    return [{"chave": k, **info, "valor": efetivos[k], "padrao": risco.PARAMETROS[k],
             "regras_nomes": [risco.REGRA[r]["nome"] for r in info["regras"]],
             "ajustado_por": ajustes.get(k, {}).get("atualizado_por"),
             "ajustado_em": ajustes.get(k, {}).get("atualizado_em")}
            for k, info in risco.PARAMETROS_INFO.items()]


@app.get("/api/parametros-risco")
@exige("consultar")
def api_parametros_risco():
    return jsonify({"parametros": parametros_risco_para_tela()})


@app.post("/api/parametros-risco")
@exige("administrar_regras")
def api_salvar_parametros_risco():
    from nucleo import risco
    d, usuario = corpo(), usuario_atual()
    if d.get("padrao"):
        repositorio.apagar_parametros_risco()
        analises.esquecer_parametros()
        auth.registrar("parametros_risco", None, f"limites de risco voltaram ao padrão por {usuario['nome']}",
                       request.remote_addr)
        return jsonify({"parametros": parametros_risco_para_tela()})
    valores = d.get("valores")
    if not isinstance(valores, dict) or not valores:
        return erro_auth("Envie os limites a alterar.")
    try:
        limpos = {k: risco.validar_parametro(k, v) for k, v in valores.items()}
    except ValueError as erro:
        return erro_auth(erro)
    atuais = analises.parametros_risco()
    mudaram = {k: v for k, v in limpos.items() if v != atuais[k]}
    repositorio.salvar_parametros_risco(limpos, usuario["nome"])
    analises.esquecer_parametros()
    if mudaram:
        auth.registrar("parametros_risco", None,
                       (", ".join(f"{k}: {atuais[k]:g} → {v:g}" for k, v in mudaram.items()) + f" por {usuario['nome']}")[:255],
                       request.remote_addr)
    return jsonify({"parametros": parametros_risco_para_tela()})


# ---------------------------------------------------------------- preferências do usuário (Fase 5)

@app.get("/api/preferencias")
@exige("consultar")
def api_preferencias():
    return jsonify({"preferencias": preferencias.ler(usuario_atual()["id"]), "padrao": preferencias.PADRAO})


@app.put("/api/preferencias")
@exige("consultar")
def api_salvar_preferencias():
    d = corpo()
    try:
        if d.get("padrao"):
            repositorio.salvar_preferencias(usuario_atual()["id"], {})
            return jsonify({"preferencias": dict(preferencias.PADRAO)})
        return jsonify({"preferencias": preferencias.salvar(usuario_atual()["id"], d.get("preferencias") or {})})
    except ValueError as erro:
        return erro_auth(erro)


# ---------------------------------------------------------------- importação de bases (Fase 6)

_importando = {}            # usuário → arquivo lido, esperando a confirmação (some em 30 minutos)
_trava_importacao = threading.Lock()
VALIDADE_IMPORTACAO = 30 * 60
NOME_DEMONSTRACAO = "Base de demonstração (40 contas, 160 transações)"


def _arquivo_em_andamento(usuario):
    with _trava_importacao:
        for uid in [u for u, v in _importando.items() if time.time() - v["em"] > VALIDADE_IMPORTACAO]:
            del _importando[uid]
        item = _importando.get(usuario["id"])
    if item is None:
        raise ValueError("O arquivo enviado expirou ou não foi encontrado. Envie o arquivo de novo.")
    return item["arquivo"]


def _sem_dados_grandes(resultado):
    return {k: v for k, v in resultado.items() if k not in ("contas", "transacoes")}


def _preparar_do_corpo(usuario, d):
    from nucleo import importacao
    arquivo = _arquivo_em_andamento(usuario)
    aba_contas = d.get("aba_contas")
    return arquivo, importacao.preparar(arquivo, int(d.get("aba_transacoes", 0)), d.get("mapa_transacoes") or {},
                                        None if aba_contas in (None, "", -1) else int(aba_contas),
                                        d.get("mapa_contas") or {}, bool(d.get("mascarar")))


@app.get("/api/base")
@exige("consultar")
def api_base():
    """Base em uso; para quem importa, também o histórico e o que a troca apagaria."""
    usuario = usuario_atual()
    contas, transacoes, _ = analises.obter_base()
    datas = sorted(t["data"] for t in transacoes)
    resposta = {"base": {**analises.info_base(), "contas": len(contas), "transacoes": len(transacoes),
                         "periodo": [datas[0], datas[-1]] if datas else None},
                "pode_importar": auth.tem_permissao(usuario, "importar_base")}
    if resposta["pode_importar"]:
        resposta["historico"] = repositorio.historico_importacoes()
        resposta["apagados_na_troca"] = repositorio.contar_derivados()
    return jsonify(resposta)


@app.get("/api/importacao/modelo")
@exige("importar_base")
def api_modelo_importacao():
    from nucleo import importacao
    return Response(importacao.modelo_xlsx(), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="modelo_base_nexo.xlsx"'})


@app.post("/api/importacao/arquivo")
@exige("importar_base")
def api_importacao_arquivo():
    """Recebe o arquivo, lê as abas e sugere o mapeamento (ou usa o salvo para o mesmo layout)."""
    from nucleo import importacao
    usuario, enviado = usuario_atual(), request.files.get("arquivo")
    if enviado is None or not enviado.filename:
        return erro_auth("Escolha um arquivo .xlsx ou .csv.")
    try:
        arquivo = importacao.ler_arquivo(enviado.filename, enviado.read())
    except importacao.ErroArquivo as erro:
        return erro_auth(erro)
    sugestao = importacao.sugerir(arquivo)
    salvo = repositorio.ler_mapeamento(importacao.assinatura_colunas(arquivo["abas"][sugestao["aba_transacoes"]]["cabecalho"]))
    if salvo and all(0 <= int(i) < len(arquivo["abas"][sugestao["aba_transacoes"]]["cabecalho"])
                     for i in salvo.get("mapa_transacoes", {}).values()):
        sugestao["mapa_transacoes"] = salvo["mapa_transacoes"]
    with _trava_importacao:
        _importando[usuario["id"]] = {"arquivo": arquivo, "em": time.time()}
    ativa = repositorio.base_ativa()
    resultado = importacao.preparar(arquivo, sugestao["aba_transacoes"], sugestao["mapa_transacoes"],
                                    sugestao["aba_contas"], sugestao["mapa_contas"])
    return jsonify({"arquivo": {"nome": arquivo["nome"], "hash": arquivo["hash"][:12]},
                    "abas": [{"nome": a["nome"], "cabecalho": a["cabecalho"], "linhas": len(a["linhas"])} for a in arquivo["abas"]],
                    # listas (e não dicionários): o JSON do Flask ordena as chaves, e a tela quer a ordem natural
                    "campos": {"transacoes": [[k, v[0], v[1]] for k, v in importacao.CAMPOS_TRANSACAO.items()],
                               "contas": [[k, v[0], v[1]] for k, v in importacao.CAMPOS_CONTA.items()]},
                    "sugestao": sugestao, "mapeamento_salvo": bool(salvo),
                    "mesmo_arquivo_da_base": bool(ativa and ativa.get("hash_arquivo") == arquivo["hash"]),
                    "resultado": _sem_dados_grandes(resultado)})


@app.post("/api/importacao/previa")
@exige("importar_base")
def api_importacao_previa():
    from nucleo import importacao
    try:
        _, resultado = _preparar_do_corpo(usuario_atual(), corpo())
    except (ValueError, importacao.ErroArquivo) as erro:
        return erro_auth(erro)
    return jsonify({"resultado": _sem_dados_grandes(resultado)})


def _trocar_base(usuario, contas, transacoes, registro):
    """Backup automático → troca numa transação → caches limpos → auditoria. Sem backup, não troca."""
    from banco import backup
    try:
        arquivo_backup, _ = backup.fazer_backup()
    except Exception as erro:  # noqa: BLE001
        raise RuntimeError(f"O backup automático falhou, então a base NÃO foi trocada: {erro}") from erro
    registro = {**registro, "backup": str(arquivo_backup.name), "importado_por": usuario["nome"]}
    importacao_id = repositorio.substituir_base(contas, transacoes, registro)
    analises.limpar_cache()
    return importacao_id, arquivo_backup.name


@app.post("/api/importacao/confirmar")
@exige("importar_base")
def api_importacao_confirmar():
    from nucleo import importacao
    usuario, d = usuario_atual(), corpo()
    if str(d.get("confirmacao", "")).strip().upper() != "SUBSTITUIR":
        return erro_auth("Digite SUBSTITUIR para confirmar a troca da base.")
    if not d.get("aceite"):
        return erro_auth("Confirme que os dados podem ser usados neste trabalho (autorização e finalidade).")
    nome = " ".join(str(d.get("nome") or "").split())[:120]
    if len(nome) < 3:
        return erro_auth("Dê um nome à base (mínimo de 3 caracteres), por exemplo o nome da empresa e o período.")
    try:
        arquivo, resultado = _preparar_do_corpo(usuario, d)
    except (ValueError, importacao.ErroArquivo) as erro:
        return erro_auth(erro)
    if not resultado["pode_importar"]:
        return jsonify({"erro": "O arquivo ainda tem erros. Corrija e envie de novo.", "resultado": _sem_dados_grandes(resultado)}), 400
    try:
        importacao_id, arquivo_backup = _trocar_base(usuario, resultado["contas"], resultado["transacoes"], {
            "nome": nome, "origem": "arquivo", "arquivo": arquivo["nome"][:255], "hash": arquivo["hash"],
            "mascarada": bool(d.get("mascarar"))})
    except RuntimeError as erro:
        return erro_auth(erro, 500)
    aba = arquivo["abas"][int(d.get("aba_transacoes", 0))]
    repositorio.salvar_mapeamento(importacao.assinatura_colunas(aba["cabecalho"]),
                                  {"mapa_transacoes": d.get("mapa_transacoes") or {}}, usuario["nome"])
    with _trava_importacao:
        _importando.pop(usuario["id"], None)
    auth.registrar("base_importada", None, (f"{usuario['nome']}: “{nome}” ({arquivo['nome']}, "
                                             f"{len(resultado['transacoes'])} transações, {len(resultado['contas'])} contas"
                                             f"{', mascarada' if d.get('mascarar') else ''}); backup {arquivo_backup}")[:255],
                   request.remote_addr)
    return jsonify({"ok": True, "importacao": importacao_id, "backup": arquivo_backup, "base": analises.info_base()})


@app.post("/api/base/demonstracao")
@exige("importar_base")
def api_base_demonstracao():
    """Volta à base de demonstração (40 contas e 160 transações dos CSVs do projeto)."""
    usuario, d = usuario_atual(), corpo()
    if str(d.get("confirmacao", "")).strip().upper() != "SUBSTITUIR":
        return erro_auth("Digite SUBSTITUIR para confirmar a troca da base.")
    contas, transacoes = repositorio.carregar_csv()
    try:
        _, arquivo_backup = _trocar_base(usuario, contas, transacoes, {"nome": NOME_DEMONSTRACAO, "origem": "demonstracao",
                                                                      "arquivo": "contas.csv + transacoes.csv"})
    except RuntimeError as erro:
        return erro_auth(erro, 500)
    auth.registrar("base_demonstracao", None, f"{usuario['nome']}: voltou à base de demonstração; backup {arquivo_backup}",
                   request.remote_addr)
    return jsonify({"ok": True, "backup": arquivo_backup, "base": analises.info_base()})


# ---------------------------------------------------------------- histórico e comparação (Fase 4)

@app.get("/api/cenarios")
@exige("simular")
def api_cenarios():
    return jsonify({"cenarios": repositorio.listar_cenarios(usuario_atual()["id"])})


@app.post("/api/cenarios")
@exige("simular")
def api_salvar_cenario():
    d = corpo()
    try:
        cid = simulacao.salvar_cenario(usuario_atual(), d.get("nome"), d.get("descricao"), d.get("recorte") or 0)
    except ValueError as erro:
        return erro_auth(erro)
    auth.registrar("cenario_salvo", None, f"cenário {cid} por {usuario_atual()['nome']}", request.remote_addr)
    return jsonify({"id": cid, "cenarios": repositorio.listar_cenarios(usuario_atual()["id"])}), 201


@app.get("/api/cenarios/<int:cid>")
@exige("simular")
def api_cenario(cid):
    cenario = repositorio.obter_cenario(usuario_atual()["id"], cid)
    if cenario is None:
        return erro_auth("Cenário não encontrado.", 404)
    cenario["comparacao"] = simulacao.comparacao.comparar(cenario["resultado_base"], cenario["resultado"])
    return jsonify(cenario)


@app.post("/api/cenarios/<int:cid>/restaurar")
@exige("simular")
def api_restaurar_cenario(cid):
    try:
        cenario = repositorio.restaurar_cenario(usuario_atual()["id"], cid)
    except ValueError as erro:
        return erro_auth(erro)
    if cenario is None:
        return erro_auth("Cenário não encontrado.", 404)
    return jsonify({"ok": True, "transacoes": len(cenario["transacoes"])})


@app.delete("/api/cenarios/<int:cid>")
@exige("simular")
def api_excluir_cenario(cid):
    if not repositorio.excluir_cenario(usuario_atual()["id"], cid):
        return erro_auth("Cenário não encontrado.", 404)
    return jsonify({"ok": True})


@app.get("/api/comparar")
@exige("consultar")
@com_recorte
def api_comparar():
    """Comparação lado a lado. a/b: base · recorte:INI:FIM · rascunho · cenario:ID · cenario:ID:base."""
    usuario = usuario_atual()
    fontes = [request.args.get("a", "base"), request.args.get("b", "base")]
    if any(f.startswith(("rascunho", "cenario")) for f in fontes) and not auth.tem_permissao(usuario, "simular"):
        return jsonify({"erro": "O seu cargo pode comparar períodos, mas não simulações."}), 403
    (ra, rotulo_a), (rb, rotulo_b) = (simulacao.fonte(usuario, f) for f in fontes)
    return jsonify({"a": {"rotulo": rotulo_a, **ra}, "b": {"rotulo": rotulo_b, **rb},
                    "diferencas": simulacao.comparacao.comparar(ra, rb)})


@app.get("/api/relatorio")
@exige("exportar")
@com_recorte
def api_relatorio():
    """Relatório em PDF, Excel, CSV (zip), Word ou PowerPoint.
    tipo=analise (recorte atual + simulação do usuário) · tipo=comparacao&a=&b= (fontes como em /api/comparar)."""
    from datetime import datetime

    from app import exportacao
    from nucleo import relatorio
    usuario, formato, tipo = usuario_atual(), request.args.get("formato", "pdf"), request.args.get("tipo", "analise")
    if formato not in exportacao.FORMATOS:
        return erro_auth("Formato inválido: use pdf, xlsx, csv, docx ou pptx.")
    agora = datetime.now()
    if tipo == "analise":
        documento = relatorio.relatorio_analise(resultados(usuario, recorte_param()), usuario, agora)
        descricao = "análise"
    elif tipo == "comparacao":
        fontes = [request.args.get("a", "base"), request.args.get("b", "base")]
        if any(f.startswith(("rascunho", "cenario")) for f in fontes) and not auth.tem_permissao(usuario, "simular"):
            return jsonify({"erro": "O seu cargo pode comparar períodos, mas não simulações."}), 403
        (ra, rotulo_a), (rb, rotulo_b) = (simulacao.fonte(usuario, f) for f in fontes)
        documento = relatorio.relatorio_comparacao(ra, rb, rotulo_a, rotulo_b, simulacao.comparacao.comparar(ra, rb),
                                                   usuario, agora)
        descricao = f"comparação {fontes[0]} × {fontes[1]}"
    else:
        return erro_auth("Tipo de relatório inválido: use analise ou comparacao.")
    try:
        conteudo, mime, nome = exportacao.gerar(documento, formato)
    except RuntimeError as erro:
        return erro_auth(erro, 500)
    auth.registrar("relatorio", None, f"{usuario['nome']}: {descricao} em {exportacao.NOMES[formato]}", request.remote_addr)
    return Response(conteudo, mimetype=mime, headers={"Content-Disposition": f'attachment; filename="{nome}"',
                                                      "Cache-Control": "no-store"})


@app.get("/api/exportar")
@exige("exportar")
@com_recorte
def api_exportar():
    dados = resultados(usuario_atual(), recorte_param(), com_matrizes=True)
    return Response(json.dumps(dados, ensure_ascii=False, indent=2),
                    mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=resultados_nexo.json"})


def _porta_livre(inicial):
    """Primeira porta em que o servidor realmente consegue escutar, a partir de `inicial`.

    Testa com bind (e não só com connect): no Windows, o Hyper-V/WSL/Docker às vezes reserva a
    porta 5000; ela parece livre, mas o servidor não consegue usá-la."""
    import socket
    for porta in range(inicial, inicial + 20):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", porta))
                return porta
            except OSError:
                continue
    return None


def _abrir_navegador_quando_pronto(url, porta):
    """Abre o navegador só depois que o servidor aceitar conexões (no máximo 60 s)."""
    import socket
    import time
    import webbrowser
    for _ in range(120):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", porta)) == 0:
                webbrowser.open(url)
                return
        time.sleep(0.5)


def executar():
    """Inicia o servidor local, na primeira porta livre a partir da 5000."""
    import os
    if auth.contar_administradores_ativos() == 0:
        print("Nenhum administrador cadastrado. Crie um com: scripts\\CRIAR_ADMIN.bat")
    inicial = int(os.environ.get("NEXO_PORTA", 5000))
    porta = _porta_livre(inicial)
    if porta is None:
        print(f"[ERRO] Nenhuma porta livre entre {inicial} e {inicial + 19}. "
              "Feche outros NEXO abertos ou defina NEXO_PORTA com outra porta (ex.: 8080).")
        raise SystemExit(1)
    url = f"http://127.0.0.1:{porta}"
    if porta != inicial:
        print(f"A porta {inicial} está ocupada ou bloqueada pelo Windows; usando a {porta}.")
    print(f"NEXO em {url}  (Ctrl+C para parar)")
    if os.environ.get("NEXO_ABRIR_NAVEGADOR") == "1":
        threading.Thread(target=_abrir_navegador_quando_pronto, args=(url, porta), daemon=True).start()
    app.run(debug=False, host="127.0.0.1", port=porta, threaded=True)
