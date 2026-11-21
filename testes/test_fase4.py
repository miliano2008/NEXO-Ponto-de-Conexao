"""Testes da Fase 4: dados bancários, regras por modalidade, simulação recorrente,
histórico de cenários e comparação lado a lado.

Executar (na raiz do projeto): python -m testes.test_fase4
Usa CSV + SQLite temporários: nunca toca no banco do grupo.
"""
import os
import tempfile
from pathlib import Path

os.environ["NEXO_BANCO"] = "local"
for _chave in [k for k in os.environ if k.startswith(("DB_", "SMTP_", "APP_URL", "GOOGLE_"))]:
    del os.environ[_chave]

from banco import conexao as db  # noqa: E402

db.SQLITE = Path(tempfile.mkdtemp()) / "fase4.db"

from app import auth, servidor  # noqa: E402
from banco import migracoes, repositorio  # noqa: E402
from nucleo import bancario, comparacao  # noqa: E402

H = {"X-Requested-With": "NEXO"}
contas, transacoes = repositorio.carregar_dados()
titulares = {c["id_conta"]: c["tipo_titular"] for c in contas}

# ------------------------------------------------------------------ 1. dados bancários fictícios
bancos = bancario.dados_bancarios(contas, transacoes)
assert bancario.dados_bancarios(contas, transacoes) == bancos                    # sempre os mesmos
assert set(bancos) == {c["id_conta"] for c in contas}
assert {b["instituicao"] for b in bancos.values()} <= set(bancario.INSTITUICOES)
assert all("Fictício" in i for i in bancario.INSTITUICOES)                       # nenhum banco real
assert all(bancos[t["de"]]["instituicao"] == bancos[t["para"]]["instituicao"]     # base coerente com a regra
           for t in transacoes if t["tipo"] == "Transferência")
for c in contas:
    b = bancos[c["id_conta"]]
    assert b["tipo_conta"] == bancario.TIPO_CONTA[c["tipo_titular"]]
    assert b["chave_pix"] in bancario.CHAVES_PIX[c["tipo_titular"]]
    assert not any(ch.isdigit() for ch in b["chave_pix"])                          # tipo da chave, nunca o número
print("ok — dados bancários: determinísticos, só instituições fictícias, coerentes com as transferências da base")

# ------------------------------------------------------------------ 2. regras por modalidade
R = bancario.regras_com_ajustes()
assert {r["origem"] for r in R.values()} == set(bancario.ORIGENS)


def avaliar(**t):
    base = {"de": "C001", "para": "C030", "valor": 100.0, "data": "2026-09-14", "hora": "12:00", "tipo": "PIX"}
    base.update(t)
    return {v["regra"]: v["resultado"] for v in bancario.avaliar_transacao(base, titulares[base["de"]], bancos, R)}


pf = next(c["id_conta"] for c in contas if c["tipo_titular"] == "Pessoa Física")
pj = next(c["id_conta"] for c in contas if c["tipo_titular"] == "Pessoa Jurídica")
assert avaliar(de=pf, valor=1500, hora="22:00")["pix_noturno_pf"] == "alerta"          # PF, noite, > R$ 1.000
assert avaliar(de=pf, valor=900, hora="22:00")["pix_noturno_pf"] == "ok"
assert avaliar(de=pf, valor=1500, hora="05:59")["pix_noturno_pf"] == "alerta"          # atravessa a meia-noite
assert avaliar(de=pf, valor=1500, hora="06:00")["pix_noturno_pf"] == "ok"
assert avaliar(de=pj, valor=50000, hora="23:00")["pix_noturno_pf"] == "ok"             # pessoa jurídica: não se aplica
assert avaliar(tipo="TED", data="2026-09-12")["ted_dia_util"] == "bloqueio"           # sábado
assert avaliar(tipo="TED", data="2026-09-13")["ted_dia_util"] == "bloqueio"           # domingo
assert avaliar(tipo="TED", data="2026-09-14", hora="17:00") == {"ted_dia_util": "ok", "ted_horario": "ok"}
assert avaliar(tipo="TED", hora="17:01")["ted_horario"] == "bloqueio"
assert avaliar(tipo="TED", hora="06:29")["ted_horario"] == "bloqueio"
mesma = [(a, b) for a in bancos for b in bancos if a != b and bancos[a]["instituicao"] == bancos[b]["instituicao"]][0]
outra = [(a, b) for a in bancos for b in bancos if bancos[a]["instituicao"] != bancos[b]["instituicao"]][0]
assert avaliar(tipo="Transferência", de=mesma[0], para=mesma[1])["transferencia_mesma_instituicao"] == "ok"
assert avaliar(tipo="Transferência", de=outra[0], para=outra[1])["transferencia_mesma_instituicao"] == "bloqueio"
assert "ted_dia_util" not in avaliar(tipo="PIX", data="2026-09-12")                    # PIX não tem a regra da TED
# ajustes do administrador: ação e limites
R2 = bancario.regras_com_ajustes({"ted_horario": {"acao": "alertar", "parametros": {"fim": "18:30"}},
                                  "ted_dia_util": {"acao": "desligada"}})
