"""NEXO — autenticação: usuários, cargos, e-mail e recuperação de senha.

Banco: MySQL (Aiven) se configurado (.env ou config.ini), senão SQLite em banco/dados/nexo.db.
A conexão fica em banco/conexao.py e as tabelas em banco/migracoes.py.

Regras de segurança:
- login com CPF/CNPJ + senha juntos; qualquer falha responde a mesma mensagem
  ("CPF/CNPJ ou senha inválidos"), sem revelar se o documento tem cadastro;
- novos usuários só entram depois de confirmar o e-mail pelo link enviado;
- links (confirmação e redefinição) são guardados só como hash e têm validade;
- cargos podem vir de códigos de convite gerados pelo administrador.
"""

import hashlib
import re
import secrets
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from banco import conexao as db
from banco import migracoes
from banco.conexao import conectar


MAX_TENTATIVAS = 5
BLOQUEIO_MINUTOS = 15
VALIDADE_TOKEN_MINUTOS = 30          # link de redefinição de senha
VALIDADE_CONFIRMACAO_HORAS = 24      # link de confirmação de e-mail
INTERVALO_ENVIO_SEGUNDOS = 60        # mínimo entre dois e-mails do mesmo tipo
MENSAGEM_LOGIN_INVALIDO = "CPF/CNPJ ou senha inválidos."

CARGOS = {
    "administrador": "Administrador",
    "analista": "Analista",
    "auditor": "Auditor",
    "visualizador": "Visualizador",
}
CARGO_PADRAO = "visualizador"

# Permissão → cargos que a possuem. A interface e a API usam a mesma tabela.
PERMISSOES = {
    "consultar":          {"administrador", "analista", "auditor", "visualizador"},
    "relatorios":         {"administrador", "analista", "auditor"},
    "exportar":           {"administrador", "analista", "auditor"},
    "simular":            {"administrador", "analista"},
    "configurar":         {"administrador", "analista"},
    "ver_auditoria":      {"administrador", "auditor"},
    "gerenciar_usuarios": {"administrador"},
}

# Comparar a senha com um hash qualquer quando o CPF não existe deixa a resposta
# com o mesmo tempo de um usuário real (não dá para descobrir cadastros pelo tempo).
_HASH_FICTICIO = generate_password_hash("nexo-sem-usuario")


class ErroAuth(ValueError):
    """Erro de regra de negócio, com mensagem pronta para o usuário."""


class EmailNaoConfirmado(ErroAuth):
    """Senha correta, mas o e-mail do cadastro ainda não foi confirmado."""

    def __init__(self, email):
        super().__init__(f"Confirme seu e-mail para entrar. Enviamos um link para {mascarar_email(email)}.")
        self.email = email


def agora():
    return datetime.now().replace(microsecond=0)


def para_data(valor):
    """DATETIME do MySQL chega como datetime; o SQLite guarda texto ISO."""
    if valor is None or isinstance(valor, datetime):
        return valor
    return datetime.fromisoformat(str(valor))


def para_texto(valor):
    return para_data(valor).isoformat() if valor else None


def iniciar_banco(registrar_migracao=None):
    """Cria/atualiza as tabelas pelas migrações numeradas (banco/migracoes.py)."""
    migracoes.aplicar(registrar=registrar_migracao)


def registrar(evento, documento=None, detalhe=None, ip=None):
    with conectar() as c:
        c.execute("INSERT INTO auditoria (data, evento, documento, detalhe, ip) VALUES (?, ?, ?, ?, ?)",
                  (agora().isoformat(), evento, documento, (detalhe or "")[:255] or None, ip))


# ---------------------------------------------------------------- documentos

def somente_digitos(texto):
    return re.sub(r"\D", "", str(texto or ""))


