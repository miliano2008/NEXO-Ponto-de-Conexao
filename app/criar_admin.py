"""Cria (ou promove) um administrador do NEXO.

Executar: scripts\CRIAR_ADMIN.bat  ou  python -m app.criar_admin
Se o CPF/CNPJ já estiver cadastrado, o usuário é promovido a Administrador.
"""

from getpass import getpass

from app import auth

auth.iniciar_banco()
print("NEXO — criação de administrador\n")
try:
    documento = input("CPF ou CNPJ: ")
    doc, tipo = auth.validar_documento(documento)
    existente = auth.buscar_por_documento(doc)
    if existente:
        usuario = auth.alterar_usuario(existente["id"], cargo="administrador", ativo=True, por="criar_admin.py")
        if not usuario["email_confirmado"]:
            usuario = auth.confirmar_email_manual(existente["id"], por="criar_admin.py")
        print(f"\n{usuario['nome']} ({usuario['documento']}) agora é Administrador.")
    else:
        nome = input("Nome completo / razão social: ")
        email = input("E-mail (usado na recuperação de senha): ")
        telefone = input("Telefone com DDD, ex.: (11) 91234-5678: ")
        senha = getpass("Senha (mín. 8, letras e números): ")
        confirmacao = getpass("Confirme a senha: ")
        # criado no próprio computador do responsável: e-mail já considerado confirmado
        usuario = auth.cadastrar(doc, nome, email, telefone, senha, confirmacao,
                                 cargo="administrador", email_confirmado=True)
        auth.registrar("admin_criado", doc, "criar_admin.py")
        print(f"\nAdministrador {usuario['nome']} ({usuario['documento']}) criado.")
except auth.ErroAuth as erro:
    print("Erro:", erro)
    raise SystemExit(1) from erro
