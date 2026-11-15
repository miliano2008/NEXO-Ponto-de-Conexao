# Histórico de versões

## 0.6 — Fase 2: análise e inteligência (branch `fase-2`)
- **Painel de risco**: 10 regras explicáveis (volume atípico, repasse rápido, cadeia de repasse, circuito recorrente, fan-in, fan-out, intermediação, ponte entre comunidades, concentração no tempo e valor atípico), cada uma com evidência, limite e peso. Prioridade de verificação (Alta, Moderada, Baixa) e comunidades em destaque. As regras foram conferidas com o gabarito da planilha.
- **Período e filtros**: calendário (atalhos, mês, data inicial e final, dia específico), tipos e faixa de valor recalculam a rede. Filtros de visualização (origem, destino, comunidade, prioridade, status, investigação, mínimo de transações) valem no Dashboard, no Painel de risco, em Transações e em Contas.
- **Investigação**: situação por conta, com comentário obrigatório, histórico e auditoria.
- **Contas em análise**: ordenação por qualquer coluna, colunas de risco e investigação. O detalhe da conta mostra os indícios e a investigação.
- **Valores em R$** com máscara; filtro de comunidade em Transações; marca de valor atípico.
- **Banco:** migração 5 (`casos`, `casos_historico`). **Motor:** versão 2.0.
- **Testes:** novo `test_fase2.py` (gabarito, regras, recorte, investigação, 300 transações); teste no navegador ampliado. São 8 conjuntos.

## 0.5 — Fase 1: identidade, login e página institucional (branch `fase-1`)
- **Página institucional** em `/`, pública, com acesso rápido no banner, como funciona, recursos, segurança, FAQ e rodapé. O sistema passou para **`/app`**.
- **Login por e-mail ou CPF/CNPJ** no mesmo campo. Mensagem única: "E-mail, CPF/CNPJ ou senha inválidos." "Esqueci minha senha" também aceita o e-mail.
- **Entrar com Google** (opcional, configurado no `CONFIGURAR`): vincula a cadastros confirmados ou cria o cadastro com CPF/CNPJ e telefone. Pode ser restrito a um domínio. Sem biblioteca nova.
- **Minha senha**: o usuário troca a própria senha dentro do sistema e pode desconectar os outros computadores.
- **Trocar a senha encerra as outras sessões**, seja pela tela, pelo link do e-mail ou pelo `CRIAR_ADMIN`.
- **Banco:** migração 4 (`versao_sessao` e `identidades_externas`).
- **Testes:** novos `test_fase1.py` e `test_email.py`; teste no navegador ampliado. São 7 conjuntos ao todo.
- **E-mail:** o login no servidor usa um método só. Antes, quando o Gmail recusava a senha e fechava a conexão, aparecia apenas "Connection unexpectedly closed", com a explicação errada "não é a senha". Agora a mensagem diz o motivo real: senha recusada, tentativas demais ou conexão bloqueada. O `iniciar.bat` também deixou de fazer login no Gmail a cada abertura.

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