def _digito(numeros, pesos):
    resto = sum(int(n) * p for n, p in zip(numeros, pesos)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cpf_valido(cpf):
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    d1 = _digito(cpf[:9], range(10, 1, -1))
    d2 = _digito(cpf[:9] + d1, range(11, 1, -1))
    return cpf[-2:] == d1 + d2


def cnpj_valido(cnpj):
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = _digito(cnpj[:12], pesos1)
    d2 = _digito(cnpj[:12] + d1, [6] + pesos1)
    return cnpj[-2:] == d1 + d2


def validar_documento(texto):
    """Retorna (documento_só_dígitos, 'CPF' | 'CNPJ') ou lança ErroAuth."""
    doc = somente_digitos(texto)
    if len(doc) == 11 and cpf_valido(doc):
        return doc, "CPF"
    if len(doc) == 14 and cnpj_valido(doc):
        return doc, "CNPJ"
    raise ErroAuth("Informe um CPF (11 dígitos) ou CNPJ (14 dígitos) válido.")


def mascarar(doc):
    if len(doc) == 11:
        return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"


# ---------------------------------------------------------------- senha / e-mail / telefone

def validar_senha(senha):
    if len(senha) < 8 or not re.search(r"[A-Za-z]", senha) or not re.search(r"\d", senha):
        raise ErroAuth("A senha precisa ter ao menos 8 caracteres, com letras e números.")


def validar_email(email):
    email = str(email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 190:
        raise ErroAuth("Informe um e-mail válido.")
    return email


def mascarar_email(email):
    nome, dominio = email.split("@", 1)
    return f"{nome[:2]}{'*' * max(len(nome) - 2, 1)}@{dominio}"


def validar_telefone(texto):
    """Telefone brasileiro com DDD: fixo (10 dígitos) ou celular (11, começando com 9)."""
    tel = somente_digitos(texto)
    if tel.startswith("55") and len(tel) in (12, 13):
        tel = tel[2:]
    valido = (len(tel) in (10, 11) and tel[0] != "0" and tel[1] != "0"
              and (len(tel) == 10 or tel[2] == "9"))
    if not valido:
        raise ErroAuth("Informe um telefone válido com DDD, ex.: (11) 91234-5678.")
    return tel


def formatar_telefone(tel):
    if not tel:
        return None
    return f"({tel[:2]}) {tel[2:-4]}-{tel[-4:]}"


# ---------------------------------------------------------------- usuários

def publico(linha):
    """Dados do usuário que podem ir para a interface (sem hash de senha)."""
    if linha is None:
        return None
    cargo = linha["cargo"]
    return {
        "id": linha["id"], "documento": mascarar(linha["documento"]),
        "tipo_documento": linha["tipo_documento"], "nome": linha["nome"],
        "email": linha["email"], "email_confirmado": bool(linha["email_confirmado"]),
        "telefone": formatar_telefone(linha["telefone"]),
        "cargo": cargo, "cargo_nome": CARGOS[cargo],
        "ativo": bool(linha["ativo"]), "criado_em": para_texto(linha["criado_em"]),
        "ultimo_login": para_texto(linha["ultimo_login"]),
        "permissoes": sorted(p for p, cargos in PERMISSOES.items() if cargo in cargos),
    }


def buscar_por_documento(doc):
    with conectar() as c:
        return c.execute("SELECT * FROM usuarios WHERE documento = ?", (doc,)).fetchone()


def buscar_por_id(uid):
    with conectar() as c:
        return c.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()


def cadastrar(documento, nome, email, telefone, senha, confirmacao, cargo=CARGO_PADRAO,
              convite=None, email_confirmado=False, ip=None):
    """Cria o usuário. Com código de convite, o cargo vem do convite."""
    doc, tipo = validar_documento(documento)
    nome = str(nome or "").strip()
    if len(nome) < 3:
        raise ErroAuth("Informe o nome completo ou a razão social.")
    email = validar_email(email)
    tel = validar_telefone(telefone)
    if senha != confirmacao:
        raise ErroAuth("A confirmação não confere com a senha.")
    validar_senha(senha)
    if cargo not in CARGOS:
        raise ErroAuth("Cargo inválido.")
    codigo = str(convite or "").strip()
    try:
        with conectar() as c:
            # convite e usuário na MESMA transação: se o cadastro falhar, o uso não é contado
            id_convite = None
            if codigo:
                id_convite, cargo = _usar_convite(c, codigo)
            cursor = c.execute(
                "INSERT INTO usuarios (documento, tipo_documento, nome, email, telefone, email_confirmado, "
                "senha_hash, cargo, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (doc, tipo, nome, email, tel, int(email_confirmado), generate_password_hash(senha),
                 cargo, agora().isoformat()))
            uid = cursor.lastrowid
    except db.ErroIntegridade as erro:
        raise ErroAuth("Não foi possível concluir o cadastro: CPF/CNPJ ou e-mail já utilizado. "
                       "Se você já tem conta, use “Esqueci minha senha”.") from erro
    registrar("cadastro", doc, f"cargo={cargo}" + (f" convite={id_convite}" if id_convite else ""), ip)
    return publico(buscar_por_id(uid))


def _verificar_credenciais(documento, senha, ip):
    """Confere CPF/CNPJ + senha. Qualquer falha gera a MESMA mensagem."""
    try:
        doc, _ = validar_documento(documento)
    except ErroAuth:
        raise ErroAuth(MENSAGEM_LOGIN_INVALIDO) from None
    linha = buscar_por_documento(doc)
    if linha is None:
        check_password_hash(_HASH_FICTICIO, senha or "")
        registrar("login_falhou", doc, "documento não cadastrado", ip)
        raise ErroAuth(MENSAGEM_LOGIN_INVALIDO)
    if not linha["ativo"]:
        check_password_hash(linha["senha_hash"], senha or "")
        registrar("login_negado_inativo", doc, ip=ip)
        raise ErroAuth(MENSAGEM_LOGIN_INVALIDO)
    if linha["bloqueado_ate"] and para_data(linha["bloqueado_ate"]) > agora():
        registrar("login_bloqueado", doc, f"até {para_data(linha['bloqueado_ate']):%H:%M}", ip)
        raise ErroAuth(MENSAGEM_LOGIN_INVALIDO)
    if not check_password_hash(linha["senha_hash"], senha or ""):
        falhas = linha["tentativas_falhas"] + 1
        bloqueio = (agora() + timedelta(minutes=BLOQUEIO_MINUTOS)).isoformat() if falhas >= MAX_TENTATIVAS else None
        with conectar() as c:
            c.execute("UPDATE usuarios SET tentativas_falhas = ?, bloqueado_ate = ? WHERE id = ?",
                      (0 if bloqueio else falhas, bloqueio, linha["id"]))
        registrar("login_falhou", doc, f"tentativa {falhas}" + (" (bloqueado)" if bloqueio else ""), ip)
        raise ErroAuth(MENSAGEM_LOGIN_INVALIDO)
    return linha


def autenticar(documento, senha, ip=None):
    linha = _verificar_credenciais(documento, senha, ip)
    if not linha["email_confirmado"]:
        registrar("login_email_pendente", linha["documento"], ip=ip)
        raise EmailNaoConfirmado(linha["email"])
    with conectar() as c:
        c.execute("UPDATE usuarios SET tentativas_falhas = 0, bloqueado_ate = NULL, ultimo_login = ? WHERE id = ?",
                  (agora().isoformat(), linha["id"]))
    registrar("login", linha["documento"], ip=ip)
    return publico(buscar_por_id(linha["id"]))


def tem_permissao(usuario, permissao):
    return usuario is not None and usuario["cargo"] in PERMISSOES[permissao]


# ---------------------------------------------------------------- links por e-mail (tokens)

def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _criar_token(c, usuario_id, tipo, validade):
    """Cria um link novo e invalida os anteriores do mesmo tipo.

    Retorna None se outro link do mesmo tipo foi criado há menos de 1 minuto.
    """
    ultimo = c.execute("SELECT MAX(criado_em) AS ultimo FROM tokens_recuperacao WHERE usuario_id = ? AND tipo = ?",
                       (usuario_id, tipo)).fetchone()["ultimo"]
    if ultimo and para_data(ultimo) > agora() - timedelta(seconds=INTERVALO_ENVIO_SEGUNDOS):
        return None
    token = secrets.token_urlsafe(32)
    c.execute("UPDATE tokens_recuperacao SET usado = 1 WHERE usuario_id = ? AND tipo = ? AND usado = 0",
              (usuario_id, tipo))
    c.execute("INSERT INTO tokens_recuperacao (usuario_id, tipo, token_hash, expira_em, criado_em) "
              "VALUES (?, ?, ?, ?, ?)",
              (usuario_id, tipo, _hash_token(token), (agora() + validade).isoformat(), agora().isoformat()))
    return token


def _token_valido(c, token, tipo):
    linha = c.execute("SELECT * FROM tokens_recuperacao WHERE token_hash = ? AND tipo = ?",
                      (_hash_token(token or ""), tipo)).fetchone()
    if linha is None or linha["usado"] or para_data(linha["expira_em"]) < agora():
        raise ErroAuth("Link inválido ou expirado. Solicite um novo." if tipo == "senha"
                       else "Link de confirmação inválido ou expirado. Faça login para receber outro.")
    return linha


def criar_token_recuperacao(documento):
    """Retorna (usuario, token) ou (None, None).

    (None, None) quando não há cadastro ativo OU um link acabou de ser enviado: quem
    chama responde a mesma mensagem nos dois casos, sem revelar se o CPF existe.
    """
    try:
        doc, _ = validar_documento(documento)
    except ErroAuth:
        return None, None
    linha = buscar_por_documento(doc)
    if linha is None or not linha["ativo"]:
        return None, None
    with conectar() as c:
        token = _criar_token(c, linha["id"], "senha", timedelta(minutes=VALIDADE_TOKEN_MINUTOS))
    return (linha, token) if token else (None, None)


def verificar_token(token):
    with conectar() as c:
        return publico(buscar_por_id(_token_valido(c, token, "senha")["usuario_id"]))


def redefinir_senha(token, senha, confirmacao, ip=None):
    if senha != confirmacao:
        raise ErroAuth("A confirmação não confere com a senha.")
    validar_senha(senha)
    with conectar() as c:
        registro = _token_valido(c, token, "senha")
        # o link chegou no e-mail do cadastro: abri-lo também comprova o e-mail
        c.execute("UPDATE usuarios SET senha_hash = ?, tentativas_falhas = 0, bloqueado_ate = NULL, "
                  "email_confirmado = 1 WHERE id = ?", (generate_password_hash(senha), registro["usuario_id"]))
        c.execute("UPDATE tokens_recuperacao SET usado = 1 WHERE id = ?", (registro["id"],))
    usuario = buscar_por_id(registro["usuario_id"])
    registrar("senha_redefinida", usuario["documento"], ip=ip)
    return publico(usuario)


def definir_senha_manual(uid, senha, confirmacao, por):
    """Troca a senha direto no banco (usado por criar_admin.py, para quem ficou sem acesso).
    Desbloqueia a conta e fica na auditoria."""
    if senha != confirmacao:
        raise ErroAuth("A confirmação não confere com a senha.")
    validar_senha(senha)
    with conectar() as c:
        c.execute("UPDATE usuarios SET senha_hash = ?, tentativas_falhas = 0, bloqueado_ate = NULL WHERE id = ?",
                  (generate_password_hash(senha), uid))
    usuario = buscar_por_id(uid)
    registrar("senha_redefinida", usuario["documento"], f"manual por {por}")
    return publico(usuario)


def criar_token_confirmacao(uid):
    """Link de confirmação de e-mail (24 h). Lança ErroAuth se pedido há menos de 1 min."""
    with conectar() as c:
        token = _criar_token(c, uid, "email", timedelta(hours=VALIDADE_CONFIRMACAO_HORAS))
    if token is None:
        raise ErroAuth("Um e-mail de confirmação acabou de ser enviado. Aguarde 1 minuto para pedir outro.")
    return token


def confirmar_email(token, ip=None):
    with conectar() as c:
        registro = _token_valido(c, token, "email")
        c.execute("UPDATE usuarios SET email_confirmado = 1 WHERE id = ?", (registro["usuario_id"],))
        c.execute("UPDATE tokens_recuperacao SET usado = 1 WHERE id = ?", (registro["id"],))
    usuario = buscar_por_id(registro["usuario_id"])
    registrar("email_confirmado", usuario["documento"], usuario["email"], ip)
    return publico(usuario)


def preparar_reenvio_confirmacao(documento, senha, ip=None):
    """Só quem sabe a senha pode pedir outro link de confirmação. Retorna (usuario, token)."""
    linha = _verificar_credenciais(documento, senha, ip)
    if linha["email_confirmado"]:
        raise ErroAuth("Seu e-mail já está confirmado. Faça login normalmente.")
    return linha, criar_token_confirmacao(linha["id"])


# ---------------------------------------------------------------- códigos de convite

_ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sem 0/O, 1/I/L: fáceis de confundir


def _normalizar_codigo(codigo):
    return re.sub(r"[^A-Z0-9]", "", str(codigo or "").upper()).removeprefix("NEXO")


def criar_convite(cargo, dias=7, max_usos=5, por=None):
    """Gera um código para entrar já com o cargo. O código só é mostrado agora."""
    if cargo not in CARGOS:
        raise ErroAuth("Cargo inválido.")
    if not 1 <= int(dias) <= 30 or not 1 <= int(max_usos) <= 50:
        raise ErroAuth("Validade de 1 a 30 dias e de 1 a 50 usos.")
    corpo = "".join(secrets.choice(_ALFABETO) for _ in range(8))
    codigo = f"NEXO-{corpo[:4]}-{corpo[4:]}"
    with conectar() as c:
        c.execute("INSERT INTO convites (codigo_hash, prefixo, cargo, max_usos, expira_em, criado_por, criado_em) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (_hash_token(corpo), corpo[:4], cargo, int(max_usos),
                   (agora() + timedelta(days=int(dias))).isoformat(), por, agora().isoformat()))
    registrar("convite_criado", None, f"{cargo} · {max_usos} uso(s) · {dias} dia(s) · NEXO-{corpo[:4]}-**** · por={por}")
    return codigo


