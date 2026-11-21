"""Testes da Fase 5: limites das regras de risco editáveis, preferências do usuário no banco e
relatórios/exportações (PDF, Excel, CSV, Word e PowerPoint) com gráficos nativos.

Executar (na raiz do projeto): python -m testes.test_fase5
Usa CSV + SQLite temporários: nunca toca no banco do grupo.
"""
import os
import tempfile
from pathlib import Path

os.environ["NEXO_BANCO"] = "local"
for _chave in [k for k in os.environ if k.startswith(("DB_", "SMTP_", "APP_URL", "GOOGLE_"))]:
    del os.environ[_chave]

from banco import conexao as db  # noqa: E402

db.SQLITE = Path(tempfile.mkdtemp()) / "fase5.db"

from app import analises, auth, preferencias, servidor  # noqa: E402
from banco import migracoes, repositorio  # noqa: E402
from nucleo import risco  # noqa: E402

H = {"X-Requested-With": "NEXO"}

auth.iniciar_banco()
assert migracoes.VERSAO_ATUAL >= 7 and 7 in migracoes.versoes_aplicadas()
auth.cadastrar("52998224725", "Ana Admin", "ana@nexo.test", "11912345678", "Senha123", "Senha123",
               cargo="administrador", email_confirmado=True)
auth.cadastrar("11144477735", "Beto Analista", "beto@nexo.test", "11912345679", "Senha123", "Senha123",
               cargo="analista", email_confirmado=True)
auth.cadastrar("39053344705", "Caio Visualizador", "caio@nexo.test", "11912345670", "Senha123", "Senha123",
               email_confirmado=True)


def cliente(login):
    servidor._tentativas_ip.clear()
    c = servidor.app.test_client()
    assert c.post("/auth/entrar", headers=H, json={"login": login, "senha": "Senha123"}).status_code == 200
    return c


ana, beto, caio = cliente("ana@nexo.test"), cliente("beto@nexo.test"), cliente("caio@nexo.test")
analises.RECARGA_SEGUNDOS = 3600   # os limites só mudam pelo esquecer_parametros() da rota

# ------------------------------------------------------------------ 1. limites das regras de risco
assert risco.parametros_efetivos() == risco.PARAMETROS
assert set(risco.PARAMETROS_INFO) == set(risco.PARAMETROS)                       # todo parâmetro tem faixa e nome
for chave, info in risco.PARAMETROS_INFO.items():
    assert info["min"] <= risco.PARAMETROS[chave] <= info["max"], chave           # o padrão está dentro da faixa
    assert all(r in risco.REGRA for r in info["regras"]), chave
assert risco.validar_parametro("fan_min_contas", "3") == 3
assert risco.validar_parametro("volume_z", "2,75") == 2.75                        # vírgula decimal
for chave, valor, trecho in (("fan_min_contas", "3,5", "inteiro"), ("fan_min_contas", 1, "de 2 a 30"),
                             ("repasse_fracao", "1,2", "de 0,1 a 1"), ("xyz", 1, "desconhecido"),
                             ("volume_z", "abc", "número")):
    try:
        risco.validar_parametro(chave, valor)
        raise AssertionError(f"{chave}={valor} deveria ser recusado")
    except ValueError as erro:
        assert trecho in str(erro), (chave, erro)
assert risco.parametros_efetivos({"fan_min_contas": "99", "volume_z": "3"})["fan_min_contas"] == 4   # inválido é ignorado

antes = beto.get("/api/resultados").get_json()
fan_in_antes = set(next(r for r in antes["risco"]["regras"] if r["id"] == "fan_in")["contas"])
assert "C001" in fan_in_antes                                                     # gabarito da Fase 2

lista = caio.get("/api/parametros-risco").get_json()["parametros"]                # todos consultam
assert len(lista) == len(risco.PARAMETROS) and all(p["valor"] == p["padrao"] for p in lista)
assert caio.post("/api/parametros-risco", headers=H, json={"valores": {"fan_min_contas": 3}}).status_code == 403
assert beto.post("/api/parametros-risco", headers=H, json={"valores": {"fan_min_contas": 3}}).status_code == 403
r = ana.post("/api/parametros-risco", headers=H, json={"valores": {"fan_min_contas": "40"}})
assert r.status_code == 400 and "de 2 a 30" in r.get_json()["erro"]
r = ana.post("/api/parametros-risco", headers=H, json={"valores": {"fan_min_contas": "3", "volume_z": "2,5"}})
assert r.status_code == 200
p = {x["chave"]: x for x in r.get_json()["parametros"]}
assert p["fan_min_contas"]["valor"] == 3 and p["fan_min_contas"]["ajustado_por"] == "Ana Admin"
assert p["volume_z"]["ajustado_por"] is None                                      # igual ao padrão: não fica gravado
assert set(repositorio.ler_parametros_risco()) == {"fan_min_contas"}

