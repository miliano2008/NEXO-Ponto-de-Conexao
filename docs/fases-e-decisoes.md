# Fases e decisões

O NEXO evolui **uma fase por vez**. Cada fase é desenvolvida na própria branch (`fase-0`, `fase-1`…), apresentada ao grupo e só entra na `main` **depois de validada**. A fase seguinte não começa antes disso.

## Roteiro
| Fase | Tema | Situação |
|---|---|---|
| **0** | Reorganização e base técnica: pastas, `.env`, migrações, backup, simulação por usuário, cache, desempenho, frontend em módulos, testes | **Concluída e validada** (na `main`) |
| **1** | Identidade, login e página institucional: login por e-mail (aceitando CPF/CNPJ na transição), Google opcional, landing page com FAQ, sessão encerrada ao trocar a senha | **Concluída e validada** (na `main`) |
| **2** | Análise e inteligência: dashboard de risco com regras explicáveis, filtros dinâmicos, calendário, campo de valor em R$, status da investigação | **Concluída e validada** (na `main`) |
| **3** | Rede de transações: navegação estilo mapa (Cytoscape.js, carregado só nessa tela), busca, vizinhança e destaques | **Concluída e validada** (na `main`) |
| **4** | Simulador e histórico: histórico das simulações, comparação antes e depois, cenários salvos | **Concluída e validada** (na `main`) |
| 5 | Relatórios e configurações: exportação em **PDF, Excel, CSV, Word e PowerPoint**, com gráficos de verdade, não capturas de tela | Planejada |
| 6 | Importação de bases: upload `.xlsx`/`.csv` de até **300 transações**, uma base por empresa, com exclusão. Depende da decisão sobre multiempresa | Planejada |

## Decisões (resposta do grupo: "aceito as recomendações", com exceções)
| # | Assunto | Decisão |
|---|---|---|
| D1 | Identificador do login | **E-mail + senha**, com o CPF/CNPJ como dado do cadastro. Na transição, o login aceita os dois (Fase 1) |
| D2 | Login com Google | Implementado na Fase 1 como opcional, mas **mantido desligado** por decisão do grupo (sem `GOOGLE_CLIENT_ID`, o botão não aparece). Pode ser ativado depois, sem mudar código |
| D3 | Quem cria empresas | Cargo "Administrador da plataforma" *(implementação adiada com o multiempresa)* |
| D4 | Empresas por usuário | Uma *(adiada)* |
| D5 | CNPJ da empresa | Obrigatório e validado *(adiada)* |
| D6 | Limites do upload | 300 transações, 300 contas, 2 MB, `.xlsx` e `.csv` (Fase 6) |
| D7 | Trocar a base | Botão "Substituir", que exclui e importa de uma vez, mediante digitar o nome da empresa e com registro na auditoria (Fase 6) |
| D8 | O que a exclusão apaga | Tudo da base (transações, contas, análises, simulações), **menos os usuários** (Fase 6) |
| D9 | Hospedagem | **Exceção: rodar local** nas primeiras fases. O assunto volta a ser discutido mais à frente. Cloud Run e Render foram as opções avaliadas |
| D10 | GitHub | Agora: https://github.com/miliano2008/NEXO-Ponto-de-Conexao |
| D11 | Gráficos | Gráficos SVG próprios (0 KB extra) e **Cytoscape.js** só na tela Rede. ECharts só se algum gráfico da Fase 2 exigir |
| D12 | Exportação | **Exceção: PDF + Excel + CSV + Word + PowerPoint**, para uso em apresentações. Bibliotecas adicionais aprovadas (ReportLab, python-docx, python-pptx), desde que o desempenho continue alto |
| D13 | Base acadêmica atual | Mantida como está (40 contas e 160 transações) |

