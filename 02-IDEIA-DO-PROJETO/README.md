> **Sobre esta pasta:** este é o documento da **ideia original** do NEXO, mantido como referência, junto com o `prototipo_original.html` (protótipo estático da interface; abra direto no navegador). O que foi de fato implementado e as mudanças em relação ao plano inicial, como as bibliotecas usadas e a organização das pastas, estão em [`docs/`](../docs/README.md) e no [README principal](../README.md).

# NEXO — Ponto de Conexão

## 1. Visão Geral

O **NEXO — Ponto de Conexão** é uma ferramenta de análise de redes aplicada a **transações financeiras**.

A proposta do projeto é transformar uma base de transações em uma estrutura de **rede (grafo)**, permitindo analisar como as contas se relacionam entre si e identificar quais delas possuem maior relevância estrutural dentro da rede.

No NEXO:

- **Contas** são representadas como nós (vértices);
- **Transações** são representadas como conexões (arestas);
- O sentido da transação representa a direção da conexão;
- O valor da transação pode ser utilizado como peso da conexão;
- As relações entre as contas formam uma rede que pode ser analisada matematicamente.

A ideia central é sair de uma visão tradicional baseada apenas em tabelas de transações e construir uma representação que permita compreender a **estrutura dos relacionamentos financeiros**.

O sistema foi pensado como uma ferramenta de apoio à análise, permitindo que um analista identifique contas, conexões, padrões e comunidades que mereçam uma investigação mais aprofundada.

---

## 2. Problema

Uma grande quantidade de transações financeiras pode gerar uma rede complexa de relacionamentos.

Quando essas informações são analisadas apenas em formato de tabela, pode ser difícil identificar:

- quais contas possuem maior quantidade de conexões;
- quais contas concentram grande volume de entradas ou saídas;
- quais contas funcionam como intermediárias entre diferentes grupos;
- quais contas possuem maior proximidade dentro da rede;
- quais contas pertencem a determinadas comunidades;
- quais estruturas ou padrões de relacionamento merecem atenção;
- quais contas apresentaram mudanças relevantes entre diferentes períodos.

Uma conta pode possuir muitas conexões e ser importante por sua quantidade de relacionamentos. Outra pode possuir poucas conexões, mas atuar como uma ponte entre diferentes grupos da rede.

Dessa forma, apenas observar o número de transações não é suficiente para compreender toda a estrutura existente.

### Pergunta central do projeto

> **Como transformar uma base de transações financeiras em uma rede capaz de revelar relações, padrões e contas estruturalmente relevantes?**

---

## 3. Proposta

O NEXO propõe transformar os dados de transações financeiras em uma estrutura de grafo e aplicar técnicas de análise de redes para estudar essa estrutura.

O processo pode ser representado da seguinte maneira:

```text
Dados de Transações
        ↓
Construção da Rede
        ↓
Matrizes e Estruturas
        ↓
Cálculo das Métricas
        ↓
Ranking de Relevância
        ↓
Análise de Comunidades
        ↓
Exploração das Contas
        ↓
Análise Humana
```

A partir dos dados armazenados, o sistema constrói a rede e calcula métricas capazes de representar diferentes características estruturais das contas.

---

## 4. Representação da Rede

A estrutura matemática utilizada pelo projeto é baseada em um grafo:

**G = (V, E)**

Onde:

- **V** representa o conjunto de vértices ou nós;
- **E** representa o conjunto de arestas ou conexões.

No contexto do NEXO:

```text
V = Contas
E = Transações
```

Por exemplo:

```text
Conta A001 ─────────→ Conta A002
             R$ 500
```

Nesse caso:

- A001 é a conta de origem;
- A002 é a conta de destino;
- A transação representa a conexão;
- R$ 500 representa o valor associado à conexão.

Quando várias transações são analisadas, o sistema constrói uma rede formada por diversos nós e conexões.

---

## 5. Objetivo Geral

O objetivo geral do NEXO é desenvolver uma ferramenta capaz de **analisar a estrutura de uma rede de transações financeiras**, utilizando conceitos de Teoria dos Grafos, Álgebra Linear e análise de dados para identificar contas estruturalmente relevantes e fornecer informações que apoiem a investigação humana.

O sistema deverá transformar dados brutos em informações estruturadas, permitindo uma análise mais clara das relações existentes entre as contas.

---

## 6. Objetivos Específicos

