"""NEXO — envio de e-mail (SMTP real): confirmação de cadastro e recuperação de senha.

Configuração: SMTP_* no .env (ou seção [smtp] do config.ini antigo).
Testar: scripts\\TESTAR_EMAIL.bat  ou  python -m app.envio_email destino@exemplo.com
"""

import html as html_lib
import smtplib
import ssl
import sys
from email.message import EmailMessage

from nucleo import configuracao as config


class ErroEmail(RuntimeError):
    pass


def configuracao():
    v = config.valores()
    if not v.get("SMTP_HOST", "").strip():
        raise ErroEmail("Envio de e-mail não configurado. Rode scripts\\CONFIGURAR.bat e responda 's' em "
                        "'Configurar o e-mail'.")
    usuario = v.get("SMTP_USER", "").strip()
    if usuario and not v.get("SMTP_PASSWORD", "").strip():
        raise ErroEmail("A senha do e-mail está vazia. Rode scripts\\CONFIGURAR.bat e cole a "
                        "senha de app do Gmail (16 letras).")
    try:
        porta = int(v.get("SMTP_PORT") or 587)
    except ValueError as erro:
        raise ErroEmail(f"SMTP_PORT inválida: {v.get('SMTP_PORT')!r}.") from erro
    return {
        "host": v["SMTP_HOST"].strip(),
        "porta": porta,
        "seguranca": (v.get("SMTP_SECURITY") or "starttls").strip().lower(),  # starttls | ssl | nenhuma
        "usuario": usuario,
        "senha": v.get("SMTP_PASSWORD", "").strip(),
        "remetente": v.get("SMTP_FROM", "").strip() or usuario,
    }


class _Etapa:
    """Guarda em que ponto da conversa com o servidor a falha aconteceu."""
    def __init__(self):
        self.nome = "conectar"


def _explicar(erro, c=None, etapa="conectar"):
    """Traduz os erros do SMTP (principalmente do Gmail), dizendo em que etapa falhou."""
    texto = str(erro)
    usado = f" ({c['host']}, porta {c['porta']}, {c['seguranca']})" if c else ""
    if isinstance(erro, smtplib.SMTPAuthenticationError):
        resposta = (erro.smtp_error.decode(errors="replace") if isinstance(erro.smtp_error, bytes)
                    else str(erro.smtp_error)).replace("\n", " ").strip()
        if erro.smtp_code == 454 or "Too many" in resposta:
            return ("o Gmail bloqueou temporariamente o login por TENTATIVAS DEMAIS. Espere cerca de 1 hora "
                    "sem testar e tente de novo; se continuar, crie uma senha de app nova "
                    f"(myaccount.google.com/apppasswords). Resposta do servidor: {erro.smtp_code} {resposta}")
        if erro.smtp_code == 534 or "Application-specific" in resposta:
            return ("o Gmail exige uma SENHA DE APP (16 letras), não a senha normal da conta. Crie em "
                    f"myaccount.google.com/apppasswords. Resposta do servidor: {erro.smtp_code} {resposta}")
        return ("o servidor RECUSOU o usuário ou a senha. Confira: (1) SMTP_USER é exatamente o Gmail em que "
                "a senha de app foi criada; (2) a senha de app ainda existe (o Google apaga as senhas de app "
                "quando a senha da conta é trocada); (3) a verificação em duas etapas está ativa. Se precisar, "
                "crie uma senha de app nova e rode scripts\\CONFIGURAR.bat (opção 1). "
                f"Resposta do servidor: {erro.smtp_code} {resposta}")
    if isinstance(erro, smtplib.SMTPServerDisconnected) or "unexpectedly closed" in texto:
        if etapa == "login":
            return ("o servidor encerrou a conexão DURANTE O LOGIN, o que no Gmail costuma significar senha "
                    "recusada ou tentativas demais. Crie uma senha de app nova (myaccount.google.com/apppasswords), "
                    "espere alguns minutos e rode scripts\\CONFIGURAR.bat (opção 1).")
        return (f"o servidor fechou a conexão logo no início{usado}, antes de pedir a senha. Causas: porta e "
                "segurança que não combinam (use 587 + starttls ou 465 + ssl), servidor digitado errado, ou "
                "a rede/antivírus bloqueando o e-mail (teste no hotspot do celular).")
    if isinstance(erro, ssl.SSLError):
        return (f"falha na conexão segura (TLS){usado}: {texto}. Confira se a segurança combina com a porta "
                "(587 + starttls ou 465 + ssl) e se o antivírus não intercepta e-mails.")
    if isinstance(erro, (TimeoutError, ConnectionRefusedError, OSError)) and not isinstance(erro, smtplib.SMTPException):
        return (f"não foi possível conectar ao servidor de e-mail{usado}: {texto}. Confira servidor, porta e "
                "internet; a rede ou o antivírus podem estar bloqueando.")
    return f"{texto} (etapa: {etapa})"


def _conectar(c, etapa=None):
    """Conecta e faz login, uma etapa por vez, para saber exatamente onde falhou."""
    etapa = etapa or _Etapa()
    contexto = ssl.create_default_context()
    # nome fixo no EHLO: alguns computadores têm nome com acento/espaço, que o servidor pode rejeitar
    if c["seguranca"] == "ssl":
        servidor = smtplib.SMTP_SSL(c["host"], c["porta"], context=contexto, timeout=20, local_hostname="nexo.local")
    else:
        servidor = smtplib.SMTP(c["host"], c["porta"], timeout=20, local_hostname="nexo.local")
    try:
        etapa.nome = "apresentar"
        servidor.ehlo()
        if c["seguranca"] == "starttls":
            etapa.nome = "starttls"
            servidor.starttls(context=contexto)
            servidor.ehlo()
        if c["usuario"]:
            etapa.nome = "login"
            _login(servidor, c["usuario"], c["senha"])
        etapa.nome = "enviar"
    except Exception:
        servidor.close()
        raise
    return servidor


