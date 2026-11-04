"""NEXO — assistente de configuração do banco (Aiven) e do e-mail.

Executar: scripts\\CONFIGURAR.bat  ou  python -m app.configurar
Faz as perguntas, grava o .env na raiz do projeto, copia o ca.pem para banco/dados/
e testa a conexão. Nenhum arquivo precisa ser editado à mão.

Quem já tinha o config.ini da versão 0.3: os valores dele aparecem como padrão
(entre colchetes) e, ao final, passam para o .env; o config.ini vira config.ini.bak.
"""

import shutil
import subprocess
import sys
from getpass import getpass
from pathlib import Path

from nucleo import configuracao

CA_DESTINO = configuracao.PASTA_DADOS / "ca.pem"


def perguntar(texto, atual=""):
    sufixo = f" [{atual}]" if atual else ""
    resposta = input(f"{texto}{sufixo}: ").strip()
    return resposta or atual


def mascarar(senha):
    return f"{len(senha)} caracteres, começa com '{senha[:4]}' e termina com '{senha[-2:]}'"


def pedir_senha(atual, rotulo="Password", origem="Aiven", prefixo="AVNS_", sem_espacos=False):
    """Pede a senha escondida; nunca aceita vazio quando ainda não há senha salva."""
    while True:
        dica = "Enter mantém a atual" if atual else "obrigatória"
        senha = getpass(f"{rotulo} (não aparece na tela; {dica}): ").strip()
        if not senha and atual:
            return atual
        if not senha:
            print("  Nenhuma senha foi recebida. No terminal do Windows, cole com o BOTÃO DIREITO do mouse.")
            if perguntar("  Prefere digitar/colar com a senha VISÍVEL? (s/n)", "s").lower().startswith("s"):
                senha = input(f"  {rotulo} (visível): ").strip()
            if not senha:
                continue
        if sem_espacos:
            senha = senha.replace(" ", "")  # o Google mostra a senha de app em 4 blocos com espaços
        print(f"  Senha recebida: {mascarar(senha)}.")
        if prefixo and not senha.startswith(prefixo):
            print(f"  Atenção: as senhas do {origem} costumam começar com '{prefixo}'. Confira se copiou a senha certa.")
        if sem_espacos and len(senha) != 16:
            print(f"  Atenção: a senha de app do Google tem 16 letras; esta tem {len(senha)}.")
        if perguntar(f"  Confere com a senha do {origem}? (s/n)", "s").lower().startswith("s"):
            return senha


def achar_ca():
    """Procura o ca.pem baixado do Aiven nas pastas mais comuns."""
    pastas = [configuracao.RAIZ, configuracao.PASTA_DADOS, configuracao.RAIZ / "dados", Path.home() / "Downloads",
              Path.home() / "Transferências", Path.home() / "Desktop", Path.home() / "Área de Trabalho"]
    for pasta in pastas:
        if pasta.exists():
            for arquivo in sorted(pasta.glob("ca*.pem"), key=lambda a: a.stat().st_mtime, reverse=True):
                return arquivo
    return None


def mostrar_falha_banco(v, erro):
    print(f"  [ERRO] {erro}")
    print("\n  Dados usados na tentativa (compare com o Aiven → Overview → Connection information):")
    print(f"    Host:     {v.get('DB_HOST')}")
    print(f"    Port:     {v.get('DB_PORT')}")
    print(f"    User:     {v.get('DB_USER')}")
    print(f"    Password: {mascarar(v['DB_PASSWORD']) if v.get('DB_PASSWORD') else 'VAZIA'}")
    if "senha incorretos" in str(erro):
        print("\n  Causas mais comuns:")
        print("   1. A senha não foi colada (no Windows, cole com o botão direito do mouse).")
        print("   2. A senha foi copiada de outro serviço, ou foi trocada no Aiven ('Reset password').")
        print("   3. O User não é o do Aiven (normalmente 'avnadmin').")
        print("   4. Um caractere trocado: l (L minúsculo), I (i maiúsculo) e 1 (um) se confundem.")
        if v.get("DB_PASSWORD") and perguntar("\n  Mostrar a senha salva para comparar com o Aiven? (s/n)",
                                              "s").lower().startswith("s"):
            print(f"\n    Senha salva: {v['DB_PASSWORD']}\n")
            for i, ch in enumerate(v["DB_PASSWORD"], 1):
                tipo = ("número" if ch.isdigit() else "MAIÚSCULA" if ch.isupper()
                        else "minúscula" if ch.islower() else "símbolo")
                print(f"    {i:2d}. {ch}  ({tipo})")
            print("\n  No Aiven, clique no olho da Password e confira posição por posição.")
    print("\n  Rode de novo: scripts\\CONFIGURAR.bat  (Enter mantém o que já está certo)")


