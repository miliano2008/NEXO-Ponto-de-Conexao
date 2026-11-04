"""NEXO — cópia de segurança do banco de dados.

Executar: scripts\\BACKUP.bat  ou  python -m banco.backup

- MySQL (Aiven): gera banco/dados/backups/nexo_AAAAMMDD_HHMMSS.sql com a estrutura
  (CREATE TABLE) e os dados (INSERT) de todas as tabelas. Restaurar: abrir o arquivo
  no MySQL Workbench (File → Open SQL Script) e executar, ou `mysql ... < arquivo.sql`.
- Modo local: copia banco/dados/nexo.db para a mesma pasta.

A pasta de backups está no .gitignore (contém dados de usuários).
"""

import shutil
from datetime import date, datetime, timedelta
from decimal import Decimal

from banco import conexao as db
from nucleo.configuracao import PASTA_DADOS

PASTA_BACKUPS = PASTA_DADOS / "backups"


def _literal(valor, conexao):
    if valor is None:
        return "NULL"
    if isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, (bytes, bytearray)):
        return "0x" + bytes(valor).hex() if valor else "''"
    if isinstance(valor, timedelta):
        total = int(valor.total_seconds())
        return f"'{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}'"
    if isinstance(valor, (datetime, date)):
        return f"'{valor.isoformat(sep=' ') if isinstance(valor, datetime) else valor.isoformat()}'"
    return conexao.escape(str(valor))


def backup_mysql():
    agora = datetime.now()
    PASTA_BACKUPS.mkdir(parents=True, exist_ok=True)
    destino = PASTA_BACKUPS / f"nexo_{agora:%Y%m%d_%H%M%S}.sql"
    conexao = db.conectar_mysql()
    cfg = db.config_mysql()
    totais = {}
    with conexao.cursor() as c, destino.open("w", encoding="utf-8") as saida:
        saida.write(f"-- NEXO — backup do banco `{cfg['banco']}` em {cfg['host']}\n-- Gerado em {agora:%d/%m/%Y %H:%M:%S}\n")
        saida.write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS = 0;\n\n")
        c.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        tabelas = sorted(list(l.values())[0] for l in c.fetchall())
        for tabela in tabelas:
            c.execute(f"SHOW CREATE TABLE `{tabela}`")
            criacao = c.fetchone()["Create Table"]
            saida.write(f"-- Tabela {tabela}\nDROP TABLE IF EXISTS `{tabela}`;\n{criacao};\n")
            c.execute(f"SELECT * FROM `{tabela}`")
            linhas = c.fetchall()
            totais[tabela] = len(linhas)
            for i in range(0, len(linhas), 200):  # INSERTs em lotes de 200 linhas
                bloco = linhas[i:i + 200]
                colunas = ", ".join(f"`{k}`" for k in bloco[0])
                valores = ",\n".join("(" + ", ".join(_literal(v, conexao) for v in l.values()) + ")" for l in bloco)
                saida.write(f"INSERT INTO `{tabela}` ({colunas}) VALUES\n{valores};\n")
            saida.write("\n")
        saida.write("SET FOREIGN_KEY_CHECKS = 1;\n")
    conexao.close()
    return destino, totais


def backup_local():
    if not db.SQLITE.exists():
        raise FileNotFoundError("Não há banco local (banco/dados/nexo.db) para copiar.")
    PASTA_BACKUPS.mkdir(parents=True, exist_ok=True)
    destino = PASTA_BACKUPS / f"nexo_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(db.SQLITE, destino)
    return destino, {}


def fazer_backup():
    return backup_mysql() if db.usando_mysql() else backup_local()


if __name__ == "__main__":
    try:
        print(f"NEXO — backup de {db.descricao()}\n")
        arquivo, totais = fazer_backup()
        for tabela, n in totais.items():
            print(f"  {tabela:<24} {n:>6} linha(s)")
        print(f"\nBackup salvo em: {arquivo}")
        print("Guarde uma cópia fora do computador (ex.: seu Google Drive pessoal). Não envie para o GitHub.")
    except (db.ErroBanco, FileNotFoundError, OSError) as erro:
        print("[ERRO]", erro)
        raise SystemExit(1) from erro
