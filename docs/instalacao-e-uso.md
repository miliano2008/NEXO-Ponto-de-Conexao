# Instalação e uso

## 1. Primeira instalação
| Sistema | O que fazer |
|---|---|
| **Windows sem Python** | Dois cliques em **`INSTALAR_WINDOWS.bat`**. Instala o Python 3.12 só para o seu usuário, sem precisar de administrador |
| **Windows com Python 3.10+** | Dois cliques em **`iniciar.bat`** |
| **Linux Mint / Ubuntu** | `bash scripts/instalar_linux.sh` na primeira vez; depois `bash iniciar.sh` |
| **macOS** | `bash scripts/instalar_mac.sh` na primeira vez; depois `bash iniciar.sh` |

Na primeira execução, o `iniciar.bat`:

1. cria a pasta `.venv` e instala as bibliotecas do `requirements.txt`;
2. abre o assistente de configuração, que pergunta os dados do Aiven e do e-mail e cria o **`.env`**. Basta apertar Enter para usar o modo local;
3. aplica as migrações do banco;
4. pede os dados do primeiro administrador, se ainda não houver um;
5. abre o navegador em **http://127.0.0.1:5000**. Se a porta estiver ocupada, usa a próxima e mostra o endereço na janela.

> Extraia o zip inteiro antes de executar. Rodar de dentro do zip não funciona.

