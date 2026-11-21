# API (rotas do servidor)

Servidor: `app/servidor.py` (Flask). Todas as respostas são JSON, exceto as páginas e a exportação.

**Regras gerais:**

- **Sessão:** cookie HttpOnly/SameSite=Lax, válido por 8 h. Guarda a *versão da sessão* do usuário: quando a senha é trocada, as sessões antigas deixam de valer. Sem sessão, a resposta é `401`. Cargo sem permissão: `403`, e a tentativa fica registrada na auditoria.
- **Anti-CSRF:** todo `POST`, `PATCH` ou `DELETE` precisa do cabeçalho `X-Requested-With: NEXO`. O `api.js` envia sozinho; sem ele, a resposta é `400`.
- **Compressão:** respostas JSON, HTML, CSS e JS acima de 1 KB vão com gzip quando o navegador aceita.
- **Erros:** `{"erro": "mensagem pronta para mostrar ao usuário"}`.

## Páginas
| Rota | Descrição |
|---|---|
| `GET /` | Página institucional, pública (`inicio.html`), com acesso rápido. Quem já entrou vê "Abrir o NEXO" |
| `GET /app` | Sistema (sem login, redireciona para `/login`) |
| `GET /login`, `/cadastro`, `/redefinir`, `/confirmar` | Telas de acesso (`login.html`). `/login?etapa=esqueci` abre a recuperação; `/login?erro=` mostra o erro devolvido pelo Google |

## Acesso (`/auth`)
| Método e rota | Corpo | Observações |
|---|---|---|
| `POST /auth/entrar` | `login` (e-mail **ou** CPF/CNPJ), `senha` | `documento` ainda é aceito no lugar de `login`. Mensagem única para qualquer falha: "E-mail, CPF/CNPJ ou senha inválidos." E-mail não confirmado: `403` com `codigo: email_nao_confirmado`. Limite: 30 por IP a cada 10 min |
| `POST /auth/cadastrar` | `documento`, `nome`, `email`, `telefone`, `senha`, `confirmacao`, `convite` (opcional) | Envia o link de confirmação. Limite: 10 por IP por hora |
| `POST /auth/reenviar-confirmacao` | `login`, `senha` | Exige login e senha corretos |
| `POST /auth/confirmar` | `token` | Confirma o e-mail pelo link |
| `POST /auth/esqueci` | `login` (e-mail ou CPF/CNPJ) | Resposta sempre igual, exista ou não o cadastro. Limite: 10 por IP a cada 15 min |
| `GET /auth/token?token=` | — | Valida o link de redefinição |
| `POST /auth/redefinir` | `token`, `senha`, `confirmacao` | Uso único; também confirma o e-mail e encerra as sessões abertas |
| `POST /auth/alterar-senha` | `atual`, `nova`, `confirmacao` | Usuário logado troca a própria senha. As **outras** sessões dele são encerradas; esta continua. Senha atual errada: `400` |
| `POST /auth/encerrar-sessoes` | — | Desconecta o usuário dos outros computadores, sem trocar a senha |
| `POST /auth/sair` | — | Encerra a sessão |
| `GET /auth/eu` | — | Usuário logado, cargo, permissões e se o Google está configurado |

## Entrar com Google (`/auth/google`)
Só funciona com `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` no `.env`; sem eles, as rotas respondem `404` e o botão não aparece.

| Método e rota | Uso |
|---|---|
| `GET /auth/google` | Gera `state`, `nonce` e PKCE (S256), guarda na sessão e redireciona para o Google. Limite de tentativas igual ao login |
| `GET /auth/google/retorno` | O Google volta aqui. O servidor troca o código pelo `id_token` direto com o Google e confere emissor, destinatário, validade, `nonce`, e-mail verificado e domínio. Resultado: entra (→ `/app`), completa o cadastro (→ `/cadastro?google=1`) ou volta ao login com o motivo (→ `/login?erro=`) |
| `GET /auth/google/pendente` | E-mail e nome da conta Google aguardando o cadastro (vale 10 min) |
| `POST /auth/google/concluir` | `documento`, `nome`, `telefone`, `convite` (opcional). Cria o usuário com e-mail confirmado, vincula a conta Google e inicia a sessão |

**Regras de vínculo:**

- Conta Google já vinculada: entra no mesmo usuário, mesmo que o e-mail do Google mude.
- E-mail do Google igual ao de um cadastro **confirmado**: vincula e entra.
- E-mail igual ao de um cadastro **ainda não confirmado**: recusa. Isso impede que alguém cadastre o e-mail de outra pessoa e espere ela entrar pelo Google.
- Usuário desativado: recusa.

## Administração
| Método e rota | Permissão | Uso |
|---|---|---|
| `GET /api/usuarios` | gerenciar_usuarios | Lista os usuários |
| `PATCH /api/usuarios/<id>` | gerenciar_usuarios | `cargo`, `ativo`, `email`, `telefone`, `confirmar_email`. Ninguém muda o próprio cargo nem se desativa |
| `GET` / `POST /api/convites` | gerenciar_usuarios | Lista ou cria um código (`cargo`, `dias` 1–30, `max_usos` 1–50). O código aparece uma única vez |
| `DELETE /api/convites/<id>` | gerenciar_usuarios | Revoga o convite |
| `GET /api/auditoria` | ver_auditoria | Trilha de acessos |