### Outras definições do grupo
- **Retiradas:** recuperação de senha por QR Code e integração com Power BI.
- **Telefone:** apenas guardado; sem envio de SMS.
- **Bibliotecas:** aprovadas desde que o desempenho continue alto. Por isso, cada biblioteca nova é medida antes de entrar.

## Itens adiados
| Item | Motivo | Quando |
|---|---|---|
| **0.3 Multiempresa:** tabelas `organizacoes` e `bases`, `base_id` em contas e transações, isolamento por empresa | O grupo vai discutir como implementar. A base atual foi mantida | A definir, antes da Fase 6 |
| **0.9 Preparação para hospedagem:** servidor de produção e arquivo de publicação | D9: rodar local por enquanto | A definir |

O que já ficou pronto para facilitar esses itens:

- configuração por variáveis de ambiente (`.env`), exigida pelas hospedagens;
- simulações guardadas no banco, porque hospedagens reiniciam a máquina;
- migrações numeradas com backup, que tornam segura a troca de chaves do multiempresa.

## Fase 4: o que foi entregue
| Item planejado | Entrega |
|---|---|
| Regras por modalidade | 5 regras em `nucleo/bancario.py`, cada uma com origem (**Regulamentação**, **Prática de mercado (configurável)** ou **Parâmetro do administrador**), ação (bloquear, alertar, desligada), limites e fonte. Ajuste só pelo administrador, com auditoria (tabela `regras_modalidade`). Valem para as transações simuladas; na base, a coluna "Na base" só informa (11 TEDs em fim de semana, 7 fora do horário, 3 PIX noturnos de pessoa física acima do limite) |
| Calendário com data, hora, intervalo e frequência | Simulação recorrente: a mesma transação repetida "a cada N dias" (até 30 vezes, intervalo de 1 a 90 dias), cada repetição com o próprio identificador |
| Histórico de simulações | Cenários salvos com as transações, o recorte e os dois resultados da execução. **O grafo do histórico é sempre o daquela execução**, nunca o grafo atual com dados antigos |
| Grafo de cada execução e comparação lado a lado | "Ver execução" (base daquele momento × cenário) e comparação livre entre base, meses, datas, simulação atual e cenários. Os dois grafos ficam nas mesmas posições (layout sobre a união das conexões); a comparação mostra conexões novas e removidas, mudanças de comunidade medidas pelo grupo (não pelo número), indicadores, destaques e tabela por conta |
| Dados bancários fictícios (4.5) | Instituição fictícia, tipo de conta e tipo de chave PIX, sem números. Aparecem no detalhe da conta, da transação e na prévia do simulador |
| Exportação | Fica para a **Fase 5**, que reúne todos os formatos (PDF, Excel, CSV, Word, PowerPoint) num motor único |

**Atenção às fontes das regras:** os textos de regulamentação citam o Banco Central, mas **confirmem a norma vigente antes de citar no trabalho**. Os limites do PIX noturno, por exemplo, foram definidos em 2021 e podem mudar. Na tela, cada regra mostra a fonte usada.

**Gabarito (planilha, "Comparação entre períodos"):** C025 passa de 1 para 3 comunidades vizinhas (comunidades 1, 6 e 7) e do 8º para o 1º lugar no ranking, do período A (01–15/08) para o B (01–15/09). Conferido em `testes/test_fase4.py` e no teste no navegador.

