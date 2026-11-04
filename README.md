# NEXO — Ponto de Conexão

Ferramenta acadêmica de **análise de redes aplicada a transações financeiras**. O NEXO transforma
uma base de transações em um **grafo** (contas = nós, transações = arestas) e calcula matrizes,
centralidades, comunidades (Louvain), análise espectral e um **score provisório de relevância
estrutural**, mostrando tudo num sistema web com login, cargos e um **simulador** de novas transações.

> Relevância estrutural **não é** detecção de fraude. O NEXO apoia a análise humana.

**Versão atual:** 0.4 (Fase 0: reorganização e base técnica). Base de demonstração: **40 contas, 160 transações**.

---

## Começar em 3 passos (Windows)

1. Baixe o projeto: **Code → Download ZIP** e extraia, ou rode `git clone https://github.com/miliano2008/NEXO-Ponto-de-Conexao.git`.
2. Sem Python instalado, dê dois cliques em **`INSTALAR_WINDOWS.bat`**. Com Python, use **`iniciar.bat`**.
3. Na primeira vez, o sistema pergunta os dados do banco (Aiven) e do e-mail e cria o arquivo **`.env`**.
   Coloque o **`ca.pem`** do Aiven em `banco\dados\`. Esse arquivo é enviado pelo grupo por um canal privado.

O navegador abre em **http://127.0.0.1:5000**. No Linux e no macOS, use `bash iniciar.sh`.

O passo a passo completo, com Aiven, e-mail, atualização e problemas comuns, está em
**[docs/instalacao-e-uso.md](docs/instalacao-e-uso.md)**.

---

## Estrutura do repositório

```text
NEXO-Ponto-de-Conexao/
├── iniciar.bat / iniciar.sh     ← abre o NEXO (cria o ambiente sozinho)
├── INSTALAR_WINDOWS.bat         ← instala o Python se o computador não tiver
├── .env.example                 ← modelo de configuração (o .env real NÃO vai para o GitHub)
├── requirements.txt             ← bibliotecas do sistema
├── requirements-dev.txt         ← + bibliotecas de teste (Playwright)
│
├── nucleo/      Motor matemático (grafos, matrizes, métricas, score) e configuração
├── banco/       Conexão MySQL/SQLite, migrações, repositório, backup e dados da base
├── app/         Servidor web Flask, login/cargos, e-mail, telas (HTML, CSS e JS em módulos)
├── testes/      Testes automáticos (motor, login, Fase 0, MySQL e navegador)
├── scripts/     Atalhos de dois cliques: diagnóstico, configurar, backup, testes…
├── docs/        Documentação técnica (arquitetura, banco, API, segurança, fases)
│
├── 01-DOCUMENTACAO/       Documentos da disciplina (enunciado A3, apostila do GitHub)
├── 02-IDEIA-DO-PROJETO/   Ideia original do projeto e protótipo estático
└── 03-APRESENTACAO/       Material de apresentação e tutorial do grupo (PDF)
```

Cada pasta tem um `README.md` explicando seus arquivos.

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/instalacao-e-uso.md](docs/instalacao-e-uso.md) | Instalação, Aiven, e-mail, atualização do PC, atalhos e solução de problemas |
| [docs/arquitetura.md](docs/arquitetura.md) | Camadas, fluxo de um pedido, cache e desempenho |
| [docs/banco-de-dados.md](docs/banco-de-dados.md) | Tabelas, migrações numeradas, backup e restauração |
| [docs/api.md](docs/api.md) | Rotas do servidor e permissões |
| [docs/frontend.md](docs/frontend.md) | Módulos JavaScript, eventos e CSS |
| [docs/seguranca.md](docs/seguranca.md) | Login, senhas, cargos, segredos e boas práticas do grupo |
| [docs/matematica.md](docs/matematica.md) | Métricas, normalização e score |
| [docs/testes.md](docs/testes.md) | Como rodar e o que cada teste cobre |
| [docs/fases-e-decisoes.md](docs/fases-e-decisoes.md) | Roteiro das fases 0–6 e decisões D1–D13 |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | Histórico de versões |

## Tecnologias

Python 3.10+ · Flask · NetworkX · NumPy · openpyxl · PyMySQL · MySQL (Aiven) ou SQLite local ·
HTML/CSS/JavaScript (módulos nativos, sem etapa de compilação) · Playwright nos testes.

## Regras do grupo

- **Nunca** envie para o GitHub: `.env`, `config.ini`, `banco/dados/ca.pem`, `banco/dados/nexo.db`,
  `banco/dados/.chave_secreta` e `banco/dados/backups/`. O `.gitignore` já bloqueia esses arquivos.
- Cada fase é desenvolvida numa branch (`fase-0`, `fase-1`…) e entra na `main` depois de validada.
- Antes de rodar uma versão nova pela primeira vez no banco do grupo, faça o backup:
  `scripts\BACKUP.bat`.
