"""Testes da Fase 2: indícios de risco, recorte da análise e investigação.

Executar (na raiz do projeto): python -m testes.test_fase2
Usa CSV + SQLite temporários: nunca toca no banco do grupo.

1. Gabarito: as regras encontram os cenários planejados na aba "Leia-me" da planilha.
2. Cada regra em redes pequenas montadas à mão (dá para conferir no papel).
3. Recorte pela API: datas, dia específico, tipos, faixa de valor e erros.
4. Investigação: situação, comentário obrigatório, histórico, permissões e auditoria.
5. Desempenho com 300 transações (limite previsto para o upload da Fase 6).
"""
import os
import random
import tempfile
import time
from pathlib import Path

os.environ["NEXO_BANCO"] = "local"
for _chave in [k for k in os.environ if k.startswith(("DB_", "SMTP_", "APP_URL", "GOOGLE_"))]:
    del os.environ[_chave]

from banco import conexao as db  # noqa: E402

db.SQLITE = Path(tempfile.mkdtemp()) / "fase2.db"

from app import auth, casos, servidor  # noqa: E402
from banco import migracoes, repositorio  # noqa: E402
from nucleo import analise, risco  # noqa: E402

H = {"X-Requested-With": "NEXO"}

# ------------------------------------------------------------------ 1. gabarito da planilha
contas, transacoes = repositorio.carregar_dados()
r = analise.calcular(contas, transacoes)
R = r["risco"]
achou = {regra["id"]: set(regra["contas"]) for regra in R["regras"]}
por = {c["id"]: c for c in r["contas"]}

assert analise.VERSAO_MOTOR == "2.0"
assert "C001" in achou["fan_in"]                                         # Comunidade 1: fan-in
assert {"C006", "C031"} <= achou["fan_out"]                              # Comunidades 2 e 7: fan-out
assert {"C011", "C012", "C013", "C014", "C015"} <= achou["cadeia"]       # Comunidade 3: cadeia
assert {"C016", "C017", "C018", "C019"} <= achou["ciclo"]                # Comunidade 4: ciclo
assert {"C026", "C027", "C028", "C029", "C030"} <= achou["ciclo"]        # Comunidade 6: ciclo maior
assert ["C016", "C017", "C018", "C019", "C016"] in [i["contas"] for i in R["contas"]["C019"]["indicios"]
                                                    if i["regra"] == "ciclo"] or \
       any(set(c) == {"C016", "C017", "C018", "C019"} for c in R["circuitos"])
assert any(set(c) == {"C026", "C027", "C028", "C029", "C030"} for c in R["circuitos"])
assert "C021" in achou["intermediacao"]                                  # Comunidade 5: hub
# contas-ponte: C035 → C036 fica interna porque o Louvain põe C036 na comunidade de C035
assert {"C005", "C010", "C015", "C017", "C025", "C030"} <= achou["ponte"]
assert por["C035"]["com"] == por["C036"]["com"]
assert achou["volume"] == {"C025"}                                       # C025: o maior fluxo da base
assert not any(R["contas"][c]["indicios"] for c in ("C038", "C039", "C040"))   # baixa conectividade
assert R["contas"]["C040"]["nivel"] == "Sem indícios"
# toda conta com indício traz a evidência em texto e os pontos batem com os pesos
for cid, info in R["contas"].items():
    assert info["pontos"] == min(100, sum(risco.REGRA[i["regra"]]["peso"] for i in info["indicios"]))
    assert info["nivel"] == risco.nivel(info["pontos"])
    assert all(i["evidencia"] and "fraude" not in i["evidencia"].lower() for i in info["indicios"])
    assert por[cid]["risco"] == info["pontos"] and por[cid]["indicios"] == [i["regra"] for i in info["indicios"]]
