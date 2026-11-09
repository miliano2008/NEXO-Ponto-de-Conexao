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


def _explicar(erro):
    """Traduz os erros mais comuns do SMTP (principalmente do Gmail)."""
    texto = str(erro)
    if isinstance(erro, smtplib.SMTPAuthenticationError) or "535" in texto:
        return ("o servidor recusou usuário/senha. No Gmail, use a SENHA DE APP de 16 letras "
                "(myaccount.google.com/apppasswords), não a senha normal, com a verificação em duas etapas ativa.")
    if isinstance(erro, (TimeoutError, ConnectionRefusedError, OSError)) and not isinstance(erro, smtplib.SMTPException):
        return f"não foi possível conectar ao servidor de e-mail ({texto}). Confira servidor/porta e a internet."
    return texto


def _conectar(c):
    contexto = ssl.create_default_context()
    if c["seguranca"] == "ssl":
        servidor = smtplib.SMTP_SSL(c["host"], c["porta"], context=contexto, timeout=20)
    else:
        servidor = smtplib.SMTP(c["host"], c["porta"], timeout=20)
    try:
        if c["seguranca"] == "starttls":
            servidor.starttls(context=contexto)
        if c["usuario"]:
            servidor.login(c["usuario"], c["senha"])
    except Exception:
        servidor.close()
        raise
    return servidor


def testar_login():
    """Conecta e faz login no servidor de e-mail, sem enviar nada."""
    c = configuracao()
    try:
        with _conectar(c):
            pass
    except (smtplib.SMTPException, OSError) as erro:
        raise ErroEmail(f"Falha no e-mail: {_explicar(erro)}") from erro
    return c


def enviar(destino, assunto, texto, html=None):
    c = configuracao()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = c["remetente"], destino, assunto
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        with _conectar(c) as servidor:
            servidor.send_message(msg)
    except (smtplib.SMTPException, OSError) as erro:
        raise ErroEmail(f"Falha ao enviar e-mail: {_explicar(erro)}") from erro


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
