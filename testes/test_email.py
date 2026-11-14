"""Testes do envio de e-mail com um servidor SMTP falso que imita as respostas do Gmail.

Executar (na raiz do projeto): python -m testes.test_email
Nada sai para a internet: o servidor falso roda neste computador, numa porta livre.
Cobre o erro que confundia o grupo: quando o Gmail recusa a senha e fecha a conexão,
o motivo real (senha recusada, tentativas demais) precisa aparecer, e não só
"Connection unexpectedly closed".
"""
import email
import email.policy
import os
import socket
import sys
import threading

os.environ["NEXO_BANCO"] = "local"
for _chave in [k for k in os.environ if k.startswith(("DB_", "SMTP_", "APP_URL", "GOOGLE_"))]:
    del os.environ[_chave]

import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

from banco import conexao as db  # noqa: E402

db.SQLITE = Path(tempfile.mkdtemp()) / "email.db"   # o diagnóstico não toca no banco real
from app import envio_email  # noqa: E402
from nucleo import configuracao  # noqa: E402

SENHA_RECUSADA = (b"535-5.7.8 Username and Password not accepted. For more information, go to\r\n"
                  b"535 5.7.8  https://support.google.com/mail/?p=BadCredentials\r\n")
TENTATIVAS_DEMAIS = b"454 4.7.0 Too many login attempts, please try again later.\r\n"


class ServidorFalso:
    """Responde como o Gmail. `auth` = resposta ao login (None aceita); depois de recusar, fecha."""

    def __init__(self, auth=None, fechar_no_inicio=False):
        self.auth, self.fechar_no_inicio = auth, fechar_no_inicio
        self.conexoes, self.metodos, self.recebidos = 0, [], []
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.porta = self.sock.getsockname()[1]
        threading.Thread(target=self._aceitar, daemon=True).start()

    def _aceitar(self):
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            self.conexoes += 1
            threading.Thread(target=self._atender, args=(c,), daemon=True).start()

    def _atender(self, c):
        if self.fechar_no_inicio:
            c.close()
            return
        f = c.makefile("rb")
        c.sendall(b"220 smtp.falso ESMTP\r\n")
        while (linha := f.readline()):
            cmd = linha.strip().upper()
            if cmd.startswith((b"EHLO", b"HELO")):
                c.sendall(b"250-smtp.falso\r\n250-AUTH LOGIN PLAIN XOAUTH2\r\n250 8BITMIME\r\n")
            elif cmd.startswith(b"AUTH"):
                self.metodos.append(cmd.split()[1].decode())
                if self.auth:
                    c.sendall(self.auth)
                    c.close()          # o Gmail encerra a conexão depois de recusar
                    return
                c.sendall(b"235 2.7.0 Accepted\r\n")
            elif cmd == b"DATA":
                c.sendall(b"354 go\r\n")
                corpo = []
                while (l := f.readline()).strip() != b".":
                    corpo.append(l)
                self.recebidos.append(b"".join(corpo).decode(errors="replace"))
                c.sendall(b"250 queued\r\n")
            elif cmd.startswith(b"QUIT"):
                c.sendall(b"221 bye\r\n")
                c.close()
                return
            else:
                c.sendall(b"250 ok\r\n")


def usar(servidor):
    os.environ.update(SMTP_HOST="127.0.0.1", SMTP_PORT=str(servidor.porta), SMTP_SECURITY="nenhuma",
                      SMTP_USER="nexo.projeto@gmail.com", SMTP_PASSWORD="abcdefghijklmnop")


def erro_de(funcao):
    try:
        funcao()
    except envio_email.ErroEmail as erro:
        return str(erro)
    raise AssertionError("deveria ter falhado")


# as variáveis de ambiente valem também para as chaves SMTP_*
assert configuracao.CHAVES and "SMTP_HOST" in configuracao.CHAVES

# 1. senha recusada: diz que é a senha (antes aparecia "fechou a conexão... não é a senha")
s = ServidorFalso(auth=SENHA_RECUSADA)
usar(s)
msg = erro_de(envio_email.testar_login)
assert "RECUSOU o usuário ou a senha" in msg and "535" in msg and "não é a senha" not in msg.lower(), msg
assert s.metodos == ["PLAIN"]                       # uma tentativa só: não esconde o motivo real

# 2. tentativas demais (bloqueio temporário do Gmail)
s = ServidorFalso(auth=TENTATIVAS_DEMAIS)
usar(s)
msg = erro_de(envio_email.testar_login)
assert "TENTATIVAS DEMAIS" in msg and "454" in msg, msg

# 3. servidor/rede derruba a conexão logo no início (porta errada, antivírus, rede bloqueada)
s = ServidorFalso(fechar_no_inicio=True)
usar(s)
msg = erro_de(envio_email.testar_login)
assert "logo no início" in msg and "hotspot" in msg, msg

# 4. porta fechada
livre = socket.socket()
livre.bind(("127.0.0.1", 0))
porta_fechada = livre.getsockname()[1]
livre.close()
os.environ["SMTP_PORT"] = str(porta_fechada)
assert "não foi possível conectar" in erro_de(envio_email.testar_login)

# 5. tudo certo: login e envio de verdade para o servidor falso
s = ServidorFalso()
usar(s)
assert envio_email.testar_login()["usuario"] == "nexo.projeto@gmail.com"
envio_email.enviar_confirmacao("ana@exemplo.com", "Ana", "http://127.0.0.1:5000/confirmar?token=abc", 24)
assert len(s.recebidos) == 1
mensagem = email.message_from_string(s.recebidos[0], policy=email.policy.default)
assert mensagem["Subject"] == "NEXO — Confirme seu e-mail" and mensagem["To"] == "ana@exemplo.com"
assert "confirmar?token=abc" in mensagem.get_body(("plain",)).get_content()

# 6. o iniciar.bat (diagnóstico rápido) não faz login no Gmail a cada abertura
s = ServidorFalso(auth=SENHA_RECUSADA)
usar(s)
sys.argv = ["diagnostico", "--rapido"]
from app import diagnostico  # noqa: E402

diagnostico.RAPIDO = True
diagnostico.main()
assert s.conexoes == 0, "o diagnóstico rápido não deveria conectar ao servidor de e-mail"
assert not diagnostico.erros, diagnostico.erros
print("TESTES OK: e-mail — senha recusada, tentativas demais, conexão derrubada, porta fechada, envio e "
      "diagnóstico rápido sem login.")