assert sum(R["resumo"]["por_nivel"].values()) == 40
assert {c["comunidade"] for c in R["comunidades"] if c["destaque"]} >= {3, 4}
assert all(t["atipica"] == (t["id"] in R["transacoes_atipicas"]) for t in r["transacoes"])
assert analise.calcular(contas, transacoes)["risco"] == R                # determinístico
print("ok — gabarito: fan-in C001, fan-out C006/C031, cadeia C011–C015, circuitos C016–C019 e C026–C030, "
      "hub C021, pontes, volume de C025 e cluster isolado sem indícios")


# ------------------------------------------------------------------ 2. regras em redes montadas à mão
def tx(i, de, para, valor, data="2026-08-01", hora="10:00", tipo="PIX"):
    return {"id": f"T{i:04d}", "de": de, "para": para, "valor": valor, "data": data, "hora": hora, "tipo": tipo}


def contas_fake(ids, **extra):
    return [{"id": c, "flow": extra.get("flow", {}).get(c, 1000), "betw": extra.get("betw", {}).get(c, 0.0),
             "com": extra.get("com", {}).get(c, 1)} for c in ids]


# percentil pelo posto mais próximo: 1..10 → p90 = 9, p95 = 10
assert risco._percentil(list(range(1, 11)), 90) == 9 and risco._percentil(list(range(1, 11)), 95) == 10
assert [risco.nivel(p) for p in (0, 1, 29, 30, 59, 60, 100)] == \
       ["Sem indícios", "Baixa", "Baixa", "Moderada", "Moderada", "Alta", "Alta"]

# repasse: recebe 1.000 e reenvia 850 em 3 h (85%) → sim; 500 em 3 h (50%) → não
t = [tx(1, "A", "B", 1000, hora="08:00"), tx(2, "B", "C", 850, hora="11:00"),
     tx(3, "D", "E", 1000, hora="08:00"), tx(4, "E", "F", 500, hora="11:00")]
achados = risco._repasse(t, risco.PARAMETROS)
assert set(achados) == {"B"} and achados["B"]["transacoes"] == ["T0001", "T0002"]
# fora da janela de 24 h → não
t2 = [tx(1, "A", "B", 1000, data="2026-08-01"), tx(2, "B", "C", 900, data="2026-08-03")]
assert risco._repasse(t2, risco.PARAMETROS) == {}

# cadeia cronológica: A→B→C→D→E em dias seguidos (4 transferências) → as 5 contas
t = [tx(i, a, b, 100, data=f"2026-08-0{i}") for i, (a, b) in enumerate(zip("ABCD", "BCDE"), start=1)]
assert set(risco._cadeias(t, risco.PARAMETROS)) == set("ABCDE")
# fora de ordem (a segunda acontece antes da primeira) → não é cadeia
t_desordem = [tx(1, "A", "B", 100, data="2026-08-05"), *t[1:]]
assert "A" not in risco._cadeias(t_desordem, risco.PARAMETROS)

# circuito recorrente: A→B→C→A em duas datas → circuito; uma data só → não
um = [tx(i, a, b, 100, data="2026-08-01") for i, (a, b) in enumerate([("A", "B"), ("B", "C"), ("C", "A")])]
dois = um + [tx(10 + i, a, b, 100, data="2026-08-20") for i, (a, b) in enumerate([("A", "B"), ("B", "C"), ("C", "A")])]
assert risco._circuitos(um, risco.PARAMETROS)[0] == {}
assert set(risco._circuitos(dois, risco.PARAMETROS)[0]) == {"A", "B", "C"}

# fan-in: X recebe de 4 e envia para 1 → sim (4 ≥ 2 × 1); Y recebe de 4 e envia para 3 → não
t = [tx(i, o, "X", 100) for i, o in enumerate("PQRS")] + [tx(9, "X", "Z", 100)]
t += [tx(20 + i, o, "Y", 100) for i, o in enumerate("PQRS")] + [tx(30 + i, "Y", d, 100) for i, d in enumerate("KLM")]
fan_in, fan_out = risco._fans(t, risco.PARAMETROS)
assert "X" in fan_in and "Y" not in fan_in and fan_in["X"]["valores"] == {"origens": 4, "destinos": 1}