def _usar_convite(c, codigo):
    """Valida e consome 1 uso do convite dentro da transação do cadastro."""
    corpo = _normalizar_codigo(codigo)
    linha = c.execute("SELECT * FROM convites WHERE codigo_hash = ?", (_hash_token(corpo),)).fetchone()
    invalido = ErroAuth("Código de convite inválido, expirado ou esgotado. Confira com o administrador "
                        "ou deixe o campo em branco para entrar como Visualizador.")
    if (linha is None or linha["revogado"] or linha["usos"] >= linha["max_usos"]
            or para_data(linha["expira_em"]) < agora()):
        raise invalido
    # "usos < max_usos" no UPDATE impede passar do limite com dois cadastros ao mesmo tempo
    if c.execute("UPDATE convites SET usos = usos + 1 WHERE id = ? AND usos < max_usos",
                 (linha["id"],)).rowcount != 1:
        raise invalido
    return linha["id"], linha["cargo"]


def listar_convites():
    with conectar() as c:
        linhas = c.execute("SELECT * FROM convites ORDER BY id DESC").fetchall()
    resultado = []
    for l in linhas:
        expirado = para_data(l["expira_em"]) < agora()
        situacao = ("Revogado" if l["revogado"] else "Esgotado" if l["usos"] >= l["max_usos"]
                    else "Expirado" if expirado else "Ativo")
        resultado.append({"id": l["id"], "codigo": f"NEXO-{l['prefixo']}-****", "cargo": l["cargo"],
                          "cargo_nome": CARGOS.get(l["cargo"], l["cargo"]), "usos": l["usos"],
                          "max_usos": l["max_usos"], "expira_em": para_texto(l["expira_em"]),
                          "criado_por": l["criado_por"], "situacao": situacao})
    return resultado


