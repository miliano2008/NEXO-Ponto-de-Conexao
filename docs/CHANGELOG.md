# Histórico de versões

## 1.0 — Fase 6: importação de bases (branch `fase-6`)
- **Importação simples** (tela *Importar base*, só o administrador): o NEXO trabalha com **uma base por vez**, e importar um arquivo substitui a base para todos.
  1. **Enviar** um `.xlsx` (aba de transações e, opcionalmente, de contas; abas como "Leia-me" são ignoradas) ou um `.csv` (`;`, `,`, tab ou `|`; UTF-8 ou Windows-1252).
  2. **Conferir as colunas:** o NEXO sugere a correspondência pelos nomes (ex.: "Pagador" → conta de origem) e o administrador ajusta. O mapeamento fica salvo para o próximo arquivo com as mesmas colunas.
  3. **Prévia** das primeiras 50 linhas, com o **erro de cada linha** (valor que não é número, data inexistente, origem igual ao destino, código repetido…) e avisos.
  4. **Substituir:** nome da base, aceite de uso dos dados e a palavra SUBSTITUIR. Antes da troca, **backup automático**; a troca é feita **numa única transação** (tudo ou nada).
- Aceita valores como `1.234,56` e `R$ 1.234,56`, datas `01/08/2026` e do Excel, horas `14h05`, modalidades e titulares escritos de vários jeitos. Sem aba de contas, as contas saem das transações.
- **Limites (D6):** 300 transações, 300 contas e 2 MB.
- **LGPD:** opção "Mascarar códigos" (contas viram C001…, transações T0001…, sem guardar a correspondência) e aceite obrigatório.
- **O que a troca apaga (D8):** simulações, cenários, investigações e análises guardadas da base antiga. Ficam usuários, preferências, limites das regras e a auditoria.
- **Voltar à base de demonstração** com um clique (também com backup e confirmação). Planilha **modelo** para baixar.
- O nome da base aparece no cabeçalho, em Configurações e na identificação dos relatórios. Histórico das trocas com quem, quando e o backup.
- **Banco:** migração 8 (códigos de até 40 caracteres no MySQL, tabelas da base também no modo local, `importacoes` e `mapeamentos`). O `MIGRAR_MYSQL` não mistura mais a demonstração com uma base importada.
- **Correção:** dois backups no mesmo segundo não se sobrescrevem mais.
- **Testes:** novo `test_fase6.py`; `test_mysql` e o teste no navegador ampliados. São 12 conjuntos.

## 0.9 — Fase 5: relatórios e configurações (branch `fase-5`)
- **Relatórios em PDF, Excel, CSV, Word e PowerPoint**, gerados pelo mesmo conteúdo (`nucleo/relatorio.py`): os números são idênticos em todos os formatos.
  - **Relatório da análise:** identificação (quem, quando, período, filtros, número e assinatura da análise, versão do motor), indicadores, 6 gráficos, contas priorizadas com a evidência e a regra de origem de cada indício, padrões, comunidades, regras com os limites em vigor e **conclusões montadas por modelos de texto** (nunca afirmam fraude).
  - **Relatório da comparação** (períodos, simulação atual ou cenários), no botão da tela Histórico e comparação.
  - **Gráficos de verdade:** nativos no Excel, no Word e no PowerPoint (editáveis em "Editar dados") e vetoriais no PDF.
  - Excel com uma aba por tabela (números somáveis, filtros); CSV em `.zip` (um arquivo por tabela, `;` e vírgula decimal); PowerPoint 16:9 com anotações do apresentador.
  - Bibliotecas novas: reportlab, XlsxWriter, python-docx e python-pptx. Só são carregadas quando alguém exporta.