O projeto possui os seguintes objetivos específicos:

1. Organizar os dados de transações financeiras;
2. Representar as contas como nós de uma rede;
3. Representar as transações como conexões direcionadas;
4. Utilizar valores financeiros como informações associadas às conexões;
5. Construir matrizes utilizadas na análise da rede;
6. Calcular métricas de centralidade;
7. Analisar entradas e saídas das contas;
8. Calcular indicadores relacionados ao fluxo financeiro;
9. Identificar comunidades dentro da rede;
10. Criar um ranking de relevância estrutural;
11. Permitir a exploração individual de contas;
12. Visualizar as conexões por meio de Ego-Graphs;
13. Consultar as transações relacionadas às conexões;
14. Comparar diferentes períodos;
15. Apresentar os resultados de forma visual e compreensível;
16. Validar matematicamente os resultados obtidos.

---

## 7. Métricas de Análise

O NEXO utiliza diferentes métricas para analisar a estrutura da rede.

### 7.1 Degree

O **Degree** representa a quantidade de conexões de um nó.

Em uma rede direcionada, podemos analisar:

### In-Degree

Quantidade de conexões que chegam a uma conta.

```text
A001 ──→
A002 ──→ A005
A003 ──→
```

Nesse exemplo:

```text
In-Degree(A005) = 3
```

### Out-Degree

Quantidade de conexões que saem de uma conta.

```text
             → A006
A005 ───────→ A007
             → A008
```

Nesse exemplo:

```text
Out-Degree(A005) = 3
```

---

## 8. Fluxo Financeiro

Além da quantidade de conexões, o NEXO considera os valores financeiros associados às transações.

### InValue

Representa o valor total recebido por uma conta.

### OutValue

Representa o valor total enviado por uma conta.

### Flow

Representa o fluxo financeiro total associado à conta.

De forma conceitual:

```text
Flow = InValue + OutValue
```

Essas informações permitem analisar não apenas quantas conexões uma conta possui, mas também o volume financeiro associado aos seus relacionamentos.

---

## 9. Diferença e Imbalance

O projeto também considera a relação entre os valores recebidos e enviados.

A diferença pode ser representada por:

```text
Diferença = |InValue - OutValue|
```

O indicador de Imbalance pode ser representado conceitualmente por:

```text
Imbalance = Diferença / Flow
```

Esses indicadores permitem observar se existe maior concentração de valores recebidos ou enviados por determinada conta.

Os resultados devem ser interpretados dentro do contexto da rede e **não representam, isoladamente, uma confirmação de irregularidade ou fraude**.

---

## 10. Betweenness Centrality

A **Betweenness Centrality** mede a importância de um nó como intermediário entre diferentes partes da rede.

Uma conta pode não possuir o maior número de conexões, mas ainda assim apresentar grande importância estrutural por conectar diferentes grupos.

Exemplo:

```text
A001 → A002 → A003
```

Nesse caso, A002 está entre A001 e A003.

Em redes maiores, esse conceito pode ajudar a identificar contas que funcionam como **pontes estruturais**.

---

## 11. Closeness Centrality

A **Closeness Centrality** representa a proximidade de um nó em relação aos demais nós da rede.

De maneira simplificada:

- **Degree** → quantidade de conexões;
- **Betweenness** → papel de ponte;
- **Closeness** → proximidade na rede.

A utilização conjunta dessas métricas permite obter diferentes perspectivas sobre a importância estrutural de uma conta.

---

## 12. Comunidades

O NEXO também prevê a identificação de **comunidades** dentro da rede.

Para isso, poderá ser utilizado o algoritmo de **Louvain**, que busca identificar grupos de nós com maior concentração de relacionamentos entre seus próprios integrantes.

Exemplo:

```text
Comunidade A

A001 ── A002
 │       │
 A003 ── A004


Comunidade B

A010 ── A011
 │       │
 A012 ── A013
```

A análise de comunidades permite observar:

- quais contas pertencem ao mesmo grupo;
- como as contas se relacionam internamente;
- quais conexões existem entre comunidades diferentes;
- como uma conta se posiciona dentro de sua comunidade.

---

## 13. Ego-Graph

Uma das principais funcionalidades planejadas para o NEXO é o **Ego-Graph**.

O Ego-Graph permite selecionar uma conta específica e visualizar suas conexões diretas.

Exemplo:

```text
             A002
              ↓
A003 ─────→ A001 ─────→ A005
              ↓
             A006
```

Ao selecionar A001, o sistema deverá permitir analisar:

- contas que enviaram recursos para A001;
- contas que receberam recursos de A001;
- conexões de entrada;
- conexões de saída;
- valores das transações;
- datas e horários;
- tipos de transação;
- comunidade da conta;
- métricas estruturais;
- dados brutos relacionados às transações.

Essa funcionalidade permite que o analista saia de uma visão geral e aprofunde a análise de uma conta específica.

---

## 14. Padrões Estruturais

O NEXO poderá auxiliar na identificação de padrões existentes na rede.

### Fan-In

Várias contas enviando recursos para uma mesma conta.

```text
A001 ──→
A002 ──→ A010
A003 ──→
A004 ──→
```

### Fan-Out

Uma conta enviando recursos para diversas outras contas.

```text
             → A002
            /
A001 ─────→ A003
            \
             → A004
```

### Cadeia

Uma sequência de transferências:

```text
A001 → A002 → A003 → A004
```

### Ciclo

Conexões que formam um circuito:

```text
A001 → A002
 ↑       ↓
 └── A003
```

Esses padrões são utilizados como **indicadores estruturais para análise** e não devem ser interpretados automaticamente como evidência de fraude.

---

## 15. Ranking de Relevância Estrutural

O NEXO deverá possuir um ranking que organize as contas de acordo com sua relevância estrutural na rede.

O ranking poderá considerar diferentes indicadores, como:

- Degree;
- In-Degree;
- Out-Degree;
- Betweenness;
- Closeness;
- Flow;
- InValue;
- OutValue;
- Comunidade;
- Outros indicadores definidos durante o desenvolvimento.

O objetivo é permitir que o analista identifique rapidamente quais contas apresentam maior relevância dentro da estrutura analisada.

O ranking deverá apresentar as métricas utilizadas para justificar a posição de cada conta.

---

## 16. Matrizes

A análise do NEXO também utiliza conceitos de Álgebra Linear.

Entre as estruturas consideradas estão:

### Matriz de Adjacência

Representa as conexões existentes entre os nós.

### Matriz de Pesos

Representa informações associadas às conexões, como valores financeiros.

### Matriz de Grau

Representa os graus dos nós.

### Matriz Laplaciana

O projeto considera a relação:

```text
L = D - A
```

Onde:

- **L** representa a matriz Laplaciana;
- **D** representa a matriz de grau;
- **A** representa a matriz de adjacência.

Essas estruturas permitem conectar os conceitos matemáticos estudados no projeto à análise prática da rede.

---

## 17. Autovalores e Autovetores

O projeto também considera conceitos de **autovalores e autovetores** para complementar a análise matemática da rede.

Esses conceitos serão utilizados de acordo com a necessidade da modelagem e deverão ser validados para garantir a precisão dos resultados.

---

## 18. Comparação entre Períodos

O NEXO deverá permitir comparar a estrutura da rede entre diferentes períodos.

Por exemplo:

```text
Período A             Período B

Ranking: 45           Ranking: 8
Degree: 4             Degree: 15
Betweenness: 0,03     Betweenness: 0,18
```

A comparação poderá apresentar:

- mudança de posição no ranking;
- alteração do Degree;
- alteração do Betweenness;
- alteração do Closeness;
- alteração do fluxo financeiro;
- mudança de comunidade;
- alteração do papel estrutural da conta.

Essa funcionalidade permite observar mudanças no comportamento estrutural de uma conta ao longo do tempo.

---

## 19. Dashboard

O sistema deverá possuir uma visão inicial de Dashboard contendo informações gerais da rede.

Entre os indicadores previstos estão:

- quantidade de contas;
- quantidade de transações;
- volume financeiro;
- quantidade de comunidades;
- contas mais relevantes;
- principais métricas;
- informações sobre a estrutura da rede.

O Dashboard será o ponto inicial da análise.

A partir dele, o usuário poderá selecionar uma conta e aprofundar a investigação.

---

## 20. Fluxo de Investigação

O fluxo principal do usuário dentro do NEXO foi definido da seguinte forma:

```text
Dashboard
    ↓
Ranking de Relevância
    ↓
Seleção da Conta
    ↓
Ego-Graph
    ↓
Conexões
    ↓
Detalhes da Transação
    ↓
Comunidade
    ↓
Comparação entre Períodos
    ↓
Análise Humana
```

