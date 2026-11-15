"""Testes da Fase 3 (lado do servidor): biblioteca do grafo e desempenho do desenho.

Executar (na raiz do projeto): python -m testes.test_fase3
O comportamento da tela (navegação, cores, minimapa, comunidade, animação) é testado
no navegador em testes/e2e/test_navegador.py.

1. Cytoscape.js copiado sem alteração (SHA-256), com a licença, servido compactado
   e baixado só pela tela Rede (nenhuma página o carrega de início).
2. Dados que a tela usa: arestas agregadas, indícios com as transações dos padrões
   animáveis, em ordem cronológica possível.
3. Desempenho: 300 contas / 300 transações desenhadas no navegador (se o Playwright estiver instalado).
"""
import hashlib
import os
import random
import tempfile
from pathlib import Path

os.environ["NEXO_BANCO"] = "local"
for _chave in [k for k in os.environ if k.startswith(("DB_", "SMTP_", "APP_URL", "GOOGLE_"))]:
    del os.environ[_chave]

from banco import conexao as db  # noqa: E402

db.SQLITE = Path(tempfile.mkdtemp()) / "fase3.db"

from app import auth, servidor  # noqa: E402
from banco import repositorio  # noqa: E402
from nucleo import analise  # noqa: E402
from nucleo.configuracao import RAIZ  # noqa: E402

VENDOR = RAIZ / "app" / "static" / "vendor" / "cytoscape"
SHA256 = "0d7e373a706f0f01d6fb7a6ccf04988c01307cee1c2f9bcc7b068e9f6b431e3f"
H = {"X-Requested-With": "NEXO"}

# ------------------------------------------------------------------ 1. biblioteca
arquivo = VENDOR / "cytoscape.esm.min.js"
assert hashlib.sha256(arquivo.read_bytes()).hexdigest() == SHA256, "cytoscape.esm.min.js foi alterado"
assert "MIT" in (VENDOR / "LICENSE").read_text(encoding="utf-8") or "Permission is hereby granted" in (VENDOR / "LICENSE").read_text(encoding="utf-8")
assert 'Gh.version="3.34.4"' in arquivo.read_text(encoding="utf-8")[-400:]

auth.iniciar_banco()
auth.cadastrar("52998224725", "Ana Admin", "ana@nexo.test", "11912345678", "Senha123", "Senha123",
               cargo="administrador", email_confirmado=True)
c = servidor.app.test_client()
assert c.post("/auth/entrar", headers=H, json={"login": "ana@nexo.test", "senha": "Senha123"}).status_code == 200
r = c.get("/static/vendor/cytoscape/cytoscape.esm.min.js", headers={"Accept-Encoding": "gzip"})
assert r.status_code == 200 and r.mimetype in ("application/javascript", "text/javascript")
assert r.headers.get("Content-Encoding") == "gzip" and len(r.get_data()) < 150_000, len(r.get_data())
for pagina in ("/", "/login", "/app"):
    assert "vendor/cytoscape" not in c.get(pagina).get_data(as_text=True)   # só a tela Rede baixa a biblioteca
print(f"ok — Cytoscape.js 3.34.4 íntegro (SHA-256), licença MIT, {len(r.get_data()) // 1024} KB compactado, carregado sob demanda")

# ------------------------------------------------------------------ 2. dados usados pela tela
dados = c.get("/api/resultados").get_json()
pares = {(a["de"], a["para"]) for a in dados["rede"]["arestas"]}
assert len(pares) == len(dados["rede"]["arestas"]) == 103                      # uma aresta por par dirigido
assert sum(a["quantidade"] for a in dados["rede"]["arestas"]) == 160
porid = {t["id"]: t for t in dados["transacoes"]}
for conta, info in dados["risco"]["contas"].items():
    for ind in info["indicios"]:
        for tid in ind.get("transacoes", []):
            assert tid in porid, (conta, ind["regra"], tid)                    # a animação acha cada transação
        if ind["regra"] in ("cadeia", "ciclo"):
            assert ind["contas"][0] and len(ind["contas"]) >= 3
        if ind["regra"] == "cadeia":                                            # cadeia: ordem cronológica
            momentos = [porid[t]["data"] + porid[t]["hora"] for t in ind["transacoes"]]
            assert momentos == sorted(momentos)
            assert all(porid[a]["para"] == porid[b]["de"] for a, b in zip(ind["transacoes"], ind["transacoes"][1:]))
circuito = next(i for i in dados["risco"]["contas"]["C026"]["indicios"] if i["regra"] == "ciclo")
assert circuito["contas"] == ["C026", "C027", "C028", "C029", "C030", "C026"] and len(circuito["transacoes"]) == 10
print("ok — arestas agregadas (103 pares, 160 transações) e padrões com as transações reais para a animação")

# ------------------------------------------------------------------ 3. desempenho no navegador (opcional)
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
if sync_playwright is None:
    print("(pulando o desenho de 300 contas no navegador: Playwright não instalado)")
else:
    import socket
    import threading
    import time

    import logging

    from werkzeug.serving import make_server

    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    random.seed(3)
    ids = [f"K{i:03d}" for i in range(300)]
    contas = [{"id": k, "com": 1 + i % 12, "degree": 2, "status": "Normal", "nivel_risco": "Baixa", "indicios": []}
              for i, k in enumerate(ids)]
    arestas = [{"de": a, "para": b, "quantidade": 1, "valor_total": round(random.uniform(100, 9000), 2)}
               for a, b in {tuple(random.sample(ids, 2)) for _ in range(300)}]
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    http = make_server("127.0.0.1", porta, servidor.app, threaded=True)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    opcoes = {"executable_path": os.environ["NEXO_CHROMIUM"]} if os.environ.get("NEXO_CHROMIUM") else {}
    with sync_playwright() as p:
        nav = p.chromium.launch(**opcoes)
        pg = nav.new_page(viewport={"width": 1366, "height": 900})
        pg.goto(f"http://127.0.0.1:{porta}/login")   # qualquer página do NEXO serve de origem para o import
        ms = pg.evaluate("""async ([contas, arestas]) => {
            const g = await import('/static/js/nucleo/grafo.js');
            const cytoscape = await g.carregarCytoscape();
            const div = document.createElement('div'); div.style.cssText = 'width:1000px;height:640px';
            document.body.appendChild(div);
            const t0 = performance.now();
            const cy = cytoscape({container: div, style: g.estilo(), elements: g.elementos(contas, arestas)});
            contas.forEach((c, i) => cy.$id(c.id).position(g.posicaoInicial(c, i, 12)));
            await new Promise(ok => { const l = cy.layout(g.LAYOUT); l.one('layoutstop', ok); l.run(); });
            return performance.now() - t0;
        }""", [contas, arestas])
        nav.close()
    http.shutdown()
    assert ms < 5000, f"{ms:.0f} ms"
    print(f"ok — desempenho: 300 contas e {len(arestas)} conexões desenhadas e organizadas em {ms:.0f} ms")
print("TESTES OK: Fase 3 — biblioteca do grafo íntegra e sob demanda, dados dos padrões e desempenho do desenho.")