def testar_banco(v):
    from banco import conexao as db
    print("\nTestando a conexão com o Aiven...")
    try:
        conexao = db.conectar_mysql(com_banco=False)
        with conexao.cursor() as cur:
            cur.execute("SELECT VERSION() AS v")
            print(f"  Conectado! MySQL {cur.fetchone()['v']}")
            cur.execute("SELECT COUNT(*) AS n FROM information_schema.tables "
                        "WHERE table_schema = %s AND table_name = 'contas'", (v["DB_NAME"],))
            n_contas = 0
            if cur.fetchone()["n"]:
                cur.execute(f"SELECT COUNT(*) AS n FROM `{v['DB_NAME']}`.contas")
                n_contas = cur.fetchone()["n"]
        conexao.close()
        if n_contas:
            print(f"  O banco do grupo já tem os dados ({n_contas} contas). Nada a exportar.")
        elif perguntar("Criar o banco e exportar as 40 contas / 160 transações agora? (s/n)", "s").lower().startswith("s"):
            subprocess.run([sys.executable, "-m", "banco.migrar_mysql"], cwd=configuracao.RAIZ, check=False)
    except Exception as erro:  # noqa: BLE001 — mostrar qualquer falha ao usuário
        mostrar_falha_banco(v, erro)


def testar_email(usuario):
    destino = perguntar("\nEnviar um e-mail de teste para qual endereço? (Enter pula)", usuario)
    if not destino:
        return
    from app import envio_email
    try:
        envio_email.enviar(destino, "NEXO — teste de e-mail", "O envio de e-mails do NEXO está funcionando.")
        print(f"  E-mail de teste enviado para {destino}. Confira a caixa de entrada (e o spam).")
    except envio_email.ErroEmail as erro:
        print(f"  [ERRO] {erro}")
        print("  Rode o scripts\\CONFIGURAR.bat de novo para corrigir (Enter mantém o que está certo).")


def main():
    v = configuracao.valores()           # .env + config.ini antigo, já combinados
    v.setdefault("APP_URL_BASE", "http://127.0.0.1:5000")

    print("=== NEXO — configuração ===")
    print("Aperte Enter para manter o valor mostrado entre [colchetes].\n")

    # ------------------------------------------------------------ MySQL / Aiven
    print("Se o seu grupo usa o banco no Aiven, peça os dados (Host, Port, User, Password e o")
    print("arquivo ca.pem) a quem administra o projeto. Sem eles, responda 'n' (modo local).\n")
    usar_mysql = perguntar("Conectar ao banco MySQL do grupo (Aiven)? (s/n)", "s").lower().startswith("s")
    if usar_mysql:
        print("\nNo console do Aiven: seu serviço MySQL → Overview → Connection information")
        v["DB_HOST"] = perguntar("Host (ex.: mysql-nexo-xxxx.l.aivencloud.com)", v.get("DB_HOST", ""))
        v["DB_PORT"] = perguntar("Port (número, NÃO é 3306)", v.get("DB_PORT", ""))
        v["DB_USER"] = perguntar("User", v.get("DB_USER", "avnadmin"))
        v["DB_PASSWORD"] = pedir_senha(v.get("DB_PASSWORD", ""))
        v["DB_NAME"] = perguntar("Nome do banco a criar", v.get("DB_NAME", "nexo"))

        ca = achar_ca()
        if ca and ca.resolve() != CA_DESTINO.resolve():
            if perguntar(f"Encontrei o certificado {ca}. Usar este? (s/n)", "s").lower().startswith("s"):
                CA_DESTINO.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ca, CA_DESTINO)
        while not CA_DESTINO.exists():
            caminho = perguntar("Caminho do 'CA certificate' baixado do Aiven (arraste o arquivo para esta janela)")
            caminho = Path(caminho.strip('"').strip("'"))
            if caminho.is_file():
                shutil.copy(caminho, CA_DESTINO)
            else:
                print("  Arquivo não encontrado. No Aiven: Overview → CA certificate → Download.")
        v["DB_SSL_CA"] = "banco/dados/ca.pem"
        print(f"  Certificado salvo em {CA_DESTINO}")
    else:
        v["DB_HOST"] = ""

    # ------------------------------------------------------------ e-mail
    configurou_email = perguntar("\nConfigurar o e-mail de recuperação de senha agora? (s/n)", "n").lower().startswith("s")
    if configurou_email:
        print("Para Gmail: use uma 'senha de app' (https://myaccount.google.com/apppasswords)")
        v["SMTP_HOST"] = perguntar("Servidor SMTP", v.get("SMTP_HOST", "smtp.gmail.com"))
        v["SMTP_PORT"] = perguntar("Porta", v.get("SMTP_PORT", "587"))
        v["SMTP_SECURITY"] = perguntar("Segurança (starttls/ssl/nenhuma)", v.get("SMTP_SECURITY", "starttls"))
        v["SMTP_USER"] = perguntar("E-mail que vai enviar as mensagens (ex.: nexo.projeto@gmail.com)",
                                   v.get("SMTP_USER", ""))
        gmail = "gmail" in v["SMTP_HOST"]
        v["SMTP_PASSWORD"] = pedir_senha(v.get("SMTP_PASSWORD", ""), rotulo="Senha de app do e-mail",
                                         origem="Google" if gmail else "e-mail", prefixo="", sem_espacos=gmail)
        v["SMTP_FROM"] = f"NEXO <{v['SMTP_USER']}>"

    arquivo = configuracao.salvar_env(v)
    print(f"\nConfigurações salvas em {arquivo}")
    for antigo in configuracao.CONFIG_INI:
        if antigo.exists():
            antigo.rename(antigo.with_name("config.ini.bak"))
            print(f"  O config.ini antigo foi convertido e renomeado para {antigo.with_name('config.ini.bak')}")

    if configurou_email:
        testar_email(v["SMTP_USER"])
    if usar_mysql:
        testar_banco(v)


if __name__ == "__main__":
    main()
