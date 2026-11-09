# Arquitetura

## Visão geral

```text
 Navegador (HTML + CSS + JavaScript em módulos)
        │  fetch JSON (compactado com gzip)
        ▼
 app/servidor.py ── Flask: páginas, login, permissões e API
        │
        ├── app/auth.py ........ usuários, cargos, convites, tokens e auditoria
        ├── app/envio_email.py . e-mails de confirmação e recuperação (SMTP)
        └── app/analises.py .... base atual + cache de resultados
                 │
                 ├── nucleo/analise.py ... motor matemático (puro: não lê nem grava nada)
                 └── banco/repositorio.py  leitura da base, simulações e análises guardadas
                          │
                          └── banco/conexao.py → MySQL (Aiven, com SSL)  ou  SQLite + CSV (modo local)
```

**Regra das camadas:** cada camada só conhece a de baixo.

- `nucleo/` não sabe que existe banco nem web. Recebe listas e devolve um dicionário. Por isso pode ser testado sozinho.
- `banco/` não conhece Flask.
- `app/` junta tudo e cuida de quem pode fazer o quê.

## Pastas

| Pasta | Responsabilidade | Principais arquivos |
|---|---|---|
| `nucleo/` | Matemática e configuração | `analise.py`, `configuracao.py` |
| `banco/` | Acesso a dados | `conexao.py`, `migracoes.py`, `repositorio.py`, `backup.py`, `migrar_mysql.py` |
| `app/` | Servidor web e ferramentas | `servidor.py`, `auth.py`, `analises.py`, `envio_email.py`, `configurar.py`, `diagnostico.py` |
| `app/static/` | Interface | `css/*.css`, `js/app.js`, `js/nucleo/*.js`, `js/paginas/*.js` |
| `testes/` | Testes automáticos | `executar.py` roda todos |
| `scripts/` | Atalhos de dois cliques (Windows) e instaladores | `*.bat`, `*.ps1`, `*.sh` |

Todos os programas rodam **a partir da raiz** como módulos: `python -m app`, `python -m banco.backup`, `python -m testes.executar`.

## Configuração

O arquivo `nucleo/configuracao.py` lê as configurações nesta ordem de prioridade:

1. variáveis de ambiente do sistema, úteis numa hospedagem futura;
2. o arquivo **`.env`** na raiz, criado por `scripts\CONFIGURAR.bat`;
3. o `config.ini` antigo da versão 0.3, ainda aceito para ninguém do grupo ficar sem acesso.

Chaves: `APP_URL_BASE`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_SSL_CA`,
`SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. O modelo está em `.env.example`.

Variáveis só para desenvolvimento e testes:

| Variável | Efeito |
|---|---|
| `NEXO_BANCO=local` | Ignora o MySQL e usa CSV + SQLite. Os testes usam esse modo para nunca tocar no banco do grupo |
| `NEXO_MYSQL_BANCO` | Troca o nome do banco. O teste de MySQL usa `nexo_teste` |
| `NEXO_PORTA` | Porta inicial do servidor (padrão 5000). Se estiver ocupada, usa a próxima livre |
| `NEXO_CHROMIUM` | Caminho de um Chrome/Chromium para o teste de navegador |

Não usamos `python-dotenv`: o leitor do `.env` tem cerca de 20 linhas, aceita arquivos salvos com BOM pelo Bloco de Notas e não exige instalar mais nada.

## Fluxo de um pedido `/api/resultados`

1. `servidor.exige("consultar")` confere a sessão e o cargo.
2. `analises.calcular(dias, simuladas_do_usuario)`:
   - a base (contas + transações) vem da memória e é relida do banco **no máximo a cada 60 s**, então mudanças feitas direto no MySQL aparecem sem reiniciar;
   - calcula a **assinatura** SHA-256 de base + transações simuladas + período + `VERSAO_MOTOR`;
   - se a assinatura já está no cache em memória (até 32 resultados), devolve na hora;
   - senão, procura na tabela `analises`, onde ficam guardadas as análises sem simulação;
   - senão, roda `nucleo.analise.calcular()` (cerca de 25 ms com 160 transações e no máximo 145 ms com 300) e guarda o resultado.
3. O servidor remove as matrizes 40×40 da resposta, que são servidas à parte em `/api/matrizes` só quando a aba é aberta, e acrescenta os dados da simulação do usuário.
4. A resposta é compactada com gzip.

## Simulações

Cada usuário tem **a própria** simulação (tabelas `simulacoes` e `simulacao_transacoes`), que sobrevive ao reinício do servidor. Na versão 0.3 era uma lista única na memória, compartilhada por todos.

- A base oficial nunca é alterada.
- Os IDs simulados são `S0001`, `S0002`…
- O limite é de 200 transações simuladas por usuário.
- Antes de gravar, a transação passa pela mesma validação do motor.

## Desempenho (medido na Fase 0)

| Medida | Versão 0.3 | Versão 0.4 |
|---|---|---|
| Resposta de `/api/resultados` (160 transações) | ~120 KB | **11,2 KB** (sem matrizes + gzip) |
| Tempo da API | recalculava a cada pedido | ~26 ms no primeiro cálculo, **~5 ms** com o resultado reaproveitado |
| Primeira carga da tela | ~92 KB sem compressão (`app.js` + `style.css` inteiros) | **~23 KB** compactados (HTML + JS inicial + CSS); cada tela baixa só quando é aberta |
| Pior caso previsto para a Fase 6 (300 transações) | — | ≤ 145 ms, 55 KB compactado |

Os arquivos estáticos são **revalidados** a cada carga: o navegador pergunta se mudaram e recebe `304` se não. Assim não é preciso Ctrl+F5 depois de atualizar o código.
