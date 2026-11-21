# app/static/vendor/ — bibliotecas de terceiros

Arquivos copiados sem alteração, servidos pelo próprio NEXO (não dependem de internet nem de CDN).

| Biblioteca | Versão | Licença | Arquivo | Onde é usada |
|---|---|---|---|---|
| [Cytoscape.js](https://js.cytoscape.org) | 3.34.4 | MIT (`cytoscape/LICENSE`) | `cytoscape/cytoscape.esm.min.js` (build ES module `dist/cytoscape.esm.min.mjs` do pacote npm) | Tela **Rede de transações** (Fase 3): baixado só quando a tela é aberta |

**Origem e conferência:** `npm pack cytoscape@3.34.4`. A integridade do pacote foi conferida com o `dist.integrity` do registro do npm:
`sha512-msY99tMY8iWTg+sIPGfSqDcPNOt4xcj+v/K/7qUFaCUxxlqnMkUYLBjRUzn9W5CU/R2hrmtJa5+UtovrEM2ctg==`

**SHA-256 do arquivo copiado** (conferido em `testes/test_fase3.py`): `0d7e373a706f0f01d6fb7a6ccf04988c01307cee1c2f9bcc7b068e9f6b431e3f`

**Para atualizar:** baixe a versão nova do mesmo jeito, confira a integridade, substitua o arquivo, atualize esta tabela, o SHA-256 (aqui e em `testes/test_fase3.py`) e rode `scripts\TESTAR.bat`.