## Fase 3: o que foi entregue
| Item planejado | Entrega |
|---|---|
| Navegação estilo mapa | Cytoscape.js: roda do mouse para zoom, arrastar o fundo, aproximar, afastar, ajustar à tela, centralizar na conta, reorganizar e **minimapa** clicável. **Localizar conta** com a vizinhança. Clique numa conta para ver as conexões; duplo clique para aproximar |
| Grafo por comunidade | Botão "Ver grafo da comunidade": só as conexões internas, com a cor pela prioridade de risco e a tabela de recebido e enviado. "Destacar na rede" apaga as outras comunidades |
| Esquemas de cores com legenda | Status, prioridade de risco, comunidade e papel (intermediária: intermediação ou ponte; repasse: repasse rápido ou cadeia). **Paleta segura para daltonismo** (Okabe–Ito, com o amarelo trocado pelo preto, por contraste) e formas por comunidade. Preferência salva no navegador; vai para o cadastro do usuário na Fase 5 |
| Animação dos padrões | Interativa, não GIF: as transações reais do padrão, em ordem cronológica, com valor e data na seta e um ponto percorrendo a ligação. Reproduzir, pausar, anterior, próximo, reiniciar e velocidade (0,5×, 1×, 2×). Desenho próprio por tipo: cadeia em linha, circuito em círculo, fan-in e fan-out em estrela, repasse com a entrada à esquerda e as saídas à direita |
| Desempenho | Biblioteca de cerca de 133 KB compactada, só na tela Rede. 300 contas desenhadas e organizadas em cerca de 1,3 s |

**Validação do grupo (Fase 3):** foram testados a navegação (zoom, arrastar, minimapa, localizar C025 com a vizinhança), os esquemas de cores e a paleta para daltonismo, o destaque de comunidade, a animação do circuito C026 → C030 com os controles e o grafo da comunidade 4.

**Observação:** o sigma.js (WebGL), citado no plano para redes de milhares de contas, não foi necessário. Com o limite de 300 transações da Fase 6, o Cytoscape atende com folga.

## Fase 2: o que foi entregue
| Item planejado | Entrega |
|---|---|
| Dashboard de risco | Nova tela **Painel de risco**: 10 regras explicáveis com evidência, limite e peso; prioridade de verificação (Alta, Moderada, Baixa); contas priorizadas com as evidências; comunidades em destaque; tabela de regras e limites. Linguagem de "indícios", nunca "fraude" |
| Regras validadas | Todas as regras encontram os cenários planejados na aba *Leia-me* da planilha (ver [matematica.md](matematica.md), seção 9) |
| Filtros dinâmicos | Painel **Período e filtros**. *Recorte* (recalcula a rede): período, tipos, faixa de valor. *Mostrar somente*: origem, destino, comunidade, prioridade, status, investigação, mínimo de transações. Dashboard, Painel de risco, Transações e Contas respondem aos filtros |
| Calendário | Atalhos (base completa, últimos 7/15/30 dias, cada mês), data inicial e final, dia específico |
| Status da investigação | Não iniciada → Em análise / Investigada / Sem indício / Encaminhada, com comentário obrigatório, responsável, histórico e auditoria. Analista e Administrador registram; os outros cargos consultam |
| Valor em R$ | Máscara no simulador e nos filtros de valor (`4500000` vira `45.000,00`); o servidor continua validando em centavos |
| Filtro de comunidades | Novo filtro na tela Transações (e no painel global) |
| Contas em análise | Ordenação por qualquer coluna (crescente ou decrescente), colunas de risco e investigação, filtro por prioridade. O detalhe da conta mostra os indícios e a investigação |
| Banco | Migração 5: `casos` e `casos_historico` |
| Desempenho | 300 transações: análise completa com as regras em cerca de 35 ms |

**Validação do grupo (Fase 2):** foram testados o Painel de risco (evidências de C001 e C016, filtro "Circuito recorrente" com os dois ciclos da planilha), o período pelo calendário (agosto) e o registro de investigação.

**Ficaram para as fases seguintes, como no plano:**

- exportação em PDF, Excel, CSV, Word e PowerPoint: Fase 5;
- edição dos limites das regras pela tela: Fase 5, Configurações;
- modalidades PIX, TED e transferência com regras e dados bancários fictícios: Fase 4, Simulador;
- comparação lado a lado entre períodos: Fase 4.

