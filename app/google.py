"""NEXO — "Entrar com Google" (OpenID Connect), sem bibliotecas extras.

Configuração (.env, criada em scripts\\CONFIGURAR.bat):
    GOOGLE_CLIENT_ID      ID do cliente OAuth (Google Cloud → APIs e serviços → Credenciais)
    GOOGLE_CLIENT_SECRET  chave secreta do cliente (NUNCA vai para o GitHub)
    GOOGLE_DOMINIOS       opcional: só aceita e-mails destes domínios (ex.: empresa.com.br,outra.com)
Endereço de retorno a cadastrar no Google: {APP_URL_BASE}/auth/google/retorno

Fluxo (authorization code + PKCE + state + nonce):
  1. /auth/google gera state, nonce e o verificador PKCE, guarda na sessão e manda ao Google;
  2. o Google devolve um código em /auth/google/retorno;
  3. o servidor troca o código pelo id_token direto com o Google (HTTPS, com a chave secreta).
     Como o token vem do próprio Google por um canal seguro, a documentação do Google
     dispensa conferir a assinatura; conferimos emissor, destinatário, validade, nonce
     e se o e-mail foi verificado.
Sem GOOGLE_CLIENT_ID configurado, o botão não aparece e as rotas respondem 404.
"""

import base64
import hashlib
import json
import secrets
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from nucleo import configuracao

URL_AUTORIZACAO = "https://accounts.google.com/o/oauth2/v2/auth"
URL_TOKEN = "https://oauth2.googleapis.com/token"
EMISSORES = {"https://accounts.google.com", "accounts.google.com"}
VALIDADE_PEDIDO_SEGUNDOS = 600


class ErroGoogle(Exception):
    """Falha no login com Google, com mensagem pronta para o usuário."""


def config():
    v = configuracao.valores()
    dominios = [d.strip().lower().lstrip("@") for d in v.get("GOOGLE_DOMINIOS", "").split(",") if d.strip()]
    return {"client_id": v.get("GOOGLE_CLIENT_ID", "").strip(),
            "client_secret": v.get("GOOGLE_CLIENT_SECRET", "").strip(),
            "dominios": dominios}


def configurado():
    c = config()
    return bool(c["client_id"] and c["client_secret"])


def _b64(dados):
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def iniciar(url_retorno):
    """Retorna (url para mandar o navegador, dados para guardar na sessão)."""
    c = config()
    pedido = {"state": secrets.token_urlsafe(24), "nonce": secrets.token_urlsafe(24),
              "verificador": secrets.token_urlsafe(48), "criado": int(time.time())}
    parametros = {
        "client_id": c["client_id"], "redirect_uri": url_retorno, "response_type": "code",
        "scope": "openid email profile", "state": pedido["state"], "nonce": pedido["nonce"],
        "code_challenge": _b64(hashlib.sha256(pedido["verificador"].encode()).digest()),
        "code_challenge_method": "S256", "prompt": "select_account",
    }
    if len(c["dominios"]) == 1:
        parametros["hd"] = c["dominios"][0]  # o Google já mostra só contas desse domínio
    return f"{URL_AUTORIZACAO}?{urllib.parse.urlencode(parametros)}", pedido


def trocar_codigo(codigo, verificador, url_retorno):
    """Troca o código pelo id_token, direto com o Google. Separada para os testes."""
    c = config()
    corpo = urllib.parse.urlencode({
        "code": codigo, "client_id": c["client_id"], "client_secret": c["client_secret"],
        "redirect_uri": url_retorno, "grant_type": "authorization_code", "code_verifier": verificador,
    }).encode()
    pedido = urllib.request.Request(URL_TOKEN, data=corpo, method="POST",
                                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(pedido, timeout=15, context=ssl.create_default_context()) as resposta:
            dados = json.load(resposta)
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode(errors="replace")[:200]
        raise ErroGoogle(f"O Google recusou o login ({erro.code}). Confira o ID e a chave do cliente "
                         f"e o endereço de retorno cadastrado. Detalhe: {detalhe}") from erro
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise ErroGoogle("Não foi possível falar com o Google. Verifique a internet.") from erro
    if "id_token" not in dados:
        raise ErroGoogle("O Google não devolveu a identificação da conta.")
    return _ler_id_token(dados["id_token"])


def _ler_id_token(id_token):
    try:
        conteudo = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(conteudo + "=" * (-len(conteudo) % 4)))
    except (IndexError, ValueError) as erro:
        raise ErroGoogle("Resposta do Google em formato inesperado.") from erro


def concluir(parametros, pedido, url_retorno):
    """Valida o retorno do Google e devolve {sujeito, email, nome}."""
    if not pedido or int(time.time()) - pedido.get("criado", 0) > VALIDADE_PEDIDO_SEGUNDOS:
        raise ErroGoogle("O pedido de login expirou. Clique em “Entrar com Google” de novo.")
    if parametros.get("error"):
        raise ErroGoogle("Login com Google cancelado." if parametros["error"] == "access_denied"
                         else f"O Google recusou o login ({parametros['error']}).")
    if not secrets.compare_digest(str(parametros.get("state", "")), pedido["state"]):
        raise ErroGoogle("Pedido de login inválido. Clique em “Entrar com Google” de novo.")
    if not parametros.get("code"):
        raise ErroGoogle("O Google não devolveu o código de acesso.")
    dados = trocar_codigo(parametros["code"], pedido["verificador"], url_retorno)
    c = config()
    if dados.get("iss") not in EMISSORES or dados.get("aud") != c["client_id"]:
        raise ErroGoogle("Identificação do Google não confere com este sistema.")
    if int(dados.get("exp", 0)) < time.time() or dados.get("nonce") != pedido["nonce"]:
        raise ErroGoogle("Identificação do Google expirada ou repetida. Tente de novo.")
    email = str(dados.get("email", "")).lower()
    if not email or dados.get("email_verified") not in (True, "true"):
        raise ErroGoogle("O Google não confirmou este e-mail. Use outra conta ou entre com senha.")
    if c["dominios"] and email.rsplit("@", 1)[-1] not in c["dominios"]:
        raise ErroGoogle(f"Só são aceitas contas dos domínios: {', '.join(c['dominios'])}.")
    return {"sujeito": str(dados["sub"]), "email": email, "nome": str(dados.get("name") or "").strip()}
