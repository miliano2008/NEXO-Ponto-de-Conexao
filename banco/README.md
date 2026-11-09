# banco/ — acesso a dados

| Arquivo | Conteúdo |
|---|---|
| `conexao.py` | Escolhe o banco: **MySQL** (Aiven, com SSL) se `DB_HOST` estiver configurado, ou **SQLite** local. Traduz os erros do MySQL para mensagens claras e reaproveita a conexão por thread |
| `migracoes.py` | Migrações numeradas (1: acesso, 2: simulações, 3: análises), aplicadas uma vez e registradas em `versao_esquema`. Impede que uma versão antiga use um banco já migrado por uma mais nova |
| `repositorio.py` | Leitura da base (`carregar_dados`: MySQL ou CSV), simulações por usuário e análises guardadas |
| `backup.py` | `python -m banco.backup`: cópia de segurança em `dados/backups/` (`.sql` do MySQL ou cópia do `nexo.db`) |
| `migrar_mysql.py` | `python -m banco.migrar_mysql [--recriar]`: cria o banco `nexo` no MySQL e envia contas, transações e usuários locais. Pode rodar de novo sem duplicar |
| `exportar_excel.py` | `python -m banco.exportar_excel`: regenera os CSVs a partir da planilha |
| `consultas_nexo.sql` | Consultas prontas para o MySQL Workbench / DBeaver |

## dados/
| Arquivo | Vai para o GitHub? | Conteúdo |
|---|:-:|---|
| `NEXO_Base_Transacoes.xlsx` | sim | Base original do grupo (não é alterada pelo sistema) |
| `contas.csv`, `transacoes.csv` | sim | 40 contas e 160 transações exportadas da planilha (modo local) |
| `ca.pem` | **não** | Certificado do Aiven, recebido por canal privado |
| `nexo.db` | **não** | Banco SQLite do modo local, criado automaticamente |
| `.chave_secreta` | **não** | Chave dos cookies de sessão, criada automaticamente |
| `backups/` | **não** | Cópias de segurança |

Tabelas, migrações e restauração: [docs/banco-de-dados.md](../docs/banco-de-dados.md).
