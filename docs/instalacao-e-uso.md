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

**Endereços:** `/` é a página institucional, com um cartão para entrar direto; `/app` é o sistema; `/login` é a tela de acesso completa.

**Para entrar**, use o **e-mail** ou o **CPF/CNPJ** do cadastro, com a senha. Para trocar a senha depois de entrar, clique em **Minha senha**, no rodapé da barra lateral. A troca desconecta os outros computadores em que você estava conectado.

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

## 3b. Entrar com Google (opcional)
Sem esta configuração, o NEXO funciona normalmente e o botão do Google simplesmente não aparece.

1. Acesse https://console.cloud.google.com com a conta Google que vai administrar o projeto e crie um projeto (ex.: "NEXO").
2. Em **APIs e serviços → Tela de permissão OAuth**, escolha **Externo**. Preencha o nome do app ("NEXO"), o e-mail de suporte e o e-mail do desenvolvedor, e salve.
   - Em **Usuários de teste**, adicione os e-mails do grupo. Enquanto o app estiver em modo de teste, **só esses e-mails conseguem entrar**, o que basta para o grupo e para a banca.
3. Em **APIs e serviços → Credenciais → Criar credenciais → ID do cliente OAuth**, escolha **Aplicativo da Web**.
   - Em **URIs de redirecionamento autorizados**, cadastre **exatamente**: `http://127.0.0.1:5000/auth/google/retorno`.
   - Precisa ser `127.0.0.1` (não `localhost`) e a porta 5000, os mesmos do `APP_URL_BASE` no `.env`.
4. Copie o **ID do cliente** (termina com `.apps.googleusercontent.com`) e a **Chave secreta do cliente** (começa com `GOCSPX-`).
5. Rode `scripts\CONFIGURAR.bat`, aperte Enter nas partes que não mudam e responda **s** em "Configurar o botão 'Entrar com Google'". Para a chave secreta, use a **opção 1** (área de transferência).
   - Opcional: restrinja a um domínio (ex.: `empresa.com.br`) para aceitar só e-mails desse domínio.
6. Reinicie o NEXO. O botão **Entrar com Google** aparece na página inicial e na tela de login. O `scripts\DIAGNOSTICO.bat` mostra se está configurado.

**Como funciona para o usuário:**

- Se o e-mail do Google já tem cadastro **confirmado** no NEXO, a conta é vinculada e a pessoa entra.
- Se não há cadastro, ela completa o cadastro com CPF/CNPJ e telefone (e o código de convite, se tiver) e entra como Visualizador, ou com o cargo do convite. Não é criada senha NEXO; se quiser uma, use "Esqueci minha senha".
- Se o e-mail tem cadastro ainda não confirmado, o Google é recusado até a pessoa confirmar o e-mail pelo login com senha. É uma proteção contra roubo de conta.

**Cuidados:** a chave secreta fica só no `.env`, que não vai para o GitHub. Quem usar outra porta (ex.: 5001, porque a 5000 estava ocupada) recebe erro de endereço de retorno no Google. Feche o outro programa que usa a porta 5000.

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
| Administrador | Tudo, inclusive usuários, cargos, convites, os limites das regras por modalidade e os limites das regras de risco |
| Analista | Consultar, relatórios, exportar, simulador, configurações e registrar a investigação das contas |
| Auditor | Consultar (inclusive o histórico das investigações), relatórios, exportar, auditoria |
| Visualizador | Apenas consultar. É o padrão de quem se cadastra sem convite |

Para dar um cargo a um colega, o administrador gera um **código de convite** em *Usuários e cargos* ou altera o cargo depois do cadastro.

**Preferências** (botão na barra lateral, para todos os cargos): tema, tamanho do texto, fonte, contraste alto, menos animação, cores do grafo e formato preferido do relatório. Ficam salvas no cadastro e valem em qualquer computador.

### Relatórios (versão 0.9)
- **Relatório da análise:** tela *Relatórios* → escolha PDF, Excel, Word, PowerPoint ou CSV. Usa o período, os filtros e a simulação que estiverem em uso.
- **Relatório da comparação:** tela *Histórico e comparação* → compare dois períodos ou cenários → botões "Baixar o relatório desta comparação".
- Os gráficos do Excel, do Word e do PowerPoint são editáveis (botão direito → *Editar dados*). O CSV vem num `.zip`, um arquivo por tabela.
- Na primeira abertura da versão 0.9, o `iniciar.bat` instala 4 bibliotecas novas (cerca de 15 MB): é preciso internet nessa vez.

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
| "E-mail, CPF/CNPJ ou senha inválidos" com usuário criado em outro PC | No modo local, cada PC tem o próprio `nexo.db` | Conecte ao Aiven (os usuários são compartilhados) ou use `CRIAR_ADMIN.bat` |
| "o servidor RECUSOU o usuário ou a senha" (535) | Senha de app errada, apagada (o Google apaga as senhas de app quando a senha da conta muda) ou criada em outro Gmail | Crie uma senha de app nova no mesmo Gmail do `SMTP_USER` e rode `scripts\CONFIGURAR.bat` (opção 1) |
| "TENTATIVAS DEMAIS" (454) | Muitos testes seguidos com senha errada | Espere cerca de 1 hora sem testar; se continuar, crie uma senha de app nova |
| "fechou a conexão logo no início" | Porta e segurança trocadas, ou a rede/antivírus bloqueando | 587 + `starttls` (ou 465 + `ssl`); teste no hotspot do celular; desligue a "proteção de e-mail" do antivírus por um minuto |
| E-mail não chega | SMTP não configurado ou senha comum em vez de senha de app | `scripts\CONFIGURAR.bat` e `scripts\TESTAR_EMAIL.bat`; veja também a caixa de spam |
| Administrador esqueceu a senha e o e-mail não funciona | O link de recuperação depende do SMTP | `scripts\CRIAR_ADMIN.bat`: informe o CPF/CNPJ, responda `s` em "Definir uma NOVA senha". Também desbloqueia a conta |
| "redirect_uri_mismatch" ao entrar com Google | O endereço de retorno cadastrado no Google é diferente do usado pelo NEXO | Cadastre exatamente `http://127.0.0.1:5000/auth/google/retorno` e confira o `APP_URL_BASE` no `.env` |
| "Acesso bloqueado: o app não concluiu a verificação do Google" | O e-mail não está na lista de usuários de teste | Google Cloud → Tela de permissão OAuth → Usuários de teste → adicione o e-mail |
| Página em branco ou sem estilo | Abriu o arquivo HTML direto | Acesse pelo endereço `http://127.0.0.1:...` com o NEXO rodando |
| Erro ao ler a base | CSV salvo pelo Excel com outro formato | `python -m banco.exportar_excel` regenera os CSVs |

## 8. O que cada pessoa tem só no próprio computador
`.venv/`, `.env` (ou `config.ini`), `banco/dados/ca.pem`, `banco/dados/nexo.db`, `banco/dados/.chave_secreta` e `banco/dados/backups/`. **Nada disso vai para o GitHub.**