- **Limites das regras de risco editáveis** em Configurações pelo administrador (14 parâmetros com faixa segura). A análise é recalculada na hora para todos, e a mudança fica na auditoria. "Voltar ao padrão" restaura tudo.
- **Preferências no cadastro do usuário** (valem em qualquer computador): tema, tamanho do texto, fonte, contraste alto, menos animação, foco bem visível, cores e paleta do grafo, rótulos, valores nos gráficos, limiares do score e formato preferido do relatório. Botão **Preferências** na barra lateral para todos os cargos.
- **Banco:** migração 7 (`parametros_risco` e `preferencias_usuario`).
- **Testes:** novo `test_fase5.py` (faixas e permissões dos limites, preferências, os 5 formatos com os mesmos números e o gabarito C025 na comparação); `test_mysql` e o teste no navegador ampliados. São 11 conjuntos.

## 0.8 — Fase 4: simulador e histórico (branch `fase-4`)
- **Dados bancários fictícios** por conta: instituição ("Banco Fictício A a D", sem nomes nem códigos de bancos reais), tipo de conta e tipo de chave PIX. São gerados por regras fixas e coerentes com a base: contas ligadas por "Transferência" ficam na mesma instituição.
- **Regras por modalidade**, cada uma marcada como Regulamentação, Prática de mercado ou Parâmetro do administrador:
  - PIX 24 horas (informativa);
  - limite noturno do PIX para pessoa física;
  - TED só em dias úteis e dentro do horário;
  - transferência só na mesma instituição.

  A ação de cada uma (bloquear, alertar ou desligada) e os limites são ajustáveis pelo administrador, com auditoria. A conferência informativa da base vem junto.
- **Simulador:** repetição "a cada N dias" (até 30 vezes); prévia ao vivo com as instituições, as datas e o resultado de cada regra; bloqueio respeitado no servidor; máscara de R$.
- **Histórico de simulações:** "Salvar como cenário" guarda as transações, o recorte e os **dois resultados daquela execução** (com e sem a simulação). O cenário não muda depois. Dá para ver, restaurar no simulador e excluir.
- **Comparação lado a lado** (base, meses, datas, simulação atual e cenários): indicadores, destaques, **dois grafos nas mesmas posições** (conexões novas e removidas) e a tabela de mudanças por conta. O exemplo da planilha mostra C025 passando de 1 para 3 comunidades vizinhas e do 8º para o 1º lugar.
- **Banco:** migração 6 (`regras_modalidade` e colunas do histórico em `simulacoes`).
- **Testes:** novo `test_fase4.py`; teste no navegador ampliado. São 10 conjuntos.
- **Correções:** os botões de zoom da Rede interrompem a animação de "ajustar"; os campos de valor, data e hora recebem o mesmo estilo dos demais.

## 0.7 — Fase 3: rede de transações (branch `fase-3`)
- **Grafo com Cytoscape.js** (3.34.4, licença MIT, copiado em `app/static/vendor/` e baixado só pela tela Rede).
  - **Navegação estilo mapa:** roda do mouse para zoom, arrastar o fundo para mover, botões de aproximar, afastar, ajustar à tela, centralizar na conta e reorganizar, e **minimapa** clicável.
  - **Localizar conta:** aproxima a conta e mostra só a vizinhança. Clique numa conta para ver as conexões; duplo clique para aproximar.
- **Esquemas de cores com legenda:** status de relevância, prioridade de risco, comunidade e papel na rede (intermediária, repasse). A **paleta segura para daltonismo** (Okabe–Ito) também usa formas diferentes por comunidade. A escolha fica salva no navegador.
- **Grafo de cada comunidade** (só as conexões internas, com recebido e enviado por conta) e "Destacar na rede".
- **Animação dos padrões** com as transações reais, em ordem cronológica: valor e data na seta, um ponto percorrendo cada ligação, controles de reproduzir, pausar, anterior, próximo, reiniciar e velocidade. Vale para fan-in, fan-out, cadeia de repasse, circuito recorrente e repasse rápido.
- O grafo respeita os filtros de visualização da Fase 2 e o tema escuro.
- **Testes:** novo `test_fase3.py` (biblioteca íntegra por SHA-256 e carregada sob demanda, dados dos padrões, 300 contas desenhadas em cerca de 1,3 s); teste no navegador cobre a navegação, as cores, a comunidade e a animação. São 9 conjuntos.

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
