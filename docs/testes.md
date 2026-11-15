# Testes

## Rodar tudo
```bat
scripts\TESTAR.bat              (ou: python -m testes.executar)
```
O executor roda cada conjunto separadamente e mostra `[OK]` ou `[FALHA]`, com as últimas linhas do erro.

- **Sempre roda:** `test_nucleo`, `test_login`, `test_fase0`, `test_fase1`, `test_fase2` e `test_email`. Usam CSV e SQLite **temporários**, e um `.env` de teste.
- **Só com o MySQL configurado:** `test_mysql`. Cria o banco temporário **`nexo_teste`** no mesmo servidor e o apaga no final. O banco `nexo` do grupo **não é tocado**.
- **Só com o Playwright instalado:** `e2e/test_navegador`. Instale assim:
  ```bash
  python -m pip install -r requirements-dev.txt
  python -m playwright install chromium
  ```

Cada arquivo também roda sozinho: `python -m testes.test_fase0`.

## O que cada conjunto cobre
| Arquivo | Cobertura |
|---|---|
| `test_nucleo.py` | Validação dos dados; grafo; matrizes (L = D − A); centralidades; Louvain (9 comunidades); espectral (3 componentes); score; valores esperados da conta C025; API do simulador, período e restauração |
| `test_login.py` | Validação de CPF/CNPJ e telefone; anti-CSRF; mensagem única de erro; cadastro com telefone e confirmação de e-mail obrigatória; bloqueio após 5 erros; recuperação com resposta idêntica exista ou não o cadastro; convites (cargo, limite, revogação); troca de e-mail pelo administrador; cargos valendo sem novo login; o administrador não rebaixa a si mesmo; limite por IP; auditoria |
| `test_fase0.py` | `.env` × `config.ini` antigo (BOM, `%` na senha, prioridades); migrações (banco novo, **atualização de um banco 0.2** sem perder usuários, proteção de versão); simulação **isolada por usuário**, que sobrevive ao reinício, valida antes de gravar e respeita o limite; cache e número da análise; matrizes sob demanda; recarga da base; gzip, 304 e arquivos estáticos; backup |
| `test_fase1.py` | Migração 4; página institucional pública e sistema em `/app`; login por e-mail (sem diferenciar maiúsculas) ou CPF/CNPJ; mensagem única; bloqueio pelo e-mail; recuperação pelo e-mail; trocar a senha desconecta os outros computadores (pela tela, pelo link e pelo `CRIAR_ADMIN`); "Desconectar outros computadores"; **Google simulado**: vínculo, segunda entrada, `state`/`nonce`/PKCE, e-mail não verificado, cadastro com e-mail pendente recusado, cadastro novo sem senha, usuário desativado e restrição de domínio |
| `test_fase2.py` | **Gabarito da planilha** (cada cenário planejado encontrado pela regra certa); cada regra em redes pequenas montadas à mão; percentil e níveis; recorte pela API (datas, dia, tipos, valor, combinado e erros); investigação (comentário obrigatório, histórico, permissões, auditoria); **desempenho com 300 transações** |
| `test_email.py` | Servidor SMTP falso, que imita as respostas do Gmail: senha recusada (535), tentativas demais (454), conexão derrubada no início, porta fechada, envio real de um e-mail de confirmação, e o diagnóstico rápido do `iniciar.bat` sem fazer login no Gmail |
| `test_mysql.py` | No MySQL real: migração, dados idênticos aos CSVs, login, cadastro com confirmação, recuperação, convites, cargos e auditoria |
| `e2e/test_navegador.py` | Num Chromium: página inicial (FAQ e acesso rápido); login por CPF com máscara e por e-mail; "Minha senha"; calendário e filtros (atalhos, mês, erro de datas, limpar, comunidade); painel de risco (evidência do fan-in, filtro por regra); ordenação das contas; registro da investigação; máscara de R$ no simulador; as 11 telas (módulos sob demanda); grafo com 40 nós; matrizes; painel da conta; as 7 conferências da validação matemática; simulador (161 → 160 após restaurar); período; limiares; tema escuro; navegação por endereço; sair. Falha se aparecer qualquer erro de JavaScript |

## Validação visual da reorganização (Fase 0)
Antes e depois da divisão do `app.js` e do `style.css`, as telas foram fotografadas e comparadas pixel a pixel:

| Tela | Resultado |
|---|---|
| Computador | 24 de 24 telas idênticas |
| Celular | 6 de 6 telas idênticas |

O único texto alterado de propósito depois disso foi o da tela Configurações → Sobre (versão 0.4 e nomes de arquivos novos).

## Antes de enviar uma mudança
1. `scripts\TESTAR.bat` sem falhas.
2. Mudou a matemática? Atualize os valores esperados em `test_nucleo.py` e aumente `VERSAO_MOTOR`.
3. Mudou o banco? Crie uma migração nova e um teste em `test_fase0.py`.
4. Criou uma tela? Acrescente-a ao `e2e/test_navegador.py`.
