"""NEXO — diagnóstico do ambiente.

Executar: scripts\\DIAGNOSTICO.bat  ou  python -m app.diagnostico
Confere Python, bibliotecas, arquivos, configuração (.env), banco (Aiven ou local),
versão do esquema, base de dados, usuários, e-mail e porta.
Com --rapido mostra só avisos e erros.
"""

import importlib
import socket
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RAPIDO = "--rapido" in sys.argv
erros, avisos = [], []


def ok(msg):
    if not RAPIDO:
        print(f"  [OK]    {msg}")


def aviso(msg, como):
    avisos.append(msg)
    print(f"  [AVISO] {msg}\n          → {como}")


def erro(msg, como):
    erros.append(msg)
    print(f"  [ERRO]  {msg}\n          → {como}")


def main():
    if not RAPIDO:
        print("NEXO — diagnóstico do ambiente\n")

    # 1. Python
    v = sys.version_info
    if v < (3, 10):
        erro(f"Python {v.major}.{v.minor} é antigo demais (networkx/numpy exigem 3.10+).",
             "Instale o Python 3.10 ou mais novo: https://www.python.org/downloads/")
    else:
        ok(f"Python {v.major}.{v.minor}.{v.micro} em {sys.executable}")
    if sys.prefix == sys.base_prefix:
        aviso("Não está rodando dentro do ambiente virtual .venv.",
              "Use iniciar.bat / iniciar.sh, ou ative o .venv antes de rodar.")

    # 2. Bibliotecas
    faltando = []
    for nome, pacote in (("networkx", "networkx"), ("numpy", "numpy"), ("flask", "flask"), ("werkzeug", "werkzeug"),
                         ("openpyxl", "openpyxl"), ("pymysql", "PyMySQL")):
        try:
            importlib.import_module(nome)
            ok(f"{nome} {version(pacote)}")
        except (ImportError, PackageNotFoundError):
            faltando.append(nome)
    if faltando:
        erro(f"Bibliotecas não instaladas: {', '.join(faltando)}.",
             "python -m pip install -r requirements.txt  (dentro do .venv)")
        return

    # 3. Arquivos do projeto (repositório/zip completo?)
    necessarios = ["app/servidor.py", "app/auth.py", "nucleo/analise.py", "banco/conexao.py", "banco/migracoes.py",
                   "requirements.txt", "app/templates/index.html", "app/templates/login.html",
                   "app/static/js/app.js", "app/static/css/tokens.css", "banco/dados/contas.csv",
                   "banco/dados/transacoes.csv"]
    ausentes = [a for a in necessarios if not (RAIZ / a).exists()]
    if ausentes:
        erro(f"Arquivos ausentes: {', '.join(ausentes)}.",
             "Baixe o projeto inteiro de novo (git pull ou o zip completo) — não rode de dentro do zip.")
    else:
        ok("Todos os arquivos do projeto presentes")

    from banco import conexao as db
    from banco import migracoes
    from nucleo import configuracao

    # 4. Configuração
    origem = configuracao.origem()
    if origem is None:
        aviso("Nenhum .env encontrado: o NEXO roda no modo local (CSV + SQLite), sem e-mail.",
              "Para usar o banco do grupo e o e-mail: scripts\\CONFIGURAR.bat")
    else:
        ok(f"Configuração lida de {origem}")
        if origem.endswith("config.ini"):
            aviso("Usando o config.ini antigo (versão 0.3). Ele continua funcionando.",
                  "Rode scripts\\CONFIGURAR.bat e aperte Enter em tudo para convertê-lo para .env.")

    # 5. MySQL (Aiven) — testado antes: base e usuários dependem dele
    mysql_falhou = False
    try:
        if db.usando_mysql():
            cfg = db.config_mysql()
            conexao = db.conectar_mysql()
            with conexao.cursor() as cur:
                cur.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
                cifra = (cur.fetchone() or {}).get("Value")
                cur.execute("SELECT (SELECT COUNT(*) FROM contas) AS c, (SELECT COUNT(*) FROM transacoes) AS t")
                n = cur.fetchone()
            conexao.close()
            if not cifra:
                aviso("Conexão com o MySQL sem SSL.", "Preencha DB_SSL_CA=banco/dados/ca.pem (CA certificate do Aiven).")
            ok(f"MySQL {cfg['host']}:{cfg['porta']}/{cfg['banco']} · SSL {cifra} · {n['c']} contas, {n['t']} transações")
        else:
            ok("Modo local (CSV + SQLite). Para usar o Aiven: scripts\\CONFIGURAR.bat")
    except db.ErroBanco as e:
        mysql_falhou = True
        if "não existe" in str(e):
            # 1049: usuário e senha foram aceitos; só falta criar o banco
            erro("Conexão com o Aiven OK (usuário e senha aceitos), mas o banco ainda não foi criado.",
                 "Dois cliques em scripts\\MIGRAR_MYSQL.bat")
        else:
            erro(str(e), "Dois cliques em scripts\\CONFIGURAR.bat — ele mostra os dados usados e permite comparar a senha.")
    except Exception as e:  # noqa: BLE001
        mysql_falhou = True
        erro(f"MySQL conectado, mas as tabelas não existem ou falharam: {e}",
             "Crie o banco e exporte os dados: scripts\\MIGRAR_MYSQL.bat")

    if mysql_falhou:
        print("  [--]    Esquema, base de dados e usuários: não verificados (dependem da conexão acima)")
    else:
        # 6. Versão do esquema (migrações)
        try:
            pendentes = [n for n, _, _ in migracoes.MIGRACOES if n not in migracoes.versoes_aplicadas()]
            aplicadas = migracoes.versoes_aplicadas()
            if aplicadas and max(aplicadas) > migracoes.VERSAO_ATUAL:
                erro(f"O banco está na versão {max(aplicadas)} do esquema e este NEXO só conhece até a "
                     f"{migracoes.VERSAO_ATUAL}.", "Atualize o projeto (git pull ou o zip mais recente).")
            elif pendentes:
                aviso(f"Migrações pendentes: {pendentes}. Serão aplicadas ao iniciar o NEXO.",
                      "Antes, faça backup do banco do grupo: scripts\\BACKUP.bat")
            else:
                ok(f"Esquema do banco na versão {migracoes.VERSAO_ATUAL} (atualizado)")
        except Exception as e:  # noqa: BLE001
            erro(f"Não foi possível ler a versão do esquema: {e}", "Rode scripts\\DIAGNOSTICO.bat de novo e envie o print.")

        # 7. Base de dados (40 contas / 160 transações)
        try:
            from banco import repositorio
            contas, transacoes = repositorio.carregar_dados()
            if (len(contas), len(transacoes)) != (40, 160):
                aviso(f"Base com {len(contas)} contas e {len(transacoes)} transações (esperado 40/160).",
                      "Regenere os CSVs: python -m banco.exportar_excel")
            else:
                ok("Base de dados: 40 contas, 160 transações")
        except Exception as e:  # noqa: BLE001 — qualquer falha aqui é útil de mostrar
            erro(f"Erro ao ler a base de dados: {e}",
                 "Os CSVs podem ter sido salvos no Excel com outro formato. Rode: python -m banco.exportar_excel")

    # 8. Permissão de escrita (banco local, chave de sessão e backups ficam em banco/dados/)
    teste = configuracao.PASTA_DADOS / ".teste_escrita"
    try:
        teste.write_text("ok")
        teste.unlink()
        ok("Permissão de escrita na pasta banco/dados/")
    except OSError:
        erro("Sem permissão para gravar na pasta banco/dados/.",
             "Mova o projeto para uma pasta sua (ex.: Documentos) fora de pastas protegidas/sincronizadas.")

    # 9. Usuários e administrador (sem aplicar migrações: o diagnóstico só lê)
    if not mysql_falhou:
        try:
            from app import auth
            if not set(n for n, _, _ in migracoes.MIGRACOES) <= set(migracoes.versoes_aplicadas()):
                print("  [--]    Usuários: verificados depois que o NEXO aplicar as migrações pendentes")
            elif auth.contar_administradores_ativos() == 0:
                if db.usando_mysql():
                    aviso("Nenhum administrador no banco do grupo (Aiven).",
                          "Dois cliques em scripts\\CRIAR_ADMIN.bat (ou o iniciar.bat pergunta na primeira vez).")
                else:
                    aviso("Nenhum administrador neste computador (modo local).",
                          "Dois cliques em scripts\\CRIAR_ADMIN.bat — usuários criados em outro PC não vêm junto.")
            else:
                ok(f"Banco de usuários: {len(auth.listar_usuarios())} usuário(s), administrador presente")
        except Exception as e:  # noqa: BLE001
            erro(f"Erro no banco de usuários: {e}",
                 "No modo local, se banco/dados/nexo.db veio de outro computador, apague-o e rode scripts\\CRIAR_ADMIN.bat.")

    # 10. E-mail (confirmação de cadastro e "Esqueci minha senha")
    from app import envio_email
    try:
        c = envio_email.testar_login()
        ok(f"E-mail: login OK em {c['host']} como {c['usuario'] or '(sem usuário)'}")
    except envio_email.ErroEmail as e:
        if "não configurado" in str(e):
            aviso("E-mail não configurado: cadastros novos não recebem confirmação e 'Esqueci minha senha' não funciona.",
                  "Dois cliques em scripts\\CONFIGURAR.bat → responda 's' em 'Configurar o e-mail'.")
        else:
            erro(str(e), "Dois cliques em scripts\\CONFIGURAR.bat e cole a senha de app de novo (botão direito do mouse).")

    # 11. Porta
    with socket.socket() as s:
        livre = s.connect_ex(("127.0.0.1", 5000)) != 0
    if livre:
        ok("Porta 5000 livre")
    else:
        aviso("A porta 5000 já está em uso (outro NEXO aberto, ou o AirPlay no macOS).",
              "O NEXO vai usar a próxima porta livre e mostrar o endereço na janela preta.")


if __name__ == "__main__":
    main()
    print()
    if erros:
        print(f"{len(erros)} erro(s) impedem o NEXO de rodar. Corrija os itens [ERRO] acima.")
        if RAPIDO:
            input("Pressione Enter para tentar iniciar mesmo assim...")
    elif not RAPIDO:
        print("Tudo certo para rodar: iniciar.bat" + (f"  ({len(avisos)} aviso(s))" if avisos else ""))
