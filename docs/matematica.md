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

`VERSAO_MOTOR` (hoje "1.0") identifica a versão destas regras. Ao mudar qualquer fórmula, aumente o número: os resultados guardados com a versão anterior deixam de ser reaproveitados.