## Análise
| Método e rota | Permissão | Uso |
|---|---|---|
| `GET /api/resultados?...` | consultar | Análise completa **sem** as matrizes n×n, já com o bloco `risco` (indícios, regras, comunidades). Recorte opcional (recalcula a rede): `dias=N` (últimos N dias), **ou** `inicio`/`fim` (AAAA-MM-DD; dia específico = mesmo valor), `tipos=PIX,TED`, `valor_min`, `valor_max`. Recorte inválido ou sem transações: `400` com a mensagem. Inclui a simulação do usuário |
| `GET /api/matrizes?...` | consultar | Matrizes A, W, D, L e versões simétricas. Carregada só quando a aba Matrizes é aberta |
| `POST /api/transacoes/validar` | simular | Prévia sem gravar: `{de, para, valor, data, hora, tipo, repetir: {vezes, a_cada_dias}}` → datas das repetições, verificações de cada regra, instituições e se é a mesma |
| `POST /api/transacoes` | simular | `{de, para, valor, data, hora, tipo, repetir?}`. Expande as repetições, aplica as regras da modalidade (bloqueio: `400` com as verificações, nada é gravado), valida no motor, grava na simulação **do usuário** e devolve `{transacao, transacoes, alertas, impacto}` |
| `DELETE /api/transacoes/<id>` | simular | Remove uma transação simulada (`S0001`…). A base oficial é protegida: `404` |
| `POST /api/simulacao/restaurar` | simular | Apaga todas as transações simuladas do usuário |
| `GET /api/modalidades` | consultar | Regras por modalidade: origem, ação, limites, fonte, quem ajustou e quantas transações da base ficariam fora (informativo) |
| `POST /api/modalidades/<regra>` | administrar_regras | `{acao, parametros}` ou `{padrao: true}`. Auditoria `regra_modalidade` |
| `GET` / `POST /api/cenarios` | simular | Lista os cenários do usuário / salva o rascunho como cenário `{nome, descricao, recorte}` |
| `GET /api/cenarios/<id>` | simular | Cenário com as transações, os dois resultados e a comparação entre eles. Só do dono (`404` para os outros) |
| `POST /api/cenarios/<id>/restaurar` | simular | Substitui a simulação em andamento pelas transações do cenário |
| `DELETE /api/cenarios/<id>` | simular | Exclui o cenário |
| `GET /api/comparar?a=&b=` | consultar | Comparação lado a lado. Fontes: `base`, `recorte:AAAA-MM-DD:AAAA-MM-DD`, `rascunho`, `cenario:ID`, `cenario:ID:base`. Simulações e cenários exigem `simular` |
| `GET /api/relatorio?tipo=analise&formato=...&<recorte>` | exportar | Relatório da análise atual (recorte + simulação do usuário). `formato`: `pdf`, `xlsx`, `csv` (zip), `docx` ou `pptx`. Auditoria `relatorio` |
| `GET /api/relatorio?tipo=comparacao&a=&b=&formato=...` | exportar | Relatório da comparação; fontes como em `/api/comparar` (simulações e cenários exigem `simular`) |
| `GET /api/exportar?...` | exportar | Baixa o JSON completo, com as matrizes, no mesmo recorte |
| `GET /api/parametros-risco` | consultar | Limites das regras de risco: nome, unidade, regras que usam, valor em vigor, padrão, faixa e quem ajustou |
| `POST /api/parametros-risco` | administrar_regras | `{valores: {chave: valor}}` (aceita vírgula decimal) ou `{padrao: true}`. Fora da faixa: `400`. A análise é recalculada com os novos limites. Auditoria `parametros_risco` |
| `GET /api/preferencias` | consultar | Preferências do usuário logado e os valores padrão |
| `PUT /api/preferencias` | consultar | `{preferencias: {...}}` (parcial; só valores conhecidos) ou `{padrao: true}` |
| `GET /api/casos` | consultar | Situação da investigação de cada conta com registro, e a lista de situações |
| `GET /api/casos/<conta>` | consultar | Situação atual e histórico (quem, quando, de → para, comentário) |
| `POST /api/casos/<conta>` | investigar | `situacao` (`em_analise`, `investigada`, `sem_indicio`, `encaminhada`) e `comentario` obrigatório (mínimo de 5 caracteres). Vai para a auditoria |

### Campos acrescentados em `/api/resultados` na versão 0.4
- `analise`: `{id, assinatura, versao_motor, duracao_ms, origem}`. `origem` é "cálculo" ou "memória"; `id` é o número da análise guardada na tabela `analises`, quando não há simulação.
- `simulacao.lista_simuladas`: apenas as transações do usuário logado.

## Cargos e permissões
| Permissão | Administrador | Analista | Auditor | Visualizador |
|---|:-:|:-:|:-:|:-:|
| consultar (dashboard, transações, rede, contas) | ✓ | ✓ | ✓ | ✓ |
| relatorios, exportar | ✓ | ✓ | ✓ | — |
| simular | ✓ | ✓ | — | — |
| configurar | ✓ | ✓ | — | — |
| investigar (mudar a situação da investigação) | ✓ | ✓ | — | — |
| administrar_regras (regras por modalidade e limites das regras de risco) | ✓ | — | — | — |
| ver_auditoria | ✓ | — | ✓ | — |
| gerenciar_usuarios | ✓ | — | — | — |

A tabela fica em `app/auth.py` (`PERMISSOES`) e é a mesma para a API e para a interface. A interface só esconde o que o cargo não pode usar: quem decide é o servidor.
