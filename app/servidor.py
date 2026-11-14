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

from app import analises, auth, casos, envio_email, google
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
                  SEND_FILE_MAX_AGE_DEFAULT=0)
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


@app.post("/api/transacoes")
@exige("simular")
def api_nova_transacao():
    d = corpo()
    usuario = usuario_atual()
    with trava:
        simuladas = repositorio.listar_simuladas(usuario["id"])
        antes = resumo_contas(resultados(usuario))
        nova = {
            "id_transacao": repositorio.proximo_id_simulado(simuladas),
            "conta_origem": str(d.get("de", "")).strip().upper(),
            "conta_destino": str(d.get("para", "")).strip().upper(),
            "valor": str(d.get("valor", "")).replace(",", "."),
            "data": str(d.get("data", "")),
            "hora": str(d.get("hora", "")),
            "tipo_transacao": str(d.get("tipo", "PIX")).strip() or "PIX",
        }
        try:
            # valida e calcula ANTES de gravar: uma transação inválida não entra na simulação
            calculado, _ = analises.calcular(0, simuladas + [nova])
            repositorio.adicionar_simulada(usuario["id"], nova)
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
    return jsonify({"transacao": nova, "impacto": impacto}), 201


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


@app.get("/api/exportar")
@exige("exportar")
@com_recorte
def api_exportar():
    dados = resultados(usuario_atual(), recorte_param(), com_matrizes=True)
    return Response(json.dumps(dados, ensure_ascii=False, indent=2),
                    mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=resultados_nexo.json"})


def executar():
    """Inicia o servidor local, na primeira porta livre a partir da 5000."""
    import os
    import socket
    if auth.contar_administradores_ativos() == 0:
        print("Nenhum administrador cadastrado. Crie um com: scripts\\CRIAR_ADMIN.bat")
    porta = int(os.environ.get("NEXO_PORTA", 5000))
    # porta ocupada (outro NEXO aberto, AirPlay no macOS): usa a próxima livre
    while porta < 5020:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", porta)) != 0:
                break
        porta += 1
    print(f"NEXO em http://127.0.0.1:{porta}  (Ctrl+C para parar)")
    app.run(debug=False, port=porta, threaded=True)
