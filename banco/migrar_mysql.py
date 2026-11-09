"""NEXO — cria o banco no MySQL (Aiven) e exporta os dados do projeto.

Executar: scripts\MIGRAR_MYSQL.bat  ou  python -m banco.migrar_mysql   (pode rodar de novo: não duplica)
          python -m banco.migrar_mysql --recriar   (apaga e recarrega contas/transações)

Etapas:
 1. testa a conexão (SSL) com as credenciais DB_* do .env (ou [mysql] do config.ini)
 2. cria o banco (CREATE DATABASE), as tabelas de dados (contas, transacoes) e aplica
    as migrações numeradas (usuários, convites, auditoria, simulações, análises...)
 3. exporta as 40 contas e 160 transações dos CSVs (validadas por nucleo/analise.py)
 4. copia os usuários do SQLite local (banco/dados/nexo.db), se existirem
 5. confere as contagens e a soma dos valores no MySQL
"""

import sqlite3
import sys
from decimal import Decimal

from banco import conexao as db
from banco import migracoes, repositorio

RECRIAR = "--recriar" in sys.argv


def passo(n, texto):
    print(f"\n[{n}/5] {texto}")


def migrar():
    cfg = db.config_mysql()
    if cfg is None:
        print("O banco MySQL não está configurado (DB_HOST vazio). Rode scripts\\CONFIGURAR.bat.")
        raise SystemExit(1)

    passo(1, f"Conectando em {cfg['host']}:{cfg['porta']} como {cfg['usuario']}...")
    conexao = db.conectar_mysql(com_banco=False)
    with conexao.cursor() as c:
        c.execute("SELECT VERSION() AS v")
        versao = c.fetchone()["v"]
        c.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
        cifra = (c.fetchone() or {}).get("Value") or "SEM SSL"
    print(f"      Servidor {versao} · conexão criptografada: {cifra}")
    if not cfg["ssl_ca"]:
        print("      Aviso: ssl_ca vazio — a conexão é criptografada, mas o certificado do servidor não é verificado.")

    passo(2, f"Criando o banco '{cfg['banco']}' e as tabelas...")
    nome = cfg["banco"].replace("`", "")
    with conexao.cursor() as c:
        c.execute(f"CREATE DATABASE IF NOT EXISTS `{nome}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conexao.select_db(nome)
    with conexao.cursor() as c:
        if RECRIAR:
            c.execute("DROP TABLE IF EXISTS transacoes")
            c.execute("DROP TABLE IF EXISTS contas")
            print("      --recriar: tabelas contas e transacoes apagadas.")
        for comando in (x.strip() for x in db.ESQUEMA_DADOS_MYSQL.split(";")):
            if comando:
                c.execute(comando)
    conexao.commit()
    # usuários, convites, auditoria, simulações e análises: migrações numeradas
    migracoes.aplicar(registrar=lambda texto: print("    " + texto.strip()))
    with conexao.cursor() as c:
        c.execute("SHOW TABLES")
        print("      Tabelas:", ", ".join(sorted(list(t.values())[0] for t in c.fetchall())))

    passo(3, "Exportando contas e transações dos CSVs...")
    contas, transacoes = repositorio.carregar_csv()  # mesma validação usada pelo sistema
    with conexao.cursor() as c:
        c.executemany(
            "INSERT INTO contas (id_conta, tipo_titular, data_abertura) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE tipo_titular = VALUES(tipo_titular), data_abertura = VALUES(data_abertura)",
            [(x["id_conta"], x["tipo_titular"], x["data_abertura"]) for x in contas])
        c.executemany(
            "INSERT INTO transacoes (id_transacao, conta_origem, conta_destino, valor, data, hora, tipo_transacao) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE conta_origem = VALUES(conta_origem), "
            "conta_destino = VALUES(conta_destino), valor = VALUES(valor), data = VALUES(data), "
            "hora = VALUES(hora), tipo_transacao = VALUES(tipo_transacao)",
            [(t["id"], t["de"], t["para"], Decimal(t["centavos"]) / 100, t["data"], t["hora"], t["tipo"])
             for t in transacoes])
    conexao.commit()
    print(f"      {len(contas)} contas e {len(transacoes)} transações enviadas.")

    passo(4, "Copiando usuários do SQLite local (se houver)...")
    if db.SQLITE.exists():
        local = sqlite3.connect(db.SQLITE)
        local.row_factory = sqlite3.Row
        usuarios = local.execute("SELECT * FROM usuarios").fetchall()
        local.close()
        colunas = ["documento", "tipo_documento", "nome", "email", "senha_hash", "cargo", "ativo",
                   "tentativas_falhas", "bloqueado_ate", "criado_em", "ultimo_login"]
        # telefone/email_confirmado só existem em bancos locais criados pela versão nova
        locais = set(usuarios[0].keys()) if usuarios else set()
        colunas += [c for c in ("telefone", "email_confirmado") if c in locais]
        with conexao.cursor() as c:
            novos = 0
            for u in usuarios:
                # INSERT IGNORE: quem já existe no MySQL (mesmo CPF/CNPJ ou e-mail) é mantido
                novos += c.execute(f"INSERT IGNORE INTO usuarios ({', '.join(colunas)}) "
                                   f"VALUES ({', '.join(['%s'] * len(colunas))})",
                                   [u[col] for col in colunas])
        conexao.commit()
        print(f"      {novos} usuário(s) copiado(s), {len(usuarios) - novos} já existia(m) no MySQL.")
        print("      As senhas continuam com hash; ninguém precisa redefinir.")
    else:
        print("      Nenhum banco/dados/nexo.db local. Crie o administrador depois: scripts\\CRIAR_ADMIN.bat")

    passo(5, "Conferindo os dados no MySQL...")
    with conexao.cursor() as c:
        c.execute("SELECT COUNT(*) AS n FROM contas")
        n_contas = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) AS n, SUM(valor) AS total FROM transacoes")
        r = c.fetchone()
        c.execute("SELECT COUNT(*) AS n FROM usuarios")
        n_usuarios = c.fetchone()["n"]
    total_csv = sum(Decimal(t["centavos"]) for t in transacoes) / 100
    print(f"      contas: {n_contas} | transações: {r['n']} | volume: R$ {r['total']:,.2f} | usuários: {n_usuarios}")
    conexao.close()
    if (n_contas, r["n"], r["total"]) != (len(contas), len(transacoes), total_csv):
        print("\n[ATENÇÃO] O MySQL tem dados diferentes dos CSVs (talvez transações extras). "
              "Use --recriar para espelhar exatamente os CSVs.")
        raise SystemExit(1)
    print("\nMigração concluída. Os dados conferem com os CSVs. Inicie o sistema: iniciar.bat")


if __name__ == "__main__":
    try:
        migrar()
    except (db.ErroBanco, ValueError, migracoes.ErroVersao) as erro:
        print("\n[ERRO]", erro)
        raise SystemExit(1) from erro
