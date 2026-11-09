# API (rotas do servidor)

Servidor: `app/servidor.py` (Flask). Todas as respostas são JSON, exceto as páginas e a exportação.

**Regras gerais:**

- **Sessão:** cookie HttpOnly/SameSite=Lax, válido por 8 h. Sem sessão, a resposta é `401`. Cargo sem permissão: `403`, e a tentativa fica registrada na auditoria.
- **Anti-CSRF:** todo `POST`, `PATCH` ou `DELETE` precisa do cabeçalho `X-Requested-With: NEXO`. O `api.js` envia sozinho; sem ele, a resposta é `400`.
- **Compressão:** respostas JSON, HTML, CSS e JS acima de 1 KB vão com gzip quando o navegador aceita.
- **Erros:** `{"erro": "mensagem pronta para mostrar ao usuário"}`.

## Páginas
| Rota | Descrição |
|---|---|
| `GET /` | Sistema (sem login, redireciona para `/login`) |
| `GET /login`, `/cadastro`, `/redefinir`, `/confirmar` | Telas de acesso (`login.html`) |

## Acesso (`/auth`)
| Método e rota | Corpo | Observações |
|---|---|---|
| `POST /auth/entrar` | `documento`, `senha` | Mensagem única para qualquer falha: "CPF/CNPJ ou senha inválidos." E-mail não confirmado: `403` com `codigo: email_nao_confirmado`. Limite: 30 por IP a cada 10 min |
| `POST /auth/cadastrar` | `documento`, `nome`, `email`, `telefone`, `senha`, `confirmacao`, `convite` (opcional) | Envia o link de confirmação. Limite: 10 por IP por hora |
| `POST /auth/reenviar-confirmacao` | `documento`, `senha` | Exige CPF e senha corretos |
| `POST /auth/confirmar` | `token` | Confirma o e-mail pelo link |
| `POST /auth/esqueci` | `documento` | Resposta sempre igual, exista ou não o cadastro. Limite: 10 por IP a cada 15 min |
| `GET /auth/token?token=` | — | Valida o link de redefinição |
| `POST /auth/redefinir` | `token`, `senha`, `confirmacao` | Uso único; também confirma o e-mail |
| `POST /auth/sair` | — | Encerra a sessão |
| `GET /auth/eu` | — | Usuário logado, cargo e permissões |

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
| `GET /api/resultados?dias=N` | consultar | Análise completa **sem** as matrizes n×n. `dias=0` = base completa; 7, 15 ou 30 = últimos N dias a partir da data mais recente. Inclui a simulação do usuário |
| `GET /api/matrizes?dias=N` | consultar | Matrizes A, W, D, L e versões simétricas. Carregada só quando a aba Matrizes é aberta |
| `POST /api/transacoes` | simular | `{de, para, valor, data, hora, tipo}`. Valida, grava na simulação **do usuário** e devolve `{transacao, impacto}` (score, status e comunidade antes e depois) |
| `DELETE /api/transacoes/<id>` | simular | Remove uma transação simulada (`S0001`…). A base oficial é protegida: `404` |
| `POST /api/simulacao/restaurar` | simular | Apaga todas as transações simuladas do usuário |
| `GET /api/exportar?dias=N` | exportar | Baixa o JSON completo, com as matrizes |

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
| ver_auditoria | ✓ | — | ✓ | — |
| gerenciar_usuarios | ✓ | — | — | — |

A tabela fica em `app/auth.py` (`PERMISSOES`) e é a mesma para a API e para a interface. A interface só esconde o que o cargo não pode usar: quem decide é o servidor.
