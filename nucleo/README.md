# nucleo/ — motor matemático e configuração

Código **puro**: não acessa banco nem web. Recebe listas de contas e transações e devolve um dicionário com os resultados. Por isso pode ser testado isoladamente.

| Arquivo | Conteúdo |
|---|---|
| `analise.py` | Todas as etapas do cálculo: `validar_dados`, `construir_grafos`, `calcular_matrizes`, `calcular_metricas`, `descobrir_comunidades` (Louvain), `analise_espectral`, `score_e_ranking`, `detectar_padroes` e `calcular()`, que executa tudo. Também define `PESOS`, `LIMIAR_ANALISE` (45), `LIMIAR_ALTA` (70) e `VERSAO_MOTOR` |
| `configuracao.py` | Lê a configuração: variável de ambiente > `.env` > `config.ini` antigo. Também define os caminhos do projeto (`RAIZ`, `PASTA_DADOS`) e grava o `.env` (`salvar_env`) |
| `__main__.py` | `python -m nucleo` gera `saida/resultados_nexo.json` com a análise da base completa |

As fórmulas estão explicadas em [docs/matematica.md](../docs/matematica.md).

**Ao mudar uma fórmula:** atualize `testes/test_nucleo.py` e aumente `VERSAO_MOTOR`, para que os resultados guardados com as regras antigas não sejam reaproveitados.
