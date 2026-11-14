# scripts/ — atalhos e instaladores

Dois cliques no Windows. Todos os atalhos criam o `.venv` sozinhos se ele ainda não existir e rodam a partir da raiz do projeto.

| Arquivo | O que faz | Comando equivalente |
|---|---|---|
| `DIAGNOSTICO.bat` | Confere o ambiente e explica como corrigir problemas | `python -m app.diagnostico` |
| `CONFIGURAR.bat` | Cria/atualiza o `.env` (Aiven e e-mail) e testa | `python -m app.configurar` |
| `BACKUP.bat` | Cópia de segurança do banco em `banco/dados/backups/` | `python -m banco.backup` |
| `MIGRAR_MYSQL.bat` | Envia a base para o MySQL (Aiven) | `python -m banco.migrar_mysql` |
| `CRIAR_ADMIN.bat` | Cria ou promove um administrador; também define senha nova para quem a esqueceu | `python -m app.criar_admin` |
| `TESTAR_EMAIL.bat` | Envia um e-mail de teste | `python -m app.envio_email` |
| `TESTAR.bat` | Roda todos os testes | `python -m testes.executar` |
| `preparar.bat` | Usado pelos outros: encontra o Python, cria o `.venv` e instala as bibliotecas | — |
| `instalar_windows.ps1` | Chamado pelo `INSTALAR_WINDOWS.bat` da raiz: instala o Python 3.12 sem administrador | — |
| `instalar_linux.sh` | `bash scripts/instalar_linux.sh`: instala Python, venv e pip pelo apt/dnf e inicia | — |
| `instalar_mac.sh` | `bash scripts/instalar_mac.sh`: instala o Python e inicia | — |

Para **abrir o sistema**, use `iniciar.bat` (ou `iniciar.sh`) na raiz.
