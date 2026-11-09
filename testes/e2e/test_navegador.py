"""Teste de ponta a ponta no navegador (Chromium via Playwright).

Executar (na raiz do projeto):
    python -m pip install -r requirements-dev.txt
    python -m playwright install chromium          # uma vez
    python -m testes.e2e.test_navegador

Sobe um NEXO temporário (CSV + SQLite numa pasta temporária, porta livre), entra
como administrador e percorre todas as telas. Falha se aparecer erro de JavaScript,
se um módulo não carregar ou se um resultado esperado não aparecer.
Variável opcional: NEXO_CHROMIUM=/caminho/do/chrome (usa um Chromium já instalado).
"""
import os
import socket
import tempfile
import threading
from pathlib import Path

os.environ["NEXO_BANCO"] = "local"

from banco import conexao as db  # noqa: E402

db.SQLITE = Path(tempfile.mkdtemp()) / "e2e.db"

from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from app import auth, servidor  # noqa: E402

import logging  # noqa: E402

logging.getLogger("werkzeug").setLevel(logging.WARNING)  # sem o registro de cada pedido na saída

DOC, SENHA = "52998224725", "Nexo2026x"
auth.cadastrar(DOC, "Grupo NEXO", "grupo@nexo.local", "11912345678", SENHA, SENHA,
               cargo="administrador", email_confirmado=True)

with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
http = make_server("127.0.0.1", porta, servidor.app, threaded=True)
threading.Thread(target=http.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{porta}"

erros = []
opcoes = {"executable_path": os.environ["NEXO_CHROMIUM"]} if os.environ.get("NEXO_CHROMIUM") else {}
with sync_playwright() as p:
    navegador = p.chromium.launch(**opcoes)
    pg = navegador.new_page(viewport={"width": 1366, "height": 900})
    pg.on("pageerror", lambda e: erros.append(f"pageerror: {e}"))
    pg.on("console", lambda m: m.type == "error" and "401" not in m.text and erros.append(f"console: {m.text}"))

    # login com mensagem única para dados inválidos
    pg.goto(f"{BASE}/login")
    pg.fill("#docInput", DOC); pg.fill("#senhaInput", "Errada123"); pg.click("#etapa-login button[type=submit]")
    pg.wait_for_selector("#erro:not([hidden])")
    assert pg.inner_text("#erro") == "CPF/CNPJ ou senha inválidos."
    pg.fill("#senhaInput", SENHA); pg.click("#etapa-login button[type=submit]")
    pg.wait_for_url(f"{BASE}/")
    pg.wait_for_selector("#dashKpis .val")
    assert [x.inner_text() for x in pg.locator("#dashKpis .val").all()] == ["160", "40", "12", "9"]

    # todas as telas carregam (cada uma é um módulo baixado sob demanda)
    esperado = {"transacoes": "#txBody tr", "rede": "#graph .node", "contas": "#contasBody tr",
                "simulador": "#simDe option", "relatorios": "#reportGrid .card", "arquitetura": "#archFlow .flow-box",
                "config": "#sobre dt", "usuarios": "#usrBody tr", "auditoria": "#audBody tr", "dashboard": "#dashTop tr"}
    for pagina, seletor in esperado.items():
        pg.click(f"#nav button[data-page={pagina}]")
        pg.wait_for_selector(f"#page-{pagina}.active {seletor}", state="attached", timeout=10000)
    assert pg.locator("#graph .node").count() == 40

    # rede: abas, matrizes sob demanda e painel da conta
    pg.click("#nav button[data-page=rede]")
    pg.click("#redeTabs button[data-tab=matriz]")
    pg.wait_for_selector("#matFull table")
    assert "40 × 40" in pg.inner_text("#matTitulo")
    pg.select_option("#matSel", "L_simetrica"); pg.wait_for_timeout(300)
    assert "simétrica" in pg.inner_text("#matTitulo")
    assert "confere" in pg.inner_text("#espectralInfo")
    pg.click("#redeTabs button[data-tab=grafo]")
    pg.wait_for_timeout(1500)
    pg.click("#graph .node[data-id=C025]"); pg.wait_for_selector("#drawer.open")
    pg.click("#drawer [data-conta=C025]"); pg.wait_for_selector("#page-conta.active #contaHist svg")
    assert "C025" in pg.inner_text("#contaDetalhe h2")

    # relatório de validação matemática: todas as conferências passam
    pg.click("#nav button[data-page=relatorios]"); pg.click("button[data-rel='3']")
    pg.wait_for_selector("#overlay.open")
    texto = pg.inner_text("#modalBody")
    assert texto.count("✔ confere") == 7 and "diverge" not in texto, texto
    pg.keyboard.press("Escape")

    # simulador: grava, aparece no dashboard e na rede, e restaura
    pg.click("#nav button[data-page=simulador]")
    pg.select_option("#simDe", "C001"); pg.select_option("#simPara", "C030"); pg.fill("#simValor", "45000")
    pg.click("#simEnviar"); pg.wait_for_selector("#simLista button[data-remover]")
    assert pg.locator("#simImpacto tr").count() > 2
    pg.click("#nav button[data-page=dashboard]"); pg.wait_for_timeout(500)
    assert pg.locator("#dashKpis .val").first.inner_text() == "161"
    pg.click("#nav button[data-page=simulador]"); pg.click("#simRestaurar"); pg.wait_for_timeout(1200)
    pg.click("#nav button[data-page=dashboard]"); pg.wait_for_timeout(500)
    assert pg.locator("#dashKpis .val").first.inner_text() == "160"

    # período, limiares e tema
    pg.select_option("#periodSelect", "7"); pg.wait_for_timeout(1200)
    assert int(pg.locator("#dashKpis .val").first.inner_text()) < 160
    pg.select_option("#periodSelect", "0"); pg.wait_for_timeout(1200)
    pg.click("#nav button[data-page=config]")
    pg.locator("#thrA").fill("20"); pg.wait_for_timeout(300)
    pg.click("#swTheme"); pg.wait_for_timeout(200)
    assert pg.evaluate("document.documentElement.dataset.theme") == "dark"
    pg.click("#nav button[data-page=dashboard]"); pg.wait_for_timeout(300)
    assert int(pg.locator("#dashKpis .val").nth(2).inner_text()) > 12   # limiar menor → mais contas em análise

    # navegação pelo endereço (#) e saída
    pg.goto(f"{BASE}/#conta/C017"); pg.wait_for_selector("#page-conta.active #contaHist svg")
    assert "C017" in pg.inner_text("#contaDetalhe h2")
    pg.click("#btnSair"); pg.wait_for_url(f"{BASE}/login")
    navegador.close()

http.shutdown()
assert not erros, "\n".join(erros)
print("TESTES OK: navegador — login, 11 telas (módulos sob demanda), rede, matrizes, validação, simulador, "
      "período, limiares, tema e navegação.")