def _login(servidor, usuario, senha):
    """Login com UM método só (PLAIN, senão LOGIN).

    O smtplib.login() tenta vários métodos em sequência; quando o Gmail recusa a senha
    e fecha a conexão, a segunda tentativa vira "Connection unexpectedly closed" e
    esconde o motivo real (senha recusada, tentativas demais...).
    """
    metodos = servidor.esmtp_features.get("auth", "").upper().split()
    servidor.user, servidor.password = usuario, senha
    if "PLAIN" in metodos:
        codigo, resposta = servidor.auth("PLAIN", servidor.auth_plain)
    elif "LOGIN" in metodos:
        codigo, resposta = servidor.auth("LOGIN", servidor.auth_login)
    else:
        servidor.login(usuario, senha)
        return
    if codigo not in (235, 503):
        raise smtplib.SMTPAuthenticationError(codigo, resposta)


def testar_login():
    """Conecta e faz login no servidor de e-mail, sem enviar nada."""
    c = configuracao()
    etapa = _Etapa()
    try:
        with _conectar(c, etapa):
            pass
    except (smtplib.SMTPException, OSError) as erro:
        raise ErroEmail(f"Falha no e-mail: {_explicar(erro, c, etapa.nome)}") from erro
    return c


def enviar(destino, assunto, texto, html=None):
    c = configuracao()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = c["remetente"], destino, assunto
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")
    etapa = _Etapa()
    try:
        with _conectar(c, etapa) as servidor:
            servidor.send_message(msg)
    except (smtplib.SMTPException, OSError) as erro:
        raise ErroEmail(f"Falha ao enviar e-mail: {_explicar(erro, c, etapa.nome)}") from erro


def configurado():
    try:
        configuracao()
        return True
    except ErroEmail:
        return False


def _modelo(nome, paragrafos, botao, link, rodape):
    """HTML com a identidade do NEXO; nome e link são escapados."""
    nome_html, link_html = html_lib.escape(nome), html_lib.escape(link, quote=True)
    corpo = "".join(f"<p>{p}</p>" for p in paragrafos)
    return f"""<div style="font-family:Arial,sans-serif;max-width:520px;color:#16202E">
      <div style="background:#0B1F3A;color:#fff;padding:18px 22px;border-radius:10px 10px 0 0;font-size:20px;letter-spacing:.14em;font-weight:700">NEXO</div>
      <div style="border:1px solid #E1E7EF;border-top:0;padding:22px;border-radius:0 0 10px 10px">
        <p>Olá, <b>{nome_html}</b>.</p>{corpo}
        <p style="text-align:center;margin:26px 0"><a href="{link_html}" style="background:#1B5FA8;color:#fff;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:600">{botao}</a></p>
        <p style="font-size:13px;color:#4A5A6E">{rodape}</p>
        <p style="font-size:12px;color:#7C8B9E">Se o botão não funcionar, copie e cole no navegador:<br>{link_html}</p>
      </div></div>"""


def enviar_recuperacao(destino, nome, link, validade_minutos):
    texto = (f"Olá, {nome}.\n\nRecebemos um pedido para redefinir sua senha no NEXO.\n"
             f"Acesse o link abaixo (válido por {validade_minutos} minutos e de uso único):\n\n{link}\n\n"
             "Se você não fez este pedido, ignore este e-mail: sua senha atual continua válida.\n\n"
             "NEXO — Ponto de Conexão")
    html = _modelo(nome, ["Recebemos um pedido para redefinir sua senha no NEXO."], "Redefinir minha senha", link,
                   f"O link vale por {validade_minutos} minutos e só pode ser usado uma vez. "
                   "Se você não fez este pedido, ignore este e-mail: sua senha atual continua válida.")
    enviar(destino, "NEXO — Redefinição de senha", texto, html)


def enviar_confirmacao(destino, nome, link, validade_horas):
    texto = (f"Olá, {nome}.\n\nFalta pouco para acessar o NEXO: confirme seu e-mail pelo link abaixo "
             f"(válido por {validade_horas} horas):\n\n{link}\n\n"
             "Se você não se cadastrou no NEXO, ignore este e-mail.\n\nNEXO — Ponto de Conexão")
    html = _modelo(nome, ["Falta pouco para acessar o NEXO: confirme que este e-mail é seu."],
                   "Confirmar meu e-mail", link,
                   f"O link vale por {validade_horas} horas. Se você não se cadastrou no NEXO, ignore este e-mail.")
    enviar(destino, "NEXO — Confirme seu e-mail", texto, html)


if __name__ == "__main__":
    destino = sys.argv[1] if len(sys.argv) > 1 else input("Enviar e-mail de teste para: ").strip()
    try:
        c = testar_login()
        print(f"Login no servidor de e-mail OK ({c['usuario']} em {c['host']}).")
        enviar(destino, "NEXO — teste de e-mail", "O envio de e-mails do NEXO está funcionando.")
        print(f"E-mail de teste enviado para {destino}. Confira a caixa de entrada e o spam.")
    except ErroEmail as erro:
        print(erro)
        raise SystemExit(1) from erro
