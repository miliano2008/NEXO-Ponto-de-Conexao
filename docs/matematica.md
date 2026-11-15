# Base matemática

O código fica em `nucleo/analise.py`. As etapas abaixo seguem a ordem de `calcular()`.

## 1. Validação dos dados
O sistema confere:

- IDs únicos;
- contas de origem e destino existentes;
- origem diferente do destino;
- valor positivo com até 2 casas decimais;
- data no formato AAAA-MM-DD;
- hora no formato HH:MM ou HH:MM:SS.

Os valores são convertidos para **centavos inteiros**, para não haver erro de arredondamento.

## 2. Grafo
- **Dirigido** `G = (V, E)`: cada conta é um nó. Várias transações de A para B formam **uma** aresta A→B, com `quantidade` e `centavos` somados.
- **Não dirigido**, só para Louvain e para a análise espectral: o peso da aresta é a quantidade de transações entre o par, somando os dois sentidos.

## 3. Matrizes (n × n, n = número de contas)
| Matriz | Definição |
|---|---|
| **A** (adjacência) | `A[i,j] = 1` se existe transação i → j |
| **W** (pesos) | `W[i,j]` = soma em R$ das transações i → j |
| **D** (grau) | diagonal com o grau de **saída** de cada conta |
| **L** (Laplaciana) | `L = D − A` (não simétrica, porque o grafo é dirigido) |
| **A_s, D_s, L_s** | versões simétricas, sem direção, usadas nos autovalores |

## 4. Métricas por conta
| Métrica | Fórmula |
|---|---|
| In/Out-Degree | número de contas distintas que enviam para a conta / que recebem dela |
| Degree | In-Degree + Out-Degree |
| InValue / OutValue | soma do que a conta recebe / envia |
| Flow | InValue + OutValue |
| Imbalance | \|InValue − OutValue\| / Flow (de 0 a 1; 0 se Flow = 0) |
| Betweenness | fração dos caminhos mínimos, contados em saltos, que passam pela conta (NetworkX, normalizada) |
| Closeness | proximidade de **saída**: quão rápido a conta alcança as outras (fórmula de Wasserman-Faust, adequada para redes desconexas) |

## 5. Comunidades (Louvain)
`louvain_communities(peso = quantidade de transações, resolution = 1, seed = 42)`. A semente fixa garante o **mesmo resultado** em todos os computadores.

Na base de demonstração, o Louvain encontra **9 comunidades**, com modularidade ≈ 0,771.

## 6. Análise espectral
Resolve `L_s · v = λ · v` com `numpy.linalg.eigh` (matriz simétrica, autovalores reais).

- O número de autovalores iguais a zero é o número de componentes conexas. A base tem 3 componentes, por isso λ₂ = 0.
- A centralidade de autovetor (maior autovalor de A_s) é mostrada como informação, mas **não entra no score**.

## 7. Score provisório (0–100)
Cada métrica é normalizada entre as contas pelo método **min-max**:

```text
norm(x) = (x − mínimo) / (máximo − mínimo)      (0 quando todas as contas são iguais)
Score   = 100 × (0,15·degree + 0,25·betweenness + 0,10·closeness + 0,25·flow + 0,25·imbalance)
```

| Status | Regra |
|---|---|
| Alta relevância | Score ≥ 70 |
| Em análise | Score ≥ 45 |
| Revisar | Score ≥ 29,7 (66% de 45) |
| Normal | abaixo disso |

Os pesos e os limiares são **provisórios**. Em Configurações é possível testar outros limiares sem mudar o código.

Como a normalização é relativa, uma transação simulada muito grande pode **diminuir** o score das outras contas: o máximo da rede muda e todas são reescaladas.

## 8. Padrões estruturais (indicadores, não acusações)
- **Fan-in:** 3 ou mais contas de origem distintas.
- **Fan-out:** 3 ou mais destinos distintos.
- **Cadeia de repasse:** sequência de 3 transferências entre 4 contas distintas (até 5 exemplos).
- **Hub:** as 3 contas com mais conexões.
- **Ponte:** as 3 contas com maior Betweenness.

## Validação
`testes/test_nucleo.py` confere valores calculados à mão em redes pequenas e os valores da base oficial. A tela **Relatórios → Validação matemática** refaz 7 conferências no navegador, como L = D − A, a simetria e os autovalores.