depois = beto.get("/api/resultados").get_json()                                   # vale na hora, para todos
assert depois["risco"]["parametros"]["fan_min_contas"] == 3
assert depois["analise"]["assinatura"] != antes["analise"]["assinatura"]          # outro limite, outra análise
fan_in_depois = set(next(r for r in depois["risco"]["regras"] if r["id"] == "fan_in")["contas"])
assert fan_in_antes < fan_in_depois, (fan_in_antes, fan_in_depois)                 # limite menor: mais contas
regra = next(r for r in depois["risco"]["regras"] if r["id"] == "fan_in")
assert "≥ 3 origens" in regra["limite"]                                           # o texto da regra acompanha

eventos = [e for e in auth.listar_auditoria() if e["evento"] == "parametros_risco"]
assert eventos and "fan_min_contas: 4 → 3" in eventos[0]["detalhe"], eventos[:1]

assert ana.post("/api/parametros-risco", headers=H, json={"padrao": True}).status_code == 200
assert repositorio.ler_parametros_risco() == {}
volta = beto.get("/api/resultados").get_json()
assert volta["analise"]["assinatura"] == antes["analise"]["assinatura"]          # padrão: mesma análise de antes
print("ok — limites das regras de risco: faixas seguras, só o administrador altera, vale na hora, auditoria e padrão")

# ------------------------------------------------------------------ 2. preferências do usuário
r = caio.get("/api/preferencias").get_json()                                      # todo cargo tem preferências
assert r["preferencias"] == preferencias.PADRAO == r["padrao"]
r = caio.put("/api/preferencias", headers=H, json={"preferencias": {"tema": "escuro", "texto": "grande",
                                                                     "contraste": True, "grafo_paleta": "daltonismo"}})
assert r.status_code == 200 and r.get_json()["preferencias"]["tema"] == "escuro"
outro_pc = cliente("caio@nexo.test")                                               # outro computador, mesmo usuário
p = outro_pc.get("/api/preferencias").get_json()["preferencias"]
assert p["tema"] == "escuro" and p["texto"] == "grande" and p["contraste"] is True and p["grafo_paleta"] == "daltonismo"
assert beto.get("/api/preferencias").get_json()["preferencias"]["tema"] == "sistema"   # cada usuário tem as suas
assert repositorio.ler_preferencias(3) == {"tema": "escuro", "texto": "grande", "contraste": True,
                                           "grafo_paleta": "daltonismo"}            # só o que difere do padrão
for corpo, trecho in (({"tema": "roxo"}, "Tema"), ({"contraste": "sim"}, "verdadeiro ou falso"),
                      ({"limiar_analise": 90}, "de 20 a 80"), ({"limiar_analise": 1.5}, "inteiro"),
                      ({"inexistente": 1}, "desconhecida"), ({"limiar_analise": 60, "limiar_alta": 62}, "5 pontos")):
    r = caio.put("/api/preferencias", headers=H, json={"preferencias": corpo})
    assert r.status_code == 400 and trecho in r.get_json()["erro"], (corpo, r.get_json())
assert caio.get("/api/preferencias").get_json()["preferencias"]["limiar_analise"] == 45   # nada foi gravado
assert caio.put("/api/preferencias", json={"preferencias": {"tema": "claro"}}).status_code == 400   # sem o cabeçalho
assert caio.put("/api/preferencias", headers=H, json={"padrao": True}).get_json()["preferencias"] == preferencias.PADRAO
assert repositorio.ler_preferencias(3) == {}
with db.conectar() as c:                                                         # valor antigo que deixou de valer
    c.execute("UPDATE preferencias_usuario SET dados = ? WHERE usuario_id = 3", ('{"tema": "neon", "texto": "maior"}',))
p = caio.get("/api/preferencias").get_json()["preferencias"]
assert p["tema"] == "sistema" and p["texto"] == "maior"
print("ok — preferências: no banco, por usuário, em qualquer computador, validadas e com volta ao padrão")

# ------------------------------------------------------------------ 3. relatórios em todos os formatos
import csv  # noqa: E402
import io  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
import zipfile  # noqa: E402

import openpyxl  # noqa: E402
from docx import Document  # noqa: E402
from pptx import Presentation  # noqa: E402

