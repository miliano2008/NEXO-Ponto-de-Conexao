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

from banco import backup  # noqa: E402
from banco import conexao as db  # noqa: E402

db.SQLITE = Path(tempfile.mkdtemp()) / "e2e.db"
backup.PASTA_BACKUPS = db.SQLITE.parent / "backups"   # backups da importação ficam na pasta temporária

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


def esperar_modal_fechar(pg):
    """Espera a janela (modal) fechar; se não fechar, mostra o que ficou na tela (erro do formulário, aviso)."""
    try:
        pg.wait_for_selector("#overlay:not(.open)", state="attached", timeout=30000)
    except Exception as erro:
        raise AssertionError(f"A janela não fechou. Título: {pg.inner_text('#modalTitle')!r} · "
                             f"conteúdo: {pg.inner_text('#modalBody')[:300]!r} · aviso: {pg.inner_text('#toast')!r}") from erro


opcoes = {"executable_path": os.environ["NEXO_CHROMIUM"]} if os.environ.get("NEXO_CHROMIUM") else {}
with sync_playwright() as p:
    navegador = p.chromium.launch(**opcoes)
    pg = navegador.new_page(viewport={"width": 1366, "height": 900})
    pg.on("pageerror", lambda e: erros.append(f"pageerror: {e}"))
    # 400/401 são respostas esperadas nos testes de senha errada; qualquer outro erro falha o teste
    pg.on("console", lambda m: m.type == "error" and not any(s in m.text for s in ("status of 400", "status of 401"))
          and erros.append(f"console: {m.text}"))

    # página institucional: pública, com FAQ e acesso rápido no banner
    pg.goto(f"{BASE}/")
    assert "Enxergue a estrutura" in pg.inner_text("h1")
    pg.click("#faq summary >> nth=0"); assert pg.locator("#faq details[open]").count() == 1
    pg.click("#faq summary >> nth=1"); pg.wait_for_timeout(200)
    assert pg.locator("#faq details[open]").count() == 1                      # uma resposta aberta por vez
    pg.fill("#hLogin", "grupo@nexo.local"); pg.fill("#hSenha", "Errada123"); pg.click("#hEntrar")
    pg.wait_for_selector("#hErro:not([hidden])")
    assert pg.inner_text("#hErro") == "E-mail, CPF/CNPJ ou senha inválidos."

    # tela de login: CPF com máscara, mensagem única; entra pelo e-mail
    pg.goto(f"{BASE}/login")
    pg.fill("#docInput", DOC); assert pg.input_value("#docInput") == "529.982.247-25"
    pg.fill("#senhaInput", "Errada123"); pg.click("#etapa-login button[type=submit]")
    pg.wait_for_selector("#erro:not([hidden])")
    assert pg.inner_text("#erro") == "E-mail, CPF/CNPJ ou senha inválidos."
    pg.fill("#docInput", "grupo@nexo.local"); assert pg.input_value("#docInput") == "grupo@nexo.local"
    pg.fill("#senhaInput", SENHA); pg.click("#etapa-login button[type=submit]")
    pg.wait_for_url(f"{BASE}/app")
    pg.wait_for_selector("#dashKpis .val")
    assert [x.inner_text() for x in pg.locator("#dashKpis .val").all()] == ["160", "40", "12", "9"]

    # todas as telas carregam (cada uma é um módulo baixado sob demanda)
    esperado = {"risco": "#riscoBody tr", "historico": "#cmpA option", "transacoes": "#txBody tr", "rede": "#graph canvas", "contas": "#contasBody tr",
                "simulador": "#simDe option", "relatorios": "#reportGrid .card", "arquitetura": "#archFlow .flow-box",
                "config": "#sobre dt", "usuarios": "#usrBody tr", "auditoria": "#audBody tr", "importacao": "#impBase dt", "dashboard": "#dashTop tr"}
    for pagina, seletor in esperado.items():
        pg.click(f"#nav button[data-page={pagina}]")
        pg.wait_for_selector(f"#page-{pagina}.active {seletor}", state="attached", timeout=10000)
    CY = "document.getElementById('graph').cy"
    pg.wait_for_function(f"{CY} && {CY}.nodes().length === 40")
    assert pg.evaluate(f"{CY}.edges().length") == 103                     # conexões dirigidas distintas

    # rede: abas, matrizes sob demanda e painel da conta
    pg.click("#nav button[data-page=rede]")
    pg.click("#redeTabs button[data-tab=matriz]")
    pg.wait_for_selector("#matFull table")
    assert "40 × 40" in pg.inner_text("#matTitulo")
    pg.select_option("#matSel", "L_simetrica"); pg.wait_for_timeout(300)
    assert "simétrica" in pg.inner_text("#matTitulo")
    assert "confere" in pg.inner_text("#espectralInfo")
    pg.click("#redeTabs button[data-tab=grafo]")
    pg.wait_for_timeout(500)

    # Fase 3 — navegação estilo mapa: localizar conta (vizinhança), ajustar, zoom, minimapa
    assert pg.locator("#minimapa canvas").count() > 0                      # minimapa desenhado
    pg.fill("#buscaConta", "C025"); pg.press("#buscaConta", "Enter")
    pg.wait_for_function("document.getElementById('grafoInfo').innerText.includes('C025: 7 conta(s)')")
    pg.wait_for_function(f"!{CY}.animated()")                             # espera a aproximação terminar
    assert pg.evaluate(f"{CY}.nodes('.apagado').length") == 40 - 8      # só C025 e os 7 vizinhos acesos
    zoom = pg.evaluate(f"{CY}.zoom()")
    pg.click("#zFit")
    pg.wait_for_function(f"{CY}.zoom() < {zoom} && !{CY}.animated()")    # "ajustar à tela" afasta (sem tempo fixo)
    z1 = pg.evaluate(f"{CY}.zoom()"); pg.click("#zIn"); assert pg.evaluate(f"{CY}.zoom()") > z1
    pg.evaluate(f"{CY}.emit('tap')")                                       # clique no fundo: rede inteira
    pg.wait_for_timeout(200)
    assert pg.evaluate(f"{CY}.nodes('.apagado').length") == 0
    # esquemas de cores: risco muda a cor; daltonismo + comunidade muda a forma do nó
    cor = pg.evaluate(f"{CY}.$id('C001').data('cor')")
    pg.select_option("#corPor", "risco"); assert pg.evaluate(f"{CY}.$id('C016').data('cor')") == "#C2263C"
    pg.select_option("#corPor", "com"); pg.select_option("#paleta", "daltonismo")
    assert pg.evaluate(f"{CY}.$id('C006').data('forma')") != pg.evaluate(f"{CY}.$id('C001').data('forma')")
    assert "Comunidade 9" in pg.inner_text("#legenda")
    pg.select_option("#corPor", "status"); pg.select_option("#paleta", "padrao")
    assert pg.evaluate(f"{CY}.$id('C001').data('cor')") == cor
    # destacar comunidade apaga as outras
    pg.select_option("#focoCom", "4"); pg.wait_for_timeout(500)
    assert pg.evaluate(f"{CY}.nodes().not('.apagado').map(n => n.id()).sort().join()") == "C016,C017,C018,C019,C020"
    pg.select_option("#focoCom", ""); pg.wait_for_timeout(200)

    # Fase 3 — animação de um padrão do gabarito (circuito C026 → C030) com controles
    pg.click("#redeTabs button[data-tab=padroes]")
    assert pg.locator("[data-animar^='ciclo:']").count() >= 2 and pg.locator("[data-animar^='fan_in:']").count() >= 1
    pg.locator("#padroesGrid li", has_text="C026 → C027 → C028 → C029 → C030").locator("[data-animar]").click()
    pg.wait_for_function("document.getElementById('animGrafo') && document.getElementById('animGrafo').cy")
    assert pg.evaluate("document.getElementById('animGrafo').cy.nodes().not('.pulso').length") == 5
    pg.wait_for_function("document.getElementById('animPasso').textContent.startsWith('Transação 2 de 10')", timeout=8000)
    pg.click("#animPlay")                                                  # pausa
    passo = pg.inner_text("#animPasso"); pg.click("#animProximo")
    assert pg.inner_text("#animPasso") != passo and pg.locator("#animLista li.on").count() == 1
    assert pg.evaluate("document.getElementById('animGrafo').cy.edges('.ativa').length") == 1
    pg.click("#animInicio"); assert pg.inner_text("#animPasso").startswith("0 de 10")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)

    # Fase 3 — grafo individual da comunidade
    pg.click("#redeTabs button[data-tab=comunidades]"); pg.click("[data-grafo-com='4']")
    pg.wait_for_function("document.getElementById('grafoCom') && document.getElementById('grafoCom').cy")
    assert pg.evaluate("document.getElementById('grafoCom').cy.nodes().length") == 5
    assert pg.evaluate("document.getElementById('grafoCom').cy.edges().length") == 14   # só as conexões internas
    pg.keyboard.press("Escape"); pg.click("#redeTabs button[data-tab=grafo]"); pg.wait_for_timeout(300)

    pg.evaluate(f"{CY}.$id('C025').emit('tap')"); pg.wait_for_selector("#drawer.open")
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
    pg.select_option("#simDe", "C001"); pg.select_option("#simPara", "C030"); pg.fill("#simValor", "4500000")
    assert pg.input_value("#simValor") == "45.000,00"                        # máscara de R$: só números
    pg.click("#simEnviar"); pg.wait_for_selector("#simLista button[data-remover]")
    pg.wait_for_function("document.getElementById('toast').classList.contains('on')")
    aviso = pg.inner_text("#toast")                                          # o aviso de sucesso aparece, e não um erro
    assert "simulada" in aviso and "conta(s) com score alterado" in aviso, aviso
    assert pg.locator("#simImpacto tr").count() > 2
    pg.click("#nav button[data-page=dashboard]"); pg.wait_for_timeout(500)
    assert pg.locator("#dashKpis .val").first.inner_text() == "161"
    pg.click("#nav button[data-page=simulador]"); pg.click("#simRestaurar"); pg.wait_for_timeout(1200)
    pg.click("#nav button[data-page=dashboard]"); pg.wait_for_timeout(500)
    assert pg.locator("#dashKpis .val").first.inner_text() == "160"

    # Fase 4 — regras por modalidade na prévia: TED num sábado às 18h fica bloqueada
    pg.click("#nav button[data-page=simulador]"); pg.wait_for_selector("#simRegras tr")
    assert pg.locator("#simRegras tr").count() == 5 and "Regulamentação" in pg.inner_text("#simRegras")
    pg.select_option("#simDe", "C001"); pg.select_option("#simPara", "C030"); pg.fill("#simValor", "4500000")
    pg.fill("#simData", "2026-09-12"); pg.fill("#simHora", "18:00"); pg.select_option("#simTipo", "TED")
    pg.wait_for_selector("#simPrevia .previa-regras li.bloqueio")
    assert pg.is_disabled("#simEnviar") and "sábado" in pg.inner_text("#simPrevia")
    assert "Banco Fictício" in pg.inner_text("#simPrevia")
    # simulação recorrente: PIX 3 vezes, a cada 7 dias
    pg.select_option("#simTipo", "PIX"); pg.fill("#simHora", "12:00"); pg.fill("#simVezes", "3"); pg.fill("#simIntervalo", "7")
    pg.wait_for_function("document.querySelector('#simPrevia .previa-datas') && !document.getElementById('simEnviar').disabled")
    assert "3 transações: 12/09, 19/09, 26/09" in pg.inner_text("#simPrevia")
    pg.click("#simEnviar"); pg.wait_for_function("document.querySelectorAll('#simLista button[data-remover]').length === 3")
    # salvar como cenário e abrir no histórico
    pg.click("#simSalvar"); pg.fill("#cnNome", "PIX semanal C001 para C030"); pg.click("#cnSalvar")
    esperar_modal_fechar(pg); pg.wait_for_timeout(300)
    pg.click("#nav button[data-page=historico]"); pg.wait_for_selector(".cenario")
    assert "PIX semanal C001 para C030" in pg.inner_text("#cenariosLista")
    pg.click("[data-ver-cenario]")
    pg.wait_for_function("document.getElementById('cmpGrafoB') && document.getElementById('cmpGrafoB').cy && document.getElementById('cmpGrafoB').cy.nodes().length === 40")
    assert pg.evaluate("document.getElementById('cmpGrafoB').cy.edges('.nova').length") >= 1   # a conexão simulada é nova
    # comparação do exemplo da planilha: C025 vira ponte entre três comunidades no período B
    pg.click("#cmpExemplo"); pg.wait_for_selector("#cmpTabela tr[data-cmp-conta=C025]")
    linha = pg.inner_text("#cmpTabela tr[data-cmp-conta=C025]")
    assert "#8 → #1" in linha and "1 → 3" in linha, linha
    assert pg.locator("#cmpResultado dd a").first.inner_text() == "C025"          # 1º em "passaram a ligar mais comunidades"
    pg.click("#cmpTabela tr[data-cmp-conta=C025]"); pg.wait_for_timeout(200)
    assert pg.evaluate("document.getElementById('cmpGrafoA').cy.$id('C025').hasClass('selecionado')")
    # Fase 5: relatório desta comparação em Word
    with pg.expect_download() as baixado:
        pg.click("#cmpExportar button[data-formato=docx]")
    assert baixado.value.suggested_filename.startswith("nexo_comparacao_") and baixado.value.suggested_filename.endswith(".docx")
    pg.click("#nav button[data-page=simulador]"); pg.click("#simRestaurar"); pg.wait_for_timeout(1200)

    # período pelo calendário (recalcula) e filtros de visualização (não recalculam)
    pg.click("#btnFiltros"); pg.wait_for_selector("#formFiltros")
    pg.click("button[data-atalho='7']"); pg.click("#fAplicar"); pg.wait_for_timeout(1500)
    assert int(pg.locator("#dashKpis .val").first.inner_text()) < 160
    assert "últimos 7 dias" in pg.inner_text("#periodLabel") and pg.inner_text("#filtrosQtd") == "1"
    pg.click("#btnFiltros"); pg.click("button[data-ini='2026-08-01']"); pg.click("#fAplicar"); pg.wait_for_timeout(1500)
    assert pg.locator("#dashKpis .val").first.inner_text() == "80"                    # agosto: 80 transações
    assert "01/08/2026 a 31/08/2026" in pg.inner_text("#periodLabel")
    pg.click("#btnFiltros"); pg.fill("#fIni", "2026-09-10"); pg.fill("#fFim", "2026-09-01"); pg.click("#fAplicar")
    pg.wait_for_selector("#fErro:not([hidden])")
    assert "data inicial é depois" in pg.inner_text("#fErro")                        # erro sem perder o recorte
    pg.click("#fLimpar"); pg.wait_for_timeout(1500)
    assert pg.locator("#dashKpis .val").first.inner_text() == "160" and pg.locator("#filtrosQtd").is_hidden()
    pg.click("#btnFiltros"); pg.select_option("#fComunidade", "1"); pg.click("#fAplicar"); pg.wait_for_timeout(500)
    assert pg.locator("#dashKpis .val").nth(1).inner_text() == "5"                    # comunidade 1: 5 contas
    assert "filtros de visualização ativos" in pg.inner_text("#filtrosAviso")
    pg.click("#limparVisual"); pg.wait_for_timeout(300)
    assert pg.locator("#dashKpis .val").nth(1).inner_text() == "40"

    # painel de risco: regras, evidências e filtro por regra
    pg.click("#nav button[data-page=risco]"); pg.wait_for_selector("#riscoBody tr[data-abrir]")
    assert pg.locator("#riscoPorRegra .barra-regra").count() == 10
    pg.click("#riscoBody tr[data-abrir=C001]"); pg.wait_for_selector(".linha-evidencia")
    assert "Recebe de 5 contas distintas" in pg.inner_text(".linha-evidencia")        # fan-in do gabarito
    pg.click(".barra-regra[data-regra=ciclo]"); pg.wait_for_timeout(200)
    ids = {x.get_attribute("data-abrir") for x in pg.locator("#riscoBody tr[data-abrir]").all()}
    assert {"C016", "C017", "C018", "C019", "C026", "C027", "C028", "C029", "C030"} <= ids, ids

    # contas: ordenar por qualquer coluna e investigação registrada na conta
    pg.click("#nav button[data-page=contas]"); pg.click("#contasHead th[data-ordem=risco]"); pg.wait_for_timeout(200)
    assert pg.locator("#contasBody tr").first.get_attribute("data-conta") == "C016"
    pg.click("#contasHead th[data-ordem=risco]"); pg.wait_for_timeout(200)              # inverte
    assert pg.locator("#contasBody tr").first.get_attribute("data-conta") != "C016"
    pg.goto(f"{BASE}/app#conta/C016"); pg.wait_for_selector("#formInvest")
    pg.select_option("#invSituacao", "encaminhada"); pg.click("#invSalvar")
    assert "comentário" in (pg.wait_for_selector("#toast.on").inner_text())            # comentário obrigatório
    pg.fill("#invComentario", "Encaminhada ao compliance para verificar os repasses."); pg.click("#invSalvar")
    pg.wait_for_selector(".historico-inv li")
    assert "Não iniciada → Encaminhada" in pg.inner_text(".historico-inv")

    # Fase 5 — relatório completo: o formato preferido vem primeiro; cada botão baixa um arquivo
    pg.click("#nav button[data-page=relatorios]"); pg.wait_for_selector("#relExportar button")
    assert pg.get_attribute("#relExportar button >> nth=0", "data-formato") == "pdf"
    for formato, extensao in (("pdf", ".pdf"), ("xlsx", ".xlsx"), ("pptx", ".pptx"), ("csv", ".zip")):
        with pg.expect_download() as baixado:
            pg.click(f"#relExportar button[data-formato={formato}]")
        assert baixado.value.suggested_filename.endswith(extensao), baixado.value.suggested_filename
        assert os.path.getsize(baixado.value.path()) > 3000

    # Fase 5 — limites das regras de risco (administrador): vale na hora para o Painel de risco
    pg.on("dialog", lambda d: d.accept())
    pg.click("#nav button[data-page=config]"); pg.wait_for_selector("#cfgRisco input[data-param=fan_min_contas]")
    pg.fill("#cfgRisco input[data-param=fan_min_contas]", "40"); pg.click("#cfgRiscoSalvar")
    pg.wait_for_selector("#cfgRiscoErro:not([hidden])"); assert "de 2 a 30" in pg.inner_text("#cfgRiscoErro")
    pg.fill("#cfgRisco input[data-param=fan_min_contas]", "3"); pg.click("#cfgRiscoSalvar")
    pg.wait_for_selector("#cfgRisco tr.ajustado"); pg.wait_for_timeout(800)
    pg.click("#nav button[data-page=risco]"); pg.wait_for_selector("#riscoRegrasBody tr")
    assert "≥ 3 origens" in pg.inner_text("#riscoRegrasBody")
    pg.click("#nav button[data-page=config]"); pg.click("#cfgRiscoPadrao"); pg.wait_for_timeout(1200)
    assert pg.locator("#cfgRisco tr.ajustado").count() == 0

    # Fase 5 — preferências no cadastro: limiar, tema, texto, contraste e paleta do grafo voltam após recarregar
    pg.locator("#thrA").fill("20"); pg.locator("#thrA").dispatch_event("change"); pg.wait_for_timeout(300)
    pg.select_option("#cfgPreferencias select[data-pref=tema]", "escuro")
    pg.select_option("#cfgPreferencias select[data-pref=texto]", "grande")
    pg.select_option("#cfgPreferencias select[data-pref=grafo_paleta]", "daltonismo")
    pg.click("#cfgPreferencias [data-pref-bool=contraste]")
    assert pg.evaluate("document.documentElement.dataset.theme") == "dark"
    pg.wait_for_timeout(900)                                                          # salvamento agrupado (400 ms)
    pg.reload(); pg.wait_for_selector("#page-config.active #sobre dt")                # volta na mesma tela (#config)
    assert pg.input_value("#thrA") == "20"
    assert pg.evaluate("[document.documentElement.dataset.theme, document.documentElement.dataset.texto,"
                       " document.documentElement.hasAttribute('data-contraste')]") == ["dark", "grande", True]
    pg.click("#nav button[data-page=dashboard]"); pg.wait_for_selector("#dashKpis .val")
    assert int(pg.locator("#dashKpis .val").nth(2).inner_text()) > 12   # limiar 20 salvo → mais contas em análise
    pg.click("#nav button[data-page=rede]"); pg.wait_for_selector("#graph canvas")
    assert pg.input_value("#paleta") == "daltonismo"
    pg.click("#btnPrefs"); pg.wait_for_selector("#prefModal [data-pref-padrao]")
    pg.click("#prefModal [data-pref-padrao]"); pg.wait_for_timeout(600)
    assert pg.evaluate("document.documentElement.dataset.texto") == "normal" and not pg.evaluate(
        "document.documentElement.hasAttribute('data-contraste')")
    pg.click("[data-close=modal] >> nth=0")

    # Fase 6 — importação simples: arquivo com erro (linha apontada), arquivo bom, troca e volta à demonstração
    pasta = Path(tempfile.mkdtemp())
    pessoas = ["Ana", "Bruno", "Carla", "Davi", "Eva"]
    linhas = ["Pagador;Favorecido;Valor (R$);Data;Hora;Meio"] + [
        f"{pessoas[i % 5]};{pessoas[(i + 1 + i % 3) % 5]};{100 + i},50;{1 + i % 28:02d}/10/2026;10:{i % 60:02d};pix" for i in range(30)]
    (pasta / "ruim.csv").write_text("\n".join(linhas + ["Ana;Bruno;abc;05/10/2026;10:00;pix"]), encoding="utf-8")
    (pasta / "bom.csv").write_text("\n".join(linhas), encoding="utf-8")
    pg.click("#nav button[data-page=importacao]"); pg.wait_for_selector("#impBase dt")
    pg.set_input_files("#impArquivo", str(pasta / "ruim.csv")); pg.wait_for_selector("#impPrevia tr")
    assert "Linha 32" in pg.inner_text("#impResumo") and pg.is_disabled("#impEnviar")
    assert pg.input_value("#impMapa select[data-campo=conta_origem]") == "0"        # "Pagador" reconhecido
    pg.set_input_files("#impArquivo", str(pasta / "bom.csv")); pg.wait_for_selector(".imp-ok")
    pg.fill("#impNome", "Empresa de teste"); pg.check("#impAceite"); pg.fill("#impConfirmacao", "SUBSTITUIR")
    pg.click("#impEnviar"); pg.wait_for_function("document.getElementById('baseLabel').innerText.includes('Empresa de teste')")
    pg.wait_for_function("document.getElementById('impHistorico').innerText.includes('Em uso')")
    assert "5 contas" in pg.inner_text("#baseLabel"), pg.inner_text("#baseLabel")
    pg.click("#nav button[data-page=dashboard]"); pg.wait_for_timeout(600)
    assert pg.locator("#dashKpis .val").first.inner_text() == "30"
    pg.click("#nav button[data-page=historico]"); assert pg.locator("#cmpExemplo").is_hidden()   # exemplo só na demonstração
    pg.click("#nav button[data-page=importacao]"); pg.click("#impDemo"); pg.fill("#demoConfirmacao", "SUBSTITUIR")
    pg.click("#formDemo button[type=submit]"); esperar_modal_fechar(pg)
    pg.wait_for_function("!document.getElementById('baseLabel').innerText.includes('Empresa de teste')")
    pg.click("#nav button[data-page=dashboard]"); pg.wait_for_timeout(600)
    assert pg.locator("#dashKpis .val").first.inner_text() == "160"

    # "Minha senha": senha atual errada mostra o erro; a troca mantém esta sessão
    pg.click("#btnSenha"); pg.wait_for_selector("#formSenha")
    pg.fill("#msAtual", "Errada123"); pg.fill("#msNova", "Nova2026x"); pg.fill("#msConf", "Nova2026x")
    pg.click("#msSalvar"); pg.wait_for_selector("#msErro:not([hidden])")
    pg.fill("#msAtual", SENHA); pg.click("#msSalvar")
    esperar_modal_fechar(pg); pg.wait_for_timeout(300)
    assert "Senha alterada" in pg.inner_text("#toast")

    # navegação pelo endereço (#) e saída
    pg.goto(f"{BASE}/app#conta/C017"); pg.wait_for_selector("#page-conta.active #contaHist svg")
    assert "C017" in pg.inner_text("#contaDetalhe h2")
    pg.click("#btnSair"); pg.wait_for_url(f"{BASE}/login")
    navegador.close()

http.shutdown()
assert not erros, "\n".join(erros)
print("TESTES OK: navegador — página inicial, login (e-mail e CPF), 14 telas (módulos sob demanda), rede com Cytoscape "
      "(localizar, vizinhança, zoom, minimapa, cores, daltonismo, comunidade, animação de padrão), regras por modalidade, "
      "simulação recorrente, cenários, comparação lado a lado, matrizes, validação, simulador, "
      "calendário e filtros, painel de risco, ordenação, investigação, relatórios (PDF, Excel, Word, PowerPoint, CSV), "
      "limites das regras de risco, preferências salvas no cadastro (tema, texto, contraste, limiares, paleta), "
      "importação de base (erro por linha, troca e volta à demonstração), minha senha e navegação.")
