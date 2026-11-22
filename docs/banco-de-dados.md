# Banco de dados

## Dois modos, a mesma estrutura
| Modo | Quando | Dados de análise | Usuários, simulações e análises |
|---|---|---|---|
| **MySQL (Aiven)** | `DB_HOST` preenchido no `.env` | tabelas `contas` e `transacoes` | tabelas no mesmo banco |
| **Local** | sem `DB_HOST`, ou `NEXO_BANCO=local` | a base importada (tabelas `contas` e `transacoes` do `nexo.db`) ou, se não houver, `banco/dados/contas.csv` e `transacoes.csv` | `banco/dados/nexo.db` (SQLite) |

A conexão com o MySQL usa SSL com o certificado `banco/dados/ca.pem` e a biblioteca **PyMySQL**.

O PyMySQL foi escolhido em vez do `mysql-connector-python` por ser escrito só em Python: instala em qualquer Windows sem compilador, e as mensagens de erro são traduzidas para o usuário. O pacote `cryptography` é necessário para o login do MySQL 8 com SSL.

## Tabelas
| Tabela | Criada por | Conteúdo |
|---|---|---|
| `contas` | `migrar_mysql` | id_conta (PK), tipo_titular, data_abertura |
| `transacoes` | `migrar_mysql` | id_transacao (PK), conta_origem e conta_destino (FK → contas), valor DECIMAL(12,2), data, hora, tipo_transacao |
| `usuarios` | migração 1 | CPF/CNPJ (único), nome, e-mail (único) e se foi confirmado, telefone, hash da senha, cargo, ativo, tentativas, bloqueio, último login. A migração 4 acrescenta `versao_sessao` |
| `tokens_recuperacao` | migração 1 | hash SHA-256 dos links enviados por e-mail (`tipo`: senha ou email), validade, uso único |
| `convites` | migração 1 | hash do código, cargo, usos e limite, validade, revogado |
| `auditoria` | migração 1 | eventos de acesso: login, falhas, cadastro, recuperação, mudanças de cargo |
| `simulacoes` | migração 2 | um rascunho por usuário (usuario_id → usuarios, apagado em cascata). Desde a migração 6, também os **cenários salvos** (`situacao = 'salva'`): nome, descrição, data, recorte, resumo e os dois resultados compactados (zlib) daquela execução |
| `simulacao_transacoes` | migração 2 | transações simuladas, com (simulacao_id, id_transacao) único, valor > 0 e origem ≠ destino |
| `identidades_externas` | migração 4 | contas externas vinculadas a um usuário: provedor (`google`; Microsoft no futuro), identificador da conta no provedor (`sujeito`), e-mail, datas. (provedor, sujeito) é único |
| `casos` | migração 5 | situação da investigação por conta (única), responsável e datas |
| `casos_historico` | migração 5 | cada decisão: situação anterior e nova, comentário, usuário e data |
| `regras_modalidade` | migração 6 | ajustes do administrador nas regras por modalidade: ação, parâmetros (JSON), quem e quando |
| `parametros_risco` | migração 7 | limites das regras de risco ajustados pelo administrador (só os diferentes do padrão): chave, valor, quem e quando |
| `preferencias_usuario` | migração 7 | preferências de cada usuário (JSON só com o que difere do padrão), apagadas em cascata com o usuário |
| `importacoes` | migração 8 | histórico das trocas de base: nome, origem (arquivo ou demonstração), arquivo e hash, contas, transações, período, mascarada, quem, quando, backup e situação (`ativa` ou `substituida`) |
| `mapeamentos` | migração 8 | mapeamento de colunas salvo por "layout" de arquivo (hash dos nomes das colunas), reaproveitado na próxima importação |
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
| 4 | Versão da sessão (`usuarios.versao_sessao`) e contas externas (`identidades_externas`), da Fase 1 |
| 5 | Investigação: `casos` e `casos_historico`, da Fase 2 |
| 6 | Regras por modalidade (`regras_modalidade`) e histórico de simulações (colunas em `simulacoes`), da Fase 4 |
| 7 | Limites das regras de risco (`parametros_risco`) e preferências do usuário (`preferencias_usuario`), da Fase 5 |
| 8 | Importação de bases (Fase 6): no MySQL, códigos de conta e de transação com até 40 caracteres (a chave estrangeira é recriada sem perder dados); no modo local, as tabelas `contas` e `transacoes` (vazias = usa os CSVs de demonstração); `importacoes` e `mapeamentos` |

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

## Troca da base (Fase 6, importação simples)
`repositorio.substituir_base` faz tudo **numa única transação**: apaga as simulações, os cenários, as análises guardadas e as investigações da base antiga, troca `contas` e `transacoes` (INSERT em lotes de 200 linhas, para não pagar uma ida e volta ao Aiven por linha) e registra a troca em `importacoes`. Se algo falhar, nada muda. Antes, o servidor faz o **backup automático** (`banco/backup.py`); sem backup, não troca.

O `MIGRAR_MYSQL` não reenvia os CSVs de demonstração quando a base em uso foi importada (misturaria as duas). Para voltar à demonstração, use a tela *Importar base*.

## Multiempresa (não adotado)
O grupo escolheu a **importação simples** (uma base por vez). O plano de organizações e bases por empresa (item 0.3) continua documentado em [fases-e-decisoes.md](fases-e-decisoes.md) caso o sistema venha a ser hospedado para várias empresas.
