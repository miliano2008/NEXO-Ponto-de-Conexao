# Frontend (interface)

HTML em `app/templates/`, estilos em `app/static/css/`, JavaScript em `app/static/js/`.

Usamos **módulos nativos do navegador** (`import`/`export`): não há npm, compilação nem empacotador. Basta editar o arquivo e recarregar a página.

## Organização do JavaScript
```text
js/
├── app.js            ponto de entrada: liga menus, botões globais e inicia (usuário → dados → tela)
├── login.js          telas de login, cadastro, esqueci e redefinir
├── nucleo/
│   ├── utilidades.js  el, esc (escapa HTML), fmtBRL, fmtNum, fmtData, pill, cores…
│   ├── estado.js      estado compartilhado + eventos ouvir/emitir
│   ├── api.js         fetch com o cabeçalho anti-CSRF e mensagens de erro
│   ├── sessao.js      usuário logado, pode(permissao), PERMISSAO_PAGINA
│   ├── dados.js       carregar() da análise, classificar() pelos limiares, obterMatrizes() sob demanda
│   ├── graficos.js    gráficos em SVG próprio (barras, linhas, rosca), sem biblioteca
│   ├── ui.js          modal, painel lateral (drawer) e avisos (toast)
│   └── roteador.js    navegação por #endereço e carregamento sob demanda das telas
└── paginas/           uma tela por arquivo
    dashboard · transacoes · rede · contas · conta · simulador · relatorios
    arquitetura · config · usuarios · auditoria
```

## Ciclo de vida de uma tela
O roteador baixa o módulo **na primeira vez** que a tela é aberta e chama:

| Função (opcional) | Quando |
|---|---|
| `iniciar()` | uma vez, ao carregar o módulo: ligar botões e campos |
| `atualizar()` | a cada análise nova (evento `dados`) |
| `reclassificar()` | quando os limiares mudam (evento `reclassificado`) |
| `mostrar(param)` | toda vez que a tela é aberta (ex.: `#conta/C025` → `mostrar("C025")`) |

## Eventos (`estado.js`)
As telas **não chamam umas às outras**: avisam por eventos.

| Evento | Quem emite | Quem ouve |
|---|---|---|
| `dados` | `dados.carregar()` | roteador → `atualizar()` de todas as telas já abertas |
| `reclassificado` | Configurações (limiares) | roteador → `reclassificar()` |
| `tema` | Configurações (claro/escuro) | Rede (redesenha o grafo) |
| `rotulos` | Configurações (nomes no grafo) | Rede |

## Atributos de navegação (em qualquer HTML gerado)
- `data-conta="C025"` abre o detalhe da conta.
- `data-goto="contas"` vai para uma tela.
- `data-simular="C025"` abre o simulador com a conta de origem.
- `data-close="modal"` ou `"drawer"` fecha o modal ou o painel lateral.

## CSS (carregado nesta ordem)
| Arquivo | Conteúdo |
|---|---|
| `tokens.css` | variáveis: cores (claro e escuro), fontes, raios, sombras |
| `base.css` | layout geral: barra lateral, topo, conteúdo |
| `componentes.css` | cartões, tabelas, botões, pílulas, modal, drawer, formulários |
| `paginas.css` | detalhes de cada tela |
| `responsivo.css` | celular e tablet (sempre por último, para prevalecer) |
| `login.css` | só na página de login |

## Como criar uma tela nova
1. Crie `js/paginas/minha.js` exportando `iniciar()` e/ou `atualizar()`.
2. Em `nucleo/roteador.js`, acrescente o título em `TITULOS` e `minha: () => import("../paginas/minha.js")` em `MODULOS`.
3. Em `index.html`, acrescente o botão `data-page="minha"` no menu e a seção `<section class="page" id="page-minha">`.
4. Se a tela exigir permissão, inclua-a em `PERMISSAO_PAGINA` (`sessao.js`) e proteja a rota no servidor.
5. Acrescente a tela em `testes/e2e/test_navegador.py`.

**Segurança:** todo texto vindo do usuário ou do banco passa por `esc()` antes de ir para o `innerHTML`.