from nucleo import relatorio  # noqa: E402

beto.post("/api/simulacao/restaurar", headers=H)
base = beto.get("/api/resultados").get_json()
top10 = [c["id"] for c in sorted(base["contas"], key=lambda c: -c["score"])[:10]]
c025 = next(c for c in base["contas"] if c["id"] == "C025")
priorizadas = [c for c in base["contas"] if c["nivel_risco"] in ("Alta", "Moderada")]

# o documento (mesmo para todos os formatos)
doc = relatorio.relatorio_analise(base, {"nome": "Beto", "cargo_nome": "Analista"}, __import__("datetime").datetime(2026, 11, 21, 10, 0))
graficos = [b for s in doc["secoes"] for b in s["blocos"] if b["tipo"] == "grafico"]
assert len(graficos) == 6
pizza = next(g for g in graficos if g["forma"] == "pizza")
assert sum(pizza["series"][0]["valores"]) == 40                                 # todas as contas, uma vez
assert dict(zip(pizza["categorias"], pizza["series"][0]["valores"])) == {k: base["risco"]["resumo"]["por_nivel"][k] for k in relatorio.NIVEIS}
assert next(g for g in graficos if g["titulo"].startswith("10 contas"))["categorias"] == top10
ident = dict(doc["identificacao"])
assert ident["Assinatura"] == base["analise"]["assinatura"] and ident["Versão do motor"] == base["analise"]["versao_motor"]
conclusoes = next(b for s in doc["secoes"] for b in s["blocos"] if b["tipo"] == "lista")["itens"]
assert any("não constituem prova" in f for f in conclusoes)
assert not any(re.search(r"\bfraude\b", f, re.I) for f in conclusoes)          # nunca afirma fraude
assert relatorio.formatar(1234.5, "brl") == "R$ 1.234,50" and relatorio.formatar(0.55, "pct") == "55,0%"
assert relatorio.formatar((3, "int"), "txt") == "3"                              # célula com formato próprio


def baixar(cliente, **params):
    inicio = time.perf_counter()
    r = cliente.get("/api/relatorio?" + "&".join(f"{k}={v}" for k, v in params.items()))
    return r, time.perf_counter() - inicio


arquivos, tempos = {}, {}
for formato in ("pdf", "xlsx", "csv", "docx", "pptx"):
    r, tempos[formato] = baixar(beto, tipo="analise", formato=formato)
    assert r.status_code == 200, (formato, r.get_data()[:300])
    assert "attachment" in r.headers["Content-Disposition"] and r.headers["Content-Disposition"].endswith(
        {"csv": ".zip"}.get(formato, f".{formato}") + '"')
    arquivos[formato] = r.data

# PDF: válido, com várias páginas e fonte embutida (acentos e símbolos)
pdf = arquivos["pdf"]
assert pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF")
assert len(re.findall(rb"/Type\s*/Page\b", pdf)) >= 8
assert b"FontFile2" in pdf

# Excel: números de verdade, uma aba por tabela e 6 gráficos nativos
wb = openpyxl.load_workbook(io.BytesIO(arquivos["xlsx"]))
assert {"Resumo", "Gráficos", "Priorizadas", "Evidencias", "Contas", "Transacoes", "Regras"} <= set(wb.sheetnames)
contas_xlsx = {l[0]: l for l in wb["Contas"].iter_rows(min_row=4, values_only=True)}
assert len(contas_xlsx) == 40 and contas_xlsx["C025"][3] == c025["score"] and isinstance(contas_xlsx["C025"][9], float)
assert sum(1 for _ in wb["Transacoes"].iter_rows(min_row=4)) == 160
with zipfile.ZipFile(io.BytesIO(arquivos["xlsx"])) as z:
    assert len([n for n in z.namelist() if n.startswith("xl/charts/chart")]) == 6

# CSV (zip): um arquivo por tabela/gráfico, ";" e vírgula decimal
with zipfile.ZipFile(io.BytesIO(arquivos["csv"])) as z:
    nomes = z.namelist()
    assert "LEIA-ME.txt" in nomes and len([n for n in nomes if "grafico" in n]) == 6
    texto = z.read(next(n for n in nomes if n.endswith("_contas.csv"))).decode("utf-8-sig")
linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))
assert len(linhas) == 41 and linhas[0][0] == "Conta"
assert float(next(l for l in linhas if l[0] == "C025")[3].replace(",", ".")) == c025["score"]