# concentração: 3 transações em 2 h → sim; 2 → não
t = [tx(1, "A", "B", 10, hora="09:00"), tx(2, "A", "C", 10, hora="10:00"), tx(3, "D", "A", 10, hora="11:00")]
assert set(risco._concentracao(t, risco.PARAMETROS)) == {"A"}

# ponte: transação entre comunidades marca as duas pontas
assert set(risco._pontes([tx(1, "A", "B", 10)], {"A": 1, "B": 2})) == {"A", "B"}
assert risco._pontes([tx(1, "A", "B", 10)], {"A": 1, "B": 1}) == {}

# volume robusto: 9 contas com fluxo 1.000 ± pouco e uma com 5.000 → só ela
fluxos = {f"C{i}": 1000 + i * 10 for i in range(9)} | {"G": 5000}
assert set(risco._volume(contas_fake(fluxos, flow=fluxos), risco.PARAMETROS)) == {"G"}
print("ok — regras em redes pequenas: repasse, cadeia, circuito, fan-in, concentração, ponte, volume, percentil e níveis")

# ------------------------------------------------------------------ 3. recorte pela API
auth.iniciar_banco()
assert migracoes.VERSAO_ATUAL >= 5 and 5 in migracoes.versoes_aplicadas()
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


def total(c, consulta=""):
    resposta = c.get("/api/resultados" + consulta)
    return resposta.status_code, resposta.get_json()


st, base = total(ana)
assert st == 200 and len(base["transacoes"]) == 160 and base["risco"]["resumo"]["por_nivel"]["Alta"] >= 1
assert base["simulacao"]["datas_base"] == {"primeira": "2026-08-01", "ultima": "2026-09-15"}
st, agosto = total(ana, "?inicio=2026-08-01&fim=2026-08-31")
assert st == 200 and len(agosto["transacoes"]) == 80 and all(t["data"] < "2026-09" for t in agosto["transacoes"])
assert agosto["simulacao"]["recorte"]["inicio_efetivo"] == "2026-08-01"
st, dia = total(ana, "?inicio=2026-09-15&fim=2026-09-15")
assert st == 200 and {t["data"] for t in dia["transacoes"]} == {"2026-09-15"}
st, pix = total(ana, "?tipos=PIX")
assert st == 200 and {t["tipo"] for t in pix["transacoes"]} == {"PIX"} and len(pix["transacoes"]) == 87
st, faixa = total(ana, "?valor_min=5000&valor_max=8000")
assert st == 200 and all(5000 <= t["valor"] <= 8000 for t in faixa["transacoes"])
st, combinado = total(ana, "?inicio=2026-09-01&fim=2026-09-15&tipos=PIX,TED&valor_min=1000")
assert st == 200 and all(t["data"] >= "2026-09-01" and t["tipo"] in ("PIX", "TED") and t["valor"] >= 1000
                         for t in combinado["transacoes"])
st, sete = total(ana, "?dias=7")
assert st == 200 and min(t["data"] for t in sete["transacoes"]) >= "2026-09-09"
# o resultado muda com o recorte (a rede é recalculada, não só filtrada)
assert agosto["risco"]["resumo"] != base["risco"]["resumo"] or agosto["dashboard"] != base["dashboard"]
for ruim, trecho in (("?inicio=2026-09-10&fim=2026-09-01", "depois"), ("?inicio=xx", "Data inválida"),
                     ("?inicio=2027-01-01", "Nenhuma transação"), ("?valor_min=-5", "negativos"),
                     ("?valor_min=9000&valor_max=10", "maior")):
    st, corpo = total(ana, ruim)
    assert st == 400 and trecho in corpo["erro"], (ruim, corpo)
assert ana.get("/api/matrizes?inicio=2026-08-01&fim=2026-08-15").status_code == 200
assert ana.get("/api/exportar?tipos=TED").status_code == 200
print("ok — recorte: datas, dia específico, últimos N dias, tipos, faixa de valor, combinado e erros (400)")

