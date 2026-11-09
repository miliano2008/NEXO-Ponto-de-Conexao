# Banco de dados

## Dois modos, a mesma estrutura
| Modo | Quando | Dados de análise | Usuários, simulações e análises |
|---|---|---|---|
| **MySQL (Aiven)** | `DB_HOST` preenchido no `.env` | tabelas `contas` e `transacoes` | tabelas no mesmo banco |
| **Local** | sem `DB_HOST`, ou `NEXO_BANCO=local` | `banco/dados/contas.csv` e `transacoes.csv` | `banco/dados/nexo.db` (SQLite) |

A conexão com o MySQL usa SSL com o certificado `banco/dados/ca.pem` e a biblioteca **PyMySQL**.

O PyMySQL foi escolhido em vez do `mysql-connector-python` por ser escrito só em Python: instala em qualquer Windows sem compilador, e as mensagens de erro são traduzidas para o usuário. O pacote `cryptography` é necessário para o login do MySQL 8 com SSL.

## Tabelas
| Tabela | Criada por | Conteúdo |
|---|---|---|
| `contas` | `migrar_mysql` | id_conta (PK), tipo_titular, data_abertura |
| `transacoes` | `migrar_mysql` | id_transacao (PK), conta_origem e conta_destino (FK → contas), valor DECIMAL(12,2), data, hora, tipo_transacao |
| `usuarios` | migração 1 | CPF/CNPJ (único), nome, e-mail (único) e se foi confirmado, telefone, hash da senha, cargo, ativo, tentativas, bloqueio, último login |
| `tokens_recuperacao` | migração 1 | hash SHA-256 dos links enviados por e-mail (`tipo`: senha ou email), validade, uso único |
| `convites` | migração 1 | hash do código, cargo, usos e limite, validade, revogado |
| `auditoria` | migração 1 | eventos de acesso: login, falhas, cadastro, recuperação, mudanças de cargo |
| `simulacoes` | migração 2 | um rascunho por usuário (usuario_id → usuarios, apagado em cascata) |
| `simulacao_transacoes` | migração 2 | transações simuladas, com (simulacao_id, id_transacao) único, valor > 0 e origem ≠ destino |
| `analises` | migração 3 | assinatura (única), base, período, versão do motor, contagens, tempo de cálculo, resultado compactado (zlib), datas de criação e último uso |
| `versao_esquema` | automática | número, descrição e data de cada migração aplicada |

As consultas prontas para o MySQL Workbench ou o DBeaver estão em `banco/consultas_nexo.sql`.

## Migrações numeradas (`banco/migracoes.py`)
Cada mudança de estrutura é uma função numerada, aplicada **uma única vez** ao iniciar o sistema e registrada em `versao_esquema`.

| Nº | Descrição |
|---|---|
| 1 | Acesso: usuários, links por e-mail, convites e auditoria. Bancos da 0.3 ganham as colunas que faltavam (telefone, email_confirmado, tipo do token) |
| 2 | Simulações por usuário |
| 3 | Análises guardadas e rastreáveis |

Regras:

- Cada migração roda dentro de uma transação. Se der erro, nada daquela migração fica pela metade.
- Todas usam `CREATE TABLE IF NOT EXISTS` e checam a coluna antes de criá-la. Rodar de novo não estraga nada.
- **Proteção de versão:** se o banco já foi migrado por uma versão **mais nova** do NEXO, a versão antiga se recusa a iniciar e pede para atualizar o código. Assim, dois colegas com versões diferentes não corrompem o banco do grupo.
- Para criar a migração 4: escreva `m4_nome(c, mysql)` com o SQL do MySQL e do SQLite, acrescente `(4, "descrição", m4_nome)` em `MIGRACOES` e um teste em `testes/test_fase0.py`.

`scripts\DIAGNOSTICO.bat` mostra a versão do banco e as migrações pendentes, sem alterar nada.

## Backup e restauração
**Antes de rodar uma versão nova no banco do grupo pela primeira vez:**

```bat
scripts\BACKUP.bat            (ou: python -m banco.backup)
```

- **MySQL:** gera `banco/dados/backups/nexo_AAAAMMDD_HHMMSS.sql`, com `CREATE TABLE` e todos os dados de todas as tabelas.
- **Local:** copia o `nexo.db`.
- A pasta `backups/` fica fora do GitHub, porque contém e-mails e hashes de senha.

**Restaurar** (MySQL Workbench → *File → Run SQL Script*, ou pela linha de comando):

```bash
mysql --ssl-ca=banco/dados/ca.pem -h HOST -P PORTA -u avnadmin -p nexo < banco/dados/backups/nexo_....sql
```

O script apaga e recria cada tabela antes de inserir os dados. Teste feito na Fase 0: 4 usuários, 160 transações e R$ 880.273,77 restaurados exatamente.

## Carga inicial e recarga da base
- `scripts\MIGRAR_MYSQL.bat`: cria o banco `nexo`, as tabelas, as 40 contas e as 160 transações, e copia os usuários do SQLite local. Pode rodar de novo sem duplicar; `--recriar` recarrega contas e transações do zero.
- `python -m banco.exportar_excel`: regenera os CSVs a partir de `NEXO_Base_Transacoes.xlsx`.
- Mudanças feitas direto no MySQL aparecem no sistema em até 60 segundos, sem reiniciar.
- Análises guardadas sem uso há mais de 30 dias são apagadas automaticamente ao iniciar.

## Multiempresa (adiado)
O plano de organizações e bases por empresa (item 0.3) foi **adiado** por decisão do grupo. A base atual continua única. Veja [fases-e-decisoes.md](fases-e-decisoes.md).