# Word: títulos, tabela de priorizadas e 6 gráficos nativos com a planilha de dados embutida
docx = Document(io.BytesIO(arquivos["docx"]))
titulos = [p.text for p in docx.paragraphs if p.style.name.startswith("Heading")]
assert "3. Contas priorizadas" in titulos and "7. Conclusões" in titulos and not any("Anexo" in t for t in titulos)
tabela = next(t for t in docx.tables if t.rows[0].cells[0].text == "Conta" and t.rows[0].cells[1].text == "Prioridade")
assert len(tabela.rows) == len(priorizadas) + 1
with zipfile.ZipFile(io.BytesIO(arquivos["docx"])) as z:
    assert len([n for n in z.namelist() if re.match(r"word/charts/chart\d+\.xml$", n)]) == 6
    assert len([n for n in z.namelist() if n.startswith("word/embeddings/")]) == 6
    assert b"<c:externalData" in z.read("word/charts/chart1.xml")

# PowerPoint: 16:9, 6 gráficos nativos com os mesmos dados, tabelas limitadas por slide
pptx = Presentation(io.BytesIO(arquivos["pptx"]))
assert round(pptx.slide_width / pptx.slide_height, 2) == 1.78
graficos_ppt = [sh.chart for s in pptx.slides for sh in s.shapes if sh.has_chart]
assert len(graficos_ppt) == 6
barras = next(g for g in graficos_ppt if list(g.plots[0].categories) == list(reversed(top10)))   # top 10, de cima para baixo
assert list(barras.plots[0].series[0].values)[-1] == c025["score"]
assert all(len(sh.table.rows) <= 11 for s in pptx.slides for sh in s.shapes if sh.has_table)
assert len(pptx.slides) <= 25
print("ok — relatório da análise: PDF, Excel, CSV, Word e PowerPoint com os mesmos números e gráficos nativos "
      f"({', '.join(f'{k} {v:.2f}s' for k, v in tempos.items())})")

# comparação: gabarito da planilha (C025: 8º → 1º e 1 → 3 comunidades vizinhas)
r, _ = baixar(beto, tipo="comparacao", formato="xlsx", a="recorte:2026-08-01:2026-08-15", b="recorte:2026-09-01:2026-09-15")
assert r.status_code == 200
wb = openpyxl.load_workbook(io.BytesIO(r.data))
linha = next(l for l in wb["Contas"].iter_rows(min_row=4, values_only=True) if l[0] == "C025")
assert (linha[4], linha[5], linha[9], linha[10]) == (8, 1, 1, 3), linha
for formato in ("pdf", "docx", "pptx", "csv"):
    r, _ = baixar(beto, tipo="comparacao", formato=formato, a="recorte:2026-08-01:2026-08-15", b="recorte:2026-09-01:2026-09-15")
    assert r.status_code == 200 and len(r.data) > 2000, formato

# permissões, erros e auditoria
assert baixar(caio, tipo="analise", formato="pdf")[0].status_code == 403         # visualizador não exporta
assert baixar(beto, tipo="analise", formato="odt")[0].status_code == 400
assert baixar(beto, tipo="xyz", formato="pdf")[0].status_code == 400
r, _ = baixar(beto, tipo="analise", formato="pdf", inicio="2030-01-01")
assert r.status_code == 400 and "Nenhuma transação" in r.get_json()["erro"]
assert baixar(beto, tipo="comparacao", formato="pdf", a="cenario:999", b="base")[0].status_code == 400
eventos = [e for e in auth.listar_auditoria() if e["evento"] == "relatorio"]
assert eventos and "Beto Analista: comparação" in eventos[0]["detalhe"] and "em CSV" in eventos[0]["detalhe"]

# com simulação: o relatório avisa e marca as transações simuladas
beto.post("/api/transacoes", headers=H, json={"de": "C001", "para": "C030", "valor": "4500000", "data": "2026-09-14",
                                              "hora": "12:00", "tipo": "PIX"})
r, _ = baixar(beto, tipo="analise", formato="xlsx")
wb = openpyxl.load_workbook(io.BytesIO(r.data))
assert [l for l in wb["Transacoes"].iter_rows(min_row=4, values_only=True) if l[8] == "Sim"]
assert any("SIMULADA" in str(c.value or "") for l in wb["Resumo"].iter_rows() for c in l)
beto.post("/api/simulacao/restaurar", headers=H)
print("ok — relatório da comparação (gabarito C025), permissões, erros, auditoria e simulação marcada")

print("TESTES OK: Fase 5 — limites das regras de risco, preferências do usuário e relatórios.")