def revogar_convite(id_convite, por=None):
    with conectar() as c:
        if c.execute("UPDATE convites SET revogado = 1 WHERE id = ?", (id_convite,)).rowcount != 1:
            raise ErroAuth("Convite não encontrado.")
    registrar("convite_revogado", None, f"convite={id_convite} por={por}")


# ---------------------------------------------------------------- administração

def listar_usuarios():
    with conectar() as c:
        return [publico(l) for l in c.execute("SELECT * FROM usuarios ORDER BY nome").fetchall()]


def contar_administradores_ativos():
    with conectar() as c:
        return c.execute("SELECT COUNT(*) AS n FROM usuarios WHERE cargo = 'administrador' AND ativo = 1").fetchone()["n"]


def alterar_usuario(uid, cargo=None, ativo=None, por=None):
    linha = buscar_por_id(uid)
    if linha is None:
        raise ErroAuth("Usuário não encontrado.")
    novo_cargo = cargo if cargo is not None else linha["cargo"]
    novo_ativo = int(ativo) if ativo is not None else linha["ativo"]
    if novo_cargo not in CARGOS:
        raise ErroAuth("Cargo inválido.")
    perde_admin = linha["cargo"] == "administrador" and linha["ativo"] and (novo_cargo != "administrador" or not novo_ativo)
    if perde_admin and contar_administradores_ativos() <= 1:
        raise ErroAuth("O sistema precisa de pelo menos um administrador ativo.")
    with conectar() as c:
        c.execute("UPDATE usuarios SET cargo = ?, ativo = ? WHERE id = ?", (novo_cargo, novo_ativo, uid))
    registrar("usuario_alterado", linha["documento"], f"cargo={novo_cargo} ativo={novo_ativo} por={por}")
    return publico(buscar_por_id(uid))


