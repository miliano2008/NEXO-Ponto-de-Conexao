"""Testes do motor matemático (nucleo/) e da API do simulador.

Executar (na raiz do projeto): python -m testes.test_nucleo
Sempre usa os CSVs + um SQLite temporário: nunca toca no banco do grupo.
"""
import math
import os
import tempfile
from pathlib import Path

os.environ['NEXO_BANCO'] = 'local'   # testes usam CSV + SQLite temporário

import networkx as nx
import numpy as np

from banco import conexao as db

db.SQLITE = Path(tempfile.mkdtemp()) / 'teste.db'   # não toca em banco/dados/nexo.db
from banco.repositorio import carregar_dados  # noqa: E402
from nucleo.__main__ import gerar_resultados  # noqa: E402
from nucleo.analise import calcular_matrizes, construir_grafos  # noqa: E402

contas, transacoes = carregar_dados()
assert len(contas) == 40, "A base deveria ter 40 contas"
assert len(transacoes) == 160, "A base deveria ter 160 transações"
assert len({t['id'] for t in transacoes}) == 160, "IDs de transação duplicados"

grafo, sim = construir_grafos(contas, transacoes)
assert grafo.number_of_nodes() == 40
assert sum(a['quantidade'] for _,_,a in grafo.edges(data=True)) == 160
assert sum(a['centavos'] for _,_,a in grafo.edges(data=True)) == sum(t['centavos'] for t in transacoes)

ids = [c['id_conta'] for c in contas]
matrizes = calcular_matrizes(grafo, sim, ids)
assert matrizes['A'].shape == (40,40)
assert np.array_equal(matrizes['L'], matrizes['D'] - matrizes['A'])
assert np.array_equal(matrizes['L_simetrica'], matrizes['L_simetrica'].T)
assert np.allclose(matrizes['L_simetrica'].sum(axis=1), 0)

resultado = gerar_resultados()
assert len(resultado['contas']) == 40
assert len(resultado['transacoes']) == 160
assert sum(len(c['contas']) for c in resultado['comunidades']) == 40
assert all(0 <= c['score'] <= 100 for c in resultado['contas'])
assert len(resultado['espectral']['autovalores']) == 40
assert all(math.isfinite(v) for v in resultado['espectral']['autovalores'])
assert sum(v < 1e-8 for v in resultado['espectral']['autovalores']) == nx.number_connected_components(sim)

c025 = next(c for c in resultado['contas'] if c['id'] == 'C025')
assert (c025['inDeg'], c025['outDeg']) == (4, 6)
assert (c025['qtd_transacoes_entrada'], c025['qtd_transacoes_saida']) == (5, 7)
assert (c025['entrada'], c025['saida'], c025['flow']) == (20805.55, 78140.50, 98946.05)
assert abs(c025['imbalance'] - 0.57945668) < 1e-6

print('TESTES OK: dados, grafos, matrizes, Louvain, espectral, score e C025.')

# ---- Simulador web (app/servidor.py): API, período e transação simulada ----
from app import auth  # noqa: E402
from app import servidor as simulador  # noqa: E402
auth.cadastrar('52998224725', 'Analista Teste', 'analista@nexo.test', '11912345678', 'Senha123', 'Senha123', cargo='analista', email_confirmado=True)
cliente = simulador.app.test_client()
H = {'X-Requested-With': 'NEXO'}
assert cliente.post('/auth/entrar', headers=H, json={'documento': '52998224725', 'senha': 'Senha123'}).status_code == 200
base = cliente.get('/api/resultados').get_json()
assert base['dashboard']['total_transacoes'] == 160
assert cliente.get('/api/resultados?dias=7').get_json()['dashboard']['total_transacoes'] < 160
r = cliente.post('/api/transacoes', headers=H, json={'de': 'C001', 'para': 'C030', 'valor': '1000',
                                          'data': '2026-09-15', 'hora': '10:30', 'tipo': 'PIX'})
assert r.status_code == 201 and r.get_json()['impacto']
assert cliente.get('/api/resultados').get_json()['dashboard']['total_transacoes'] == 161
assert cliente.post('/api/transacoes', headers=H, json={'de': 'C001', 'para': 'C001', 'valor': '5',
                                             'data': '2026-09-15', 'hora': '10:00'}).status_code == 400
assert cliente.post('/api/transacoes', headers=H, json={'de': 'C001', 'para': 'X999', 'valor': '5',
                                             'data': '2026-09-15', 'hora': '10:00'}).status_code == 400
assert cliente.delete('/api/transacoes/T0001', headers=H).status_code == 404  # base original é protegida
cliente.post('/api/simulacao/restaurar', headers=H)
assert cliente.get('/api/resultados').get_json()['dashboard']['total_transacoes'] == 160
print('TESTES OK: simulador web (API, período, simulação, validação e restauração).')