# ------------------------------------------------------------------ 4. investigação
assert ana.get("/api/casos").get_json()["casos"] == {}
assert caio.get("/api/casos/C016").get_json()["situacao"] == "nao_iniciada"
r = caio.post("/api/casos/C016", headers=H, json={"situacao": "em_analise", "comentario": "Visualizador tentando."})
assert r.status_code == 403                                               # visualizador só consulta
assert beto.post("/api/casos/C016", headers=H, json={"situacao": "em_analise", "comentario": "ok"}).status_code == 400
assert beto.post("/api/casos/C999", headers=H, json={"situacao": "em_analise", "comentario": "Conta que não existe"}).status_code == 400
assert beto.post("/api/casos/C016", headers=H, json={"situacao": "aprovada", "comentario": "Situação inválida"}).status_code == 400
assert beto.post("/api/casos/C016", headers=H, json={"situacao": "nao_iniciada", "comentario": "Voltar ao início"}).status_code == 400
r = beto.post("/api/casos/c016", headers=H, json={"situacao": "em_analise", "comentario": "  Verificar   repasses de setembro.  "})
assert r.status_code == 200 and r.get_json()["situacao_nome"] == "Em análise"
r = ana.post("/api/casos/C016", headers=H, json={"situacao": "encaminhada", "comentario": "Encaminhada ao compliance."})
caso = r.get_json()
assert caso["situacao"] == "encaminhada" and caso["responsavel"] == "Ana Admin"
assert [(h["de_nome"], h["para_nome"], h["usuario"]) for h in caso["historico"]] == [
    ("Em análise", "Encaminhada", "Ana Admin"), ("Não iniciada", "Em análise", "Beto Analista")]
assert caso["historico"][1]["comentario"] == "Verificar repasses de setembro."   # espaços normalizados
assert caio.get("/api/casos").get_json()["casos"]["C016"]["situacao"] == "encaminhada"  # todos consultam
assert set(caio.get("/api/casos").get_json()["situacoes"]) == set(casos.SITUACOES)
eventos = [l for l in auth.listar_auditoria() if l["evento"] == "caso_atualizado"]
assert len(eventos) == 2 and "Em análise → Encaminhada" in eventos[0]["detalhe"]
assert "investigar" in auth.publico(auth.buscar_por_documento("11144477735"))["permissoes"]
assert "investigar" not in auth.publico(auth.buscar_por_documento("39053344705"))["permissoes"]
print("ok — investigação: situações, comentário obrigatório, histórico, responsável, permissões e auditoria")

# ------------------------------------------------------------------ 5. desempenho com 300 transações
random.seed(7)
ids = [f"K{i:03d}" for i in range(120)]
grandes = [{"id_conta": c, "tipo_titular": "Pessoa Física", "data_abertura": "2020-01-01"} for c in ids]
linhas = []
for i in range(300):
    a, b = random.sample(ids[:60] if i % 3 else ids, 2)
    linhas.append({"id_transacao": f"X{i:04d}", "conta_origem": a, "conta_destino": b,
                   "valor": f"{random.uniform(100, 20000):.2f}", "data": f"2026-08-{random.randint(1, 30):02d}",
                   "hora": f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}",
                   "tipo_transacao": random.choice(["PIX", "TED", "Transferência"])})
grandes, validadas = analise.validar_dados(grandes, linhas)
inicio = time.perf_counter()
resultado = analise.calcular(grandes, validadas)
ms = (time.perf_counter() - inicio) * 1000
assert ms < 2000, f"{ms:.0f} ms"
assert sum(resultado["risco"]["resumo"]["por_nivel"].values()) == 120
print(f"ok — desempenho: 300 transações / 120 contas, análise completa com as regras em {ms:.0f} ms")
print("TESTES OK: Fase 2 — gabarito da planilha, regras explicáveis, recorte, investigação e desempenho.")