## 2. Conectar ao banco do grupo (Aiven)
1. No [console.aiven.io](https://console.aiven.io), abra o serviço MySQL (status **Running**) e vá em **Overview → Connection information**.
2. Copie **Host**, **Port** (não é 3306), **User** (`avnadmin`) e **Password** (começa com `AVNS_`).
3. Clique em **CA certificate → Download** e salve como **`banco\dados\ca.pem`**.
4. Rode **`scripts\CONFIGURAR.bat`** e informe os dados. O assistente testa a conexão e, se o banco estiver vazio, oferece enviar a base (equivalente a `scripts\MIGRAR_MYSQL.bat`).

Quem já recebeu o `.env` e o `ca.pem` de um colega não precisa fazer nada disso: basta colocar os dois arquivos nas pastas certas (`.env` na raiz e `ca.pem` em `banco\dados\`).

**MySQL Workbench / DBeaver:** use os mesmos Host, Port, User e Password. Em *SSL*, escolha **Require** e aponte o *SSL CA File* para o `ca.pem`. As consultas prontas estão em `banco/consultas_nexo.sql`.

**Plano gratuito do Aiven:** o serviço desliga depois de um tempo parado. Se aparecer "servidor inacessível", confira no console se ele está **Running**.

## 3. E-mail (confirmação de cadastro e "Esqueci minha senha")
1. Na conta Gmail do grupo, ative a verificação em duas etapas.
2. Crie uma **senha de app** em https://myaccount.google.com/apppasswords. São 16 letras.
3. Rode `scripts\CONFIGURAR.bat`, responda às perguntas do e-mail e cole essa senha.
4. Teste com `scripts\TESTAR_EMAIL.bat`, que manda um e-mail de teste.

Sem e-mail configurado, o administrador pode confirmar os cadastros manualmente em **Usuários e cargos**.

## 4. Atualizar o seu computador para a versão 0.4 (quem já usava a 0.3)
1. **Backup primeiro**, na versão antiga ou na nova: `scripts\BACKUP.bat` (ou `python -m banco.backup`). O arquivo fica em `banco\dados\backups\`. Basta **uma pessoa** do grupo fazer isso antes de a versão 0.4 conectar ao Aiven pela primeira vez.
2. Baixe a versão nova: `git pull`, ou **Download ZIP** numa pasta nova.
3. Traga os seus arquivos privados para a pasta nova:
   - **`ca.pem`** → `banco\dados\ca.pem` (antes ficava em `dados\`);
   - **`config.ini`** → na raiz. Ele continua funcionando; para convertê-lo em `.env`, rode `scripts\CONFIGURAR.bat`, que mostra os valores atuais como padrão.
4. Dois cliques em **`iniciar.bat`**. Na primeira vez, ele cria as 3 tabelas novas no Aiven (`simulacoes`, `simulacao_transacoes`, `analises`) e registra a versão do banco. Usuários, senhas e dados continuam iguais.
5. Depois de um colega rodar a 0.4, quem ainda tiver a 0.3 deve atualizar também. A versão antiga continua lendo o banco, mas as simulações dela não são compartilhadas com a nova.

## 5. Atalhos (pasta `scripts\`)
| Atalho | Para que serve |
|---|---|
| `iniciar.bat` (raiz) | Abre o NEXO |
| `DIAGNOSTICO.bat` | Confere Python, bibliotecas, arquivos, configuração, banco, migrações, base, administrador, e-mail e porta, e diz como corrigir |
| `CONFIGURAR.bat` | Cria ou atualiza o `.env` (Aiven e e-mail) e testa a conexão |
| `BACKUP.bat` | Cópia de segurança do banco |
| `MIGRAR_MYSQL.bat` | Envia a base (contas, transações e usuários locais) para o MySQL |
| `CRIAR_ADMIN.bat` | Cria um administrador, promove um usuário existente ou **define uma senha nova** para quem a esqueceu |
| `TESTAR_EMAIL.bat` | Testa o envio de e-mail |
| `TESTAR.bat` | Roda todos os testes automáticos |

Pela linha de comando, sempre a partir da raiz: `.venv\Scripts\python -m app`, `-m app.diagnostico`, `-m banco.backup`, `-m testes.executar`…

## 6. Cargos
| Cargo | O que pode |
|---|---|
| Administrador | Tudo, inclusive usuários, cargos e convites |
| Analista | Consultar, relatórios, exportar, simulador, configurações |
| Auditor | Consultar, relatórios, exportar, auditoria |
| Visualizador | Apenas consultar. É o padrão de quem se cadastra sem convite |

Para dar um cargo a um colega, o administrador gera um **código de convite** em *Usuários e cargos* ou altera o cargo depois do cadastro.

## 7. Problemas comuns
Rode primeiro o **`scripts\DIAGNOSTICO.bat`**: ele aponta a causa e a correção.

| Sintoma | Causa | Solução |
|---|---|---|
| "O sistema não pode encontrar o caminho especificado" ao digitar `.venv\Scripts\python` | A pasta `.venv` ainda não existe **nesta** pasta | Use `iniciar.bat` ou os atalhos, que a criam sozinhos |
| Erro estranho no `.venv`, "No Python at…" | `.venv` copiado de outro PC (pen drive, OneDrive) | Os atalhos detectam e recriam. Ou apague a pasta `.venv` |
| `'python' não é reconhecido` | Python ausente ou fora do PATH | `INSTALAR_WINDOWS.bat`, ou reinstale marcando **"Add python.exe to PATH"** |
| `ensurepip is not available` (Linux) | Falta o pacote de venv | `sudo apt install python3-venv python3-pip` |
| "usuário ou senha incorretos" no MySQL | Senha do Aiven errada, colada pela metade ou trocada no Aiven (Reset password) | `scripts\CONFIGURAR.bat`, opção **1** (lê a senha copiada, sem colar no CMD); ele também mostra a comparação caractere a caractere |
| "o banco 'nexo' não existe" | Base ainda não enviada | `scripts\MIGRAR_MYSQL.bat` |
| "O banco está na versão N do esquema, mas este NEXO conhece só até a…" | Um colega já usou uma versão mais nova e o seu código está desatualizado | Atualize o código (`git pull`) |
| "CPF/CNPJ ou senha inválidos" com usuário criado em outro PC | No modo local, cada PC tem o próprio `nexo.db` | Conecte ao Aiven (os usuários são compartilhados) ou use `CRIAR_ADMIN.bat` |
| E-mail não chega | SMTP não configurado ou senha comum em vez de senha de app | `scripts\CONFIGURAR.bat` e `scripts\TESTAR_EMAIL.bat`; veja também a caixa de spam |
| Administrador esqueceu a senha e o e-mail não funciona | O link de recuperação depende do SMTP | `scripts\CRIAR_ADMIN.bat`: informe o CPF/CNPJ, responda `s` em "Definir uma NOVA senha". Também desbloqueia a conta |
| Página em branco ou sem estilo | Abriu o arquivo HTML direto | Acesse pelo endereço `http://127.0.0.1:...` com o NEXO rodando |
| Erro ao ler a base | CSV salvo pelo Excel com outro formato | `python -m banco.exportar_excel` regenera os CSVs |

## 8. O que cada pessoa tem só no próprio computador
`.venv/`, `.env` (ou `config.ini`), `banco/dados/ca.pem`, `banco/dados/nexo.db`, `banco/dados/.chave_secreta` e `banco/dados/backups/`. **Nada disso vai para o GitHub.**
