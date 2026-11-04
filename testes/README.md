# testes/ — testes automáticos

```bat
scripts\TESTAR.bat        (ou: python -m testes.executar)
```

| Arquivo | O que testa | Banco usado |
|---|---|---|
| `test_nucleo.py` | Motor matemático e API do simulador | CSV + SQLite temporário |
| `test_login.py` | Login, cadastro, e-mail, recuperação, convites, cargos, limites e auditoria | SQLite temporário |
| `test_fase0.py` | `.env`, migrações (inclusive de um banco antigo), simulação por usuário, cache, matrizes, gzip e backup | SQLite temporário |
| `test_mysql.py` | Tudo no MySQL real (só roda se o MySQL estiver configurado) | banco temporário `nexo_teste`, apagado no final |
| `e2e/test_navegador.py` | O sistema inteiro num Chromium, tela por tela (exige `requirements-dev.txt`) | SQLite temporário |
| `executar.py` | Roda todos os conjuntos e resume o resultado | — |

**Nenhum teste toca no banco `nexo` do grupo, nem no `.env` real.**

Detalhes: [docs/testes.md](../docs/testes.md).