## Fase 1: o que foi entregue
| Item planejado | Entrega |
|---|---|
| Página institucional | `/` pública (`inicio.html`): cabeçalho fixo com "Entrar" e "Criar cadastro", banner com cartão de acesso (entra sem trocar de página), números da base, como funciona (4 passos), 6 recursos, faixa "relevância estrutural não é acusação", público, segurança, 7 perguntas frequentes e rodapé institucional. Ilustrações em SVG próprio; identidade NEXO (azul-marinho, símbolo de rede, Inter), sem copiar o site de referência |
| Sistema em `/app` | O sistema saiu de `/` e foi para `/app`; links antigos com `#tela` continuam funcionando em `/app#tela` |
| Login por e-mail (D1) | O mesmo campo aceita e-mail ou CPF/CNPJ (máscara só quando são números), na tela de login, no banner, em "Esqueci minha senha" e no reenvio da confirmação. Mensagem única: "E-mail, CPF/CNPJ ou senha inválidos." |
| Entrar com Google (D2) | Botão opcional, ativado pelo `.env`. Fluxo OpenID Connect com PKCE, sem biblioteca nova. Vínculo seguro com cadastros confirmados, cadastro novo com CPF/CNPJ e telefone, e restrição opcional de domínio. Tabela `identidades_externas`, pronta também para a Microsoft no futuro |
| Segurança da sessão | Trocar a senha (pela tela, pelo link ou pelo `CRIAR_ADMIN`) desconecta os outros computadores. Nova janela **Minha senha** no sistema, com "Desconectar outros computadores" |
| Banco | Migração 4: `usuarios.versao_sessao` e tabela `identidades_externas` |
| Ferramentas | `CONFIGURAR` com seção opcional do Google; `DIAGNOSTICO` mostra se o Google está configurado |
| Testes | Novo `test_fase1.py` (Google simulado, sem internet); teste no navegador cobre a página inicial, o login por e-mail e "Minha senha" |

**Validação do grupo (Fase 1):** foram testados o envio de e-mail, cadastros com diferentes CNPJs, a recuperação de senha por e-mail, a página institucional, a visualização e as abas novas, cargos e permissões, e "Minha senha" / "Desconectar outros computadores".

**Decisões do grupo na validação:**

- **Google:** por enquanto sem acesso pelo Google. Para ativar depois, siga [instalacao-e-uso.md](instalacao-e-uso.md#3b-entrar-com-google-opcional).
- **Backup do Aiven:** feito e guardado pelo grupo.
- **Senha do Aiven:** mantida até o fim do projeto, por decisão do grupo, apesar de ter aparecido num print. O `.env` continua sendo compartilhado só por canal privado.

## Fase 0: o que foi entregue
| Item planejado | Entrega |
|---|---|
| 0.1 GitHub | Repositório reorganizado; `.gitignore` bloqueia todos os segredos |
| 0.2 Backup e migrações | `banco/backup.py` + `scripts\BACKUP.bat`; `banco/migracoes.py` com a tabela `versao_esquema` e proteção de versão |
| 0.3 Multiempresa | **Adiado** por decisão do grupo |
| 0.4 Simulação por usuário | Tabelas `simulacoes` e `simulacao_transacoes`; a lista global na memória foi removida |
| 0.5 Resultados guardados | Tabela `analises`, assinatura SHA-256, cache em memória e recarga da base a cada 60 s |
| 0.6 Desempenho | gzip, matrizes sob demanda, revalidação de estáticos; resposta de 120 KB → 11 KB |
| 0.7 Frontend em módulos | `app.js` de 1.223 linhas dividido em 8 módulos de núcleo + 11 telas carregadas sob demanda; CSS em 5 arquivos |
| 0.8 Testes | 5 conjuntos em `testes/`, incluindo o navegador; telas idênticas pixel a pixel antes e depois |
| 0.9 Hospedagem | **Adiado** (D9) |
| Extra | Configuração em `.env` (o `config.ini` antigo continua aceito), documentação em `docs/` e README em cada pasta |