def alterar_contato(uid, email=None, telefone=None, por=None):
    """Administrador troca e-mail/telefone (ex.: usuário perdeu acesso ao e-mail).

    Um e-mail novo volta a ficar pendente até ser confirmado pelo link (ou manualmente).
    Retorna (usuario, email_mudou).
    """
    linha = buscar_por_id(uid)
    if linha is None:
        raise ErroAuth("Usuário não encontrado.")
    novo_email = validar_email(email) if email else linha["email"]
    novo_tel = validar_telefone(telefone) if telefone else linha["telefone"]
    email_mudou = novo_email != linha["email"]
    try:
        with conectar() as c:
            c.execute("UPDATE usuarios SET email = ?, telefone = ?, email_confirmado = ? WHERE id = ?",
                      (novo_email, novo_tel, 0 if email_mudou else linha["email_confirmado"], uid))
    except db.ErroIntegridade as erro:
        raise ErroAuth("Este e-mail já pertence a outro usuário.") from erro
    detalhe = (f"email {mascarar_email(linha['email'])} → {mascarar_email(novo_email)}" if email_mudou else "")
    if novo_tel != linha["telefone"]:
        detalhe += f" telefone → {formatar_telefone(novo_tel)}"
    registrar("contato_alterado", linha["documento"], f"{detalhe.strip()} por={por}")
    return publico(buscar_por_id(uid)), email_mudou


def confirmar_email_manual(uid, por=None):
    linha = buscar_por_id(uid)
    if linha is None:
        raise ErroAuth("Usuário não encontrado.")
    with conectar() as c:
        c.execute("UPDATE usuarios SET email_confirmado = 1 WHERE id = ?", (uid,))
        c.execute("UPDATE tokens_recuperacao SET usado = 1 WHERE usuario_id = ? AND tipo = 'email'", (uid,))
    registrar("email_confirmado_manual", linha["documento"], f"por={por}")
    return publico(buscar_por_id(uid))


def listar_auditoria(limite=200):
    with conectar() as c:
        linhas = c.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    return [{**dict(l), "data": para_texto(l["data"]),
             "documento": mascarar(l["documento"]) if l["documento"] else None} for l in linhas]