v = {x["regra"]: x["resultado"] for x in bancario.avaliar_transacao(
    {"de": "C001", "para": "C030", "valor": 1, "data": "2026-09-12", "hora": "18:00", "tipo": "TED"}, "Pessoa Jurídica", bancos, R2)}
assert v == {"ted_horario": "ok"}
assert bancario.REGRAS_PADRAO["ted_horario"]["parametros"]["fim"] == "17:00"           # o padrão não muda
for ruim in ({"limite": "abc"}, {"limite": -1}):
    try:
        bancario.validar_parametros("pix_noturno_pf", ruim)
        raise AssertionError(ruim)
    except ValueError:
        pass
assert bancario.validar_parametros("ted_horario", {"inicio": "07:05", "outro": 1}) == {"inicio": "07:05"}
for ruim in ({"inicio": "7:5"}, {"fim": "25:00"}):
    try:
        bancario.validar_parametros("ted_horario", ruim)
        raise AssertionError(ruim)
    except ValueError:
        pass
# conferência informativa da base (gerada sem calendário bancário)
fora = bancario.conferir_base(transacoes, titulares, bancos, R)
assert fora == {"ted_dia_util": 11, "ted_horario": 7, "pix_noturno_pf": 3}, fora
print("ok — regras por modalidade: PIX noturno PF (inclusive após a meia-noite), TED em dia útil e horário, "
      "transferência na mesma instituição, ajustes e conferência da base")

# ------------------------------------------------------------------ 3. API: simulação recorrente e bloqueios
auth.iniciar_banco()
assert migracoes.VERSAO_ATUAL >= 6 and 6 in migracoes.versoes_aplicadas()
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
assert ana.get("/api/resultados").get_json()["bancario"]["C001"] == bancos["C001"]
TED_SABADO = {"de": "C001", "para": "C030", "valor": "45000", "data": "2026-09-12", "hora": "18:00", "tipo": "TED"}
previa = beto.post("/api/transacoes/validar", headers=H, json=TED_SABADO).get_json()
assert previa["bloqueios"] == 2 and previa["origem"] == bancos["C001"]
r = beto.post("/api/transacoes", headers=H, json=TED_SABADO)
assert r.status_code == 400 and "sábado" in r.get_json()["erro"] and "17:00" in r.get_json()["erro"]
assert beto.get("/api/resultados").get_json()["simulacao"]["transacoes_simuladas"] == 0  # nada foi gravado
assert caio.post("/api/transacoes/validar", headers=H, json=TED_SABADO).status_code == 403
# recorrente: 4 PIX a cada 3 dias
r = beto.post("/api/transacoes", headers=H, json={**TED_SABADO, "tipo": "PIX", "valor": "2500", "hora": "22:00",
                                                    "data": "2026-09-01", "repetir": {"vezes": 4, "a_cada_dias": 3}})
j = r.get_json()
assert r.status_code == 201 and j["transacoes"] == ["S0001", "S0002", "S0003", "S0004"], j
datas = [s["data"] for s in beto.get("/api/resultados").get_json()["simulacao"]["lista_simuladas"]]
assert datas == ["2026-09-01", "2026-09-04", "2026-09-07", "2026-09-10"]
for ruim in ({"vezes": 31, "a_cada_dias": 1}, {"vezes": 3, "a_cada_dias": 0}, {"vezes": "x"}):
    assert beto.post("/api/transacoes/validar", headers=H, json={**TED_SABADO, "tipo": "PIX", "repetir": ruim}).status_code == 400
# alerta (não bloqueia): PIX noturno de pessoa física
r = beto.post("/api/transacoes", headers=H, json={"de": pf, "para": "C030", "valor": "3000", "data": "2026-09-02",
                                                    "hora": "23:30", "tipo": "PIX"})
assert r.status_code == 201 and r.get_json()["alertas"][0]["regra"] == "pix_noturno_pf"
print("ok — simulação: prévia, bloqueio sem gravar, recorrência a cada N dias, limites da repetição, alerta que não bloqueia")

