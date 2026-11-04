# Histórico de versões

## 0.4 — Fase 0: reorganização e base técnica (branch `fase-0`)
**Para quem usa, nada muda na tela.** Por dentro:

- **Pastas:** código separado em `nucleo/` (matemática), `banco/` (dados), `app/` (web), `testes/` e `scripts/`. Os atalhos `.bat` foram para `scripts/`; `iniciar.bat` e `INSTALAR_WINDOWS.bat` continuam na raiz.
- **Configuração:** novo arquivo `.env`, criado por `scripts\CONFIGURAR.bat`. O `config.ini` antigo continua funcionando e é convertido automaticamente ao rodar o CONFIGURAR.
- **Banco:**
  - migrações numeradas com controle de versão (`versao_esquema`) e bloqueio de versões antigas;
  - novas tabelas `simulacoes`, `simulacao_transacoes` e `analises`;
  - backup com `scripts\BACKUP.bat`.
- **Simulador:** cada usuário tem a própria simulação, salva no banco, que sobrevive ao reinício. Antes, uma lista única na memória era compartilhada por todos.
- **Desempenho:**
  - resultados reaproveitados (cerca de 5 ms) com assinatura de dados;
  - respostas com gzip;
  - matrizes carregadas só quando a aba é aberta (`/api/resultados` passou de ~120 KB para ~11 KB);
  - mudanças no MySQL aparecem em até 60 s, sem reiniciar.
- **Frontend:** `app.js` dividido em módulos nativos e telas carregadas sob demanda; `style.css` dividido em 5 arquivos.
- **Testes:** `testes/` com 5 conjuntos (motor, login, Fase 0, MySQL e navegador) e o executor `scripts\TESTAR.bat`.
- **Documentação:** pasta `docs/` e um README por pasta.
- **Dependências reais** no `requirements.txt`. Saíram `pandas`, `matplotlib`, `mysql-connector-python` e `python-dotenv`, que não eram usadas; entrou o `requirements-dev.txt` (Playwright).

## 0.3 — Login completo e MySQL (Aiven)
- Login por CPF/CNPJ com mensagem única, confirmação de e-mail, recuperação por link, convites com cargo, telefone, edição de contato pelo administrador, limites por IP e auditoria.
- MySQL no Aiven com SSL, migração da base e dos usuários, `CONFIGURAR.bat` e `DIAGNOSTICO.bat`.

## 0.2 — Login e cargos
- Cadastro, login, recuperação de senha e quatro cargos (Administrador, Analista, Auditor, Visualizador), com SQLite local.

## 0.1 — Simulador web
- Backend matemático em Flask sobre a base de 40 contas e 160 transações: dashboard, rede, matrizes, comunidades, ranking e simulador, com o visual do protótipo.
