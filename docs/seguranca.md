# Segurança

## Segredos: o que NUNCA vai para o GitHub nem para o zip do grupo
| Arquivo | Por quê |
|---|---|
| `.env` (e `config.ini` / `config.ini.bak` antigos) | Senhas do Aiven e do e-mail |
| `banco/dados/ca.pem` | Certificado do Aiven do grupo |
| `banco/dados/.chave_secreta` | Assina os cookies de sessão. Quem tiver a chave pode forjar um login |
| `banco/dados/nexo.db` | Usuários locais (e-mails, hashes de senha) |
| `banco/dados/backups/` | Cópia completa do banco |

O `.gitignore` já bloqueia todos eles. Compartilhe o `.env` e o `ca.pem` **só por canal privado**, como uma mensagem direta.

> **Pendência:** a senha do Aiven apareceu num print durante o desenvolvimento. Antes da entrega final, use **Reset password** no console do Aiven e atualize o `.env` de cada pessoa com `scripts\CONFIGURAR.bat`.

## Login e senhas
- Senhas guardadas só como **hash scrypt** (Werkzeug), nunca em texto puro.
- Senha com no mínimo 8 caracteres, com letras e números.
- **Mensagem única** para qualquer falha: "CPF/CNPJ ou senha inválidos." A resposta para um CPF inexistente leva o mesmo tempo que a de um real.
- 5 senhas erradas bloqueiam a conta por 15 minutos.
- Limites por computador (IP): 30 tentativas de login a cada 10 min, 10 cadastros por hora, 10 pedidos de recuperação a cada 15 min.
- **Confirmação de e-mail obrigatória** (link válido por 24 h) antes do primeiro acesso.
- **Recuperação de senha:** link válido por 30 min e de uso único, com no máximo 1 e-mail por minuto. O banco guarda só o hash SHA-256 do link.
- **Convites:** o código aparece uma única vez (só o hash é guardado), tem validade e limite de usos, e pode ser revogado.
- **Sessão:** cookie HttpOnly e SameSite=Lax, válido por 8 h. Mudanças de cargo e desativação valem no pedido seguinte.
- **Anti-CSRF:** pedidos que alteram dados exigem o cabeçalho `X-Requested-With: NEXO`.
- O sistema não permite ficar sem um administrador ativo.
- Auditoria de todos os acessos, falhas, recusas por permissão e mudanças de cargo.

## Dados
- A conexão com o MySQL sempre usa SSL com o certificado do Aiven.
- Todas as consultas usam parâmetros (`?`/`%s`), nunca texto concatenado: não há injeção de SQL.
- As simulações ficam separadas por usuário: ninguém vê nem altera a simulação de outra pessoa.
- Os testes usam `NEXO_BANCO=local` ou o banco temporário `nexo_teste`, e **nunca** tocam no banco do grupo.

## Limitações conhecidas (versão local)
- Sem HTTPS: o servidor roda em `127.0.0.1`. Publicar na internet exige HTTPS (Fase de hospedagem, adiada).
- O cadastro informa quando um CPF/CNPJ ou e-mail já foi usado, sem dizer qual. Isso é necessário para o usuário entender o erro; o limite por IP reduz o abuso.
- Não há envio de SMS. O telefone é só um dado de contato para o administrador confirmar a identidade.