# ------------------------------------------------------------------ 4. administrador ajusta as regras
assert beto.post("/api/modalidades/ted_horario", headers=H, json={"acao": "alertar"}).status_code == 403
r = ana.post("/api/modalidades/ted_horario", headers=H, json={"acao": "alertar", "parametros": {"fim": "18:30"}})
regra = next(x for x in r.get_json()["regras"] if x["id"] == "ted_horario")
assert r.status_code == 200 and regra["acao"] == "alertar" and regra["parametros"]["fim"] == "18:30"
assert regra["ajustado_por"] == "Ana Admin"
assert beto.post("/api/transacoes/validar", headers=H, json={**TED_SABADO, "data": "2026-09-14"}).get_json()["bloqueios"] == 0
assert ana.post("/api/modalidades/pix_24h", headers=H, json={"acao": "bloquear"}).status_code == 400
assert ana.post("/api/modalidades/inexistente", headers=H, json={"acao": "alertar"}).status_code == 404
assert ana.post("/api/modalidades/pix_noturno_pf", headers=H, json={"acao": "alertar", "parametros": {"limite": "x"}}).status_code == 400
r = ana.post("/api/modalidades/ted_horario", headers=H, json={"padrao": True})
assert next(x for x in r.get_json()["regras"] if x["id"] == "ted_horario")["acao"] == "bloquear"
assert any(l["evento"] == "regra_modalidade" for l in auth.listar_auditoria())
assert caio.get("/api/modalidades").status_code == 200                       # todos consultam
print("ok — regras: só o administrador ajusta, validação dos limites, voltar ao padrão e auditoria")

# ------------------------------------------------------------------ 5. histórico de cenários
assert beto.post("/api/cenarios", headers=H, json={"nome": "x"}).status_code == 400          # nome curto
r = beto.post("/api/cenarios", headers=H, json={"nome": "PIX recorrente C001", "descricao": "teste", "recorte": 0})
assert r.status_code == 201
cid = r.get_json()["id"]
cenario = beto.get(f"/api/cenarios/{cid}").get_json()
assert len(cenario["transacoes"]) == 5 and cenario["resumo"]["transacoes_simuladas"] == 5
assert cenario["resultado"]["dashboard"]["total_transacoes"] == 165
assert cenario["resultado_base"]["dashboard"]["total_transacoes"] == 160
assert cenario["comparacao"]["indicadores"]["total_transacoes"] == [160, 165]
assert ana.get(f"/api/cenarios/{cid}").status_code == 404                  # cenário é de quem salvou
assert caio.get("/api/cenarios").status_code == 403
# o cenário não muda quando a simulação em andamento muda
beto.post("/api/simulacao/restaurar", headers=H)
assert beto.get(f"/api/cenarios/{cid}").get_json()["resultado"]["dashboard"]["total_transacoes"] == 165
assert beto.post("/api/cenarios", headers=H, json={"nome": "Vazio"}).status_code == 400       # sem transações
# restaurar e excluir
assert beto.post(f"/api/cenarios/{cid}/restaurar", headers=H).get_json() == {"ok": True, "transacoes": 5}
assert beto.get("/api/resultados").get_json()["simulacao"]["transacoes_simuladas"] == 5
assert ana.delete(f"/api/cenarios/{cid}", headers=H).status_code == 404
assert beto.delete(f"/api/cenarios/{cid}", headers=H).status_code == 200
assert beto.get("/api/cenarios").get_json()["cenarios"] == []
assert beto.get("/api/resultados").get_json()["simulacao"]["transacoes_simuladas"] == 5          # o rascunho fica
print("ok — histórico: salvar com os dois resultados, imutável, só do dono, restaurar no simulador e excluir")

# ------------------------------------------------------------------ 6. comparação lado a lado (gabarito C025)
r = caio.get("/api/comparar?a=recorte:2026-08-01:2026-08-15&b=recorte:2026-09-01:2026-09-15")
assert r.status_code == 200
d = r.get_json()["diferencas"]
c025 = next(c for c in d["contas"] if c["id"] == "C025")
assert c025["comunidades_vizinhas"] == [1, 3]                                 # vira ponte entre três comunidades
assert c025["ranking"] == [8, 1] and c025["betweenness"][1] > c025["betweenness"][0]
assert d["destaques"]["mais_pontes"][0] == "C025"
assert d["indicadores"]["total_transacoes"] == [80, 80]
assert len(d["arestas_novas"]) == len(d["arestas_removidas"]) == 23
# o número de cada comunidade muda entre análises; "mudou de comunidade" compara o grupo
mesmo = comparacao.comparar(r.get_json()["a"], r.get_json()["a"])
assert not mesmo["destaques"]["mudaram_comunidade"] and not mesmo["arestas_novas"]
assert all(c["delta_score"] == 0 for c in mesmo["contas"])
assert caio.get("/api/comparar?a=base&b=rascunho").status_code == 403         # visualizador não compara simulações
assert beto.get("/api/comparar?a=base&b=rascunho").status_code == 200
assert beto.get("/api/comparar?a=base&b=cenario:999").status_code == 400
assert caio.get("/api/comparar?a=recorte:2026-09-10:2026-09-01&b=base").status_code == 400
print("ok — comparação: C025 passa de 1 para 3 comunidades vizinhas e do 8º para o 1º lugar (gabarito); "
      "comparação idêntica sem diferenças; permissões e erros")
print("TESTES OK: Fase 4 — dados bancários, regras por modalidade, simulação recorrente, histórico e comparação.")