Esse fluxo permite começar com uma visão macro da rede e chegar até os detalhes de uma determinada transação.

---

## 21. Usuários do Sistema

O NEXO foi pensado para apoiar profissionais que trabalham com análise de redes e transações financeiras.

Entre os possíveis usuários estão:

- Analistas de Compliance;
- Analistas de Risco;
- Auditores;
- Profissionais de Inteligência;
- Cientistas de Dados;
- Equipes responsáveis pela análise de transações.

---

## 22. Tecnologias

As principais tecnologias planejadas para o projeto são:

### Python

Linguagem principal utilizada no desenvolvimento.

### NetworkX

Biblioteca utilizada para construção e análise dos grafos.

### NumPy

Utilizada para operações matemáticas, matrizes e vetores.

### Pandas

Utilizada para manipulação e tratamento dos dados.

### Matplotlib

Utilizada para visualizações e gráficos.

### MySQL

Banco de dados utilizado para armazenamento das informações das transações.

### Python-dotenv

Utilizada para gerenciamento das variáveis de ambiente.

---

## 23. Estrutura Inicial do Projeto

O repositório foi organizado para separar as principais responsabilidades:

```text
NEXO-Ponto-de-Conexao/

├── nucleo/
├── banco/
├── app/
├── testes/
├── docs/
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

### nucleo/

Responsável pela lógica principal do projeto, incluindo processamento e análise matemática da rede.

### banco/

Responsável pelos elementos relacionados ao banco de dados e às consultas.

### app/

Responsável pela aplicação e pela interação com o usuário.

### testes/

Responsável pelos testes e validações do sistema.

### docs/

Responsável pela documentação técnica e materiais do projeto.

---

## 24. Validação

A precisão dos resultados matemáticos é um dos requisitos do projeto.

Para validar o sistema, serão utilizados:

### Rede de teste

Uma pequena rede será construída para que os cálculos possam ser realizados manualmente.

### Validação matemática

Os resultados produzidos pelo sistema serão comparados com valores calculados manualmente.

### Validação com bibliotecas

Quando aplicável, os resultados poderão ser comparados com bibliotecas especializadas, como o NetworkX.

### Validação do banco

Os dados utilizados no grafo deverão ser comparados com os registros existentes no banco de dados, garantindo que não existam transações duplicadas ou omitidas.

### Casos extremos

Também serão considerados cenários como:

- contas isoladas;
- estruturas em estrela;
- cadeias;
- ciclos;
- contas centrais;
- redes com comunidades.

---

## 25. Limites do Projeto

O NEXO é uma ferramenta de **análise e apoio à investigação**.

O sistema não tem como objetivo:

- bloquear transações;
- determinar automaticamente que uma conta é fraudulenta;
- substituir um analista humano;
- realizar acusações;
- tomar decisões financeiras automaticamente.

Uma conta apresentar alta relevância estrutural não significa, por si só, que exista fraude ou irregularidade.

Os resultados devem ser interpretados considerando o contexto dos dados e a análise humana.

---

## 26. Resultado Esperado

Ao final do desenvolvimento, espera-se que o NEXO seja capaz de transformar uma base de transações financeiras em uma representação estruturada da rede.

O usuário deverá conseguir:

1. Visualizar informações gerais da rede;
2. Identificar contas estruturalmente relevantes;
3. Consultar as métricas utilizadas;
4. Selecionar uma conta;
5. Visualizar seu Ego-Graph;
6. Explorar suas conexões;
7. Consultar os detalhes das transações;
8. Identificar comunidades;
9. Observar padrões estruturais;
10. Comparar diferentes períodos;
11. Utilizar os resultados para apoiar uma investigação.

---

## 27. Conceito Central

O conceito central do NEXO pode ser resumido em:

> **Transformar transações em conexões, conexões em estruturas e estruturas em informações para análise.**

O projeto busca tornar visível aquilo que uma tabela tradicional de transações pode esconder: **a estrutura dos relacionamentos entre as contas**.

Dessa forma, o NEXO conecta conceitos de:

**Matemática + Teoria dos Grafos + Álgebra Linear + Programação + Banco de Dados + Análise de Dados + Visualização**

para desenvolver uma solução acadêmica capaz de transformar dados complexos em informações estruturadas para apoiar a análise humana.