## 9. Indícios de risco (Fase 2, `nucleo/risco.py`)
O score do item 7 mede a **relevância estrutural**. Os indícios de risco são outra leitura: dez regras explicáveis, cada uma medindo algo concreto nos dados e devolvendo a **evidência** (o número que disparou, o limite e as transações envolvidas).

| Regra | O que mede | Limite padrão | Peso |
|---|---|---|---|
| Volume atípico | Fluxo muito acima do padrão da base | desvio robusto (mediana/MAD × 1,4826) ≥ 2,5 | 20 |
| Repasse rápido | Recebe e reenvia a maior parte logo em seguida | reenvia ≥ 80% do valor recebido em até 24 h | 20 |
| Cadeia de repasse | Transferências encadeadas em ordem cronológica (cada uma sai da conta que acabou de receber) | ≥ 4 transferências, até 7 dias entre elas | 15 |
| Circuito recorrente | Circuito que volta à origem, formado por ligações que se repetem | 3 a 5 contas; cada ligação em ≥ 2 datas | 15 |
| Recebimentos concentrados (fan-in) | Recebe de muitas contas e envia para poucas | ≥ 4 origens e ≥ 2× o número de destinos | 15 |
| Envios dispersos (fan-out) | Envia para muitas contas e recebe de poucas | ≥ 4 destinos e ≥ 2× o número de origens | 15 |
| Intermediação | Betweenness alta (hub ou ponte) | entre as 10% maiores da base | 15 |
| Ponte entre comunidades | Transaciona com outra comunidade (Louvain) | ≥ 1 transação com outra comunidade | 10 |
| Concentração no tempo | Muitas transações num intervalo curto | ≥ 3 transações em 24 h | 10 |
| Transação de valor atípico | Envia ou recebe valor muito acima do padrão | acima do percentil 95 (com 20 ou mais transações) | 10 |

- **Pontos** = soma dos pesos das regras que encontraram evidência (máximo 100).
- **Prioridade de verificação:** Alta ≥ 60 · Moderada 30–59 · Baixa 1–29 · Sem indícios = 0.
- **Comunidade em destaque:** 2 ou mais contas com prioridade moderada ou alta.
- **Percentis** pelo método do posto mais próximo, sem interpolação, para dar para conferir à mão.
- Os limites são **relativos à base**, então valem para qualquer recorte (período, tipo, faixa de valor) e para as simulações.

**Por que estas definições** (calibradas com os dados, e não escolhidas no escuro):

- **"Ciclo" puro** encontra 96 circuitos de 3 a 5 contas na base, porque as comunidades são densas e têm transferências de ida e volta. Os circuitos planejados na planilha não estão em ordem cronológica nem conservam o valor, mas **cada ligação se repete nos dois períodos**. Daí o "circuito recorrente", que reduz a 8 circuitos, entre eles os dois do gabarito.
- **"Fan-out ≥ 4 destinos"** marcava 9 contas. Exigir também "≥ 2× o número de origens" separa quem **dispersa** de quem só troca muito.

**Gabarito (aba *Leia-me* da planilha), conferido em `testes/test_fase2.py`:**

| Cenário planejado | Regra que encontra |
|---|---|
| fan-in em C001 | Recebimentos concentrados |
| fan-out em C006 e C031 | Envios dispersos |
| cadeia C011→C015 | Cadeia de repasse |
| ciclos C016→C019 e C026→C030 | Circuito recorrente |
| hub C021 | Intermediação |
| pontes C005, C010, C015, C017, C025 e C030 | Ponte entre comunidades |
| C025 | Volume atípico (o maior fluxo da base) |
| cluster C038–C040 | Nenhum indício |

**Exceção documentada:** a ponte C035→C036 não aparece, porque o Louvain coloca C036 na mesma comunidade de C035. A ligação passa a ser interna.

**Linguagem:** o painel fala em indícios e em prioridade de verificação, nunca em fraude.

`VERSAO_MOTOR` ("2.0" desde a Fase 2) identifica a versão destas regras. Ao mudar qualquer fórmula, aumente o número: os resultados guardados com a versão anterior deixam de ser reaproveitados.
