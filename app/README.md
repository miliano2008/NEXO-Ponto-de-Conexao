# app/ — servidor web e ferramentas

`python -m app` (ou `iniciar.bat`) inicia o servidor em http://127.0.0.1:5000: a página institucional fica em `/` e o sistema em `/app`. Se a porta estiver ocupada, usa a próxima livre.

| Arquivo | Conteúdo |
|---|---|
| `servidor.py` | Flask: páginas, rotas `/auth/*` e `/api/*`, permissões por cargo, anti-CSRF, limite por IP e compressão gzip |
| `analises.py` | Base atual (relida a cada 60 s), cache de resultados por assinatura e rastreabilidade das análises |
| `auth.py` | Usuários, login por e-mail ou CPF/CNPJ, senhas (scrypt), versão da sessão, cargos e permissões, convites, links por e-mail, contas externas e auditoria |
| `casos.py` | Investigação (Fase 2): situação de cada conta, comentário obrigatório, histórico e auditoria |
| `google.py` | "Entrar com Google" (OpenID Connect com PKCE), sem biblioteca extra. Só ativo com `GOOGLE_CLIENT_ID` no `.env` |
| `envio_email.py` | Envio SMTP dos e-mails de confirmação e recuperação. `python -m app.envio_email` testa o envio |
| `configurar.py` | Assistente que cria o `.env` (Aiven e e-mail) e testa a conexão. `scripts\CONFIGURAR.bat` |
| `diagnostico.py` | Confere tudo o que o NEXO precisa e explica como corrigir. `scripts\DIAGNOSTICO.bat` |
| `criar_admin.py` | Cria ou promove um administrador. `scripts\CRIAR_ADMIN.bat` |
| `templates/` | `inicio.html` (página institucional, `/`), `index.html` (sistema, `/app`) e `login.html` (login, cadastro, esqueci a senha, redefinir) |
| `static/css/` | `tokens`, `base`, `componentes`, `paginas`, `responsivo`, `login` e `inicio` |
| `static/js/` | `app.js` (entrada), `login.js`, `nucleo/` (serviços compartilhados) e `paginas/` (uma tela por arquivo, carregada sob demanda) |

Rotas e permissões: [docs/api.md](../docs/api.md) · Módulos JavaScript: [docs/frontend.md](../docs/frontend.md) · Segurança: [docs/seguranca.md](../docs/seguranca.md).
