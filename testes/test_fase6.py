"""Testes da Fase 6 (importação simples): leitura de .xlsx e .csv, sugestão e mapeamento de colunas,
erros linha a linha, limites, mascaramento, backup automático, troca da base em uma transação
(com a limpeza do que dependia da base antiga), volta à base de demonstração e permissões.

Executar (na raiz do projeto): python -m testes.test_fase6
Usa CSV + SQLite temporários e uma pasta de backups temporária: nunca toca no banco do grupo.
"""
import io
import os
import tempfile
from pathlib import Path

os.environ["NEXO_BANCO"] = "local"
for _chave in [k for k in os.environ if k.startswith(("DB_", "SMTP_", "APP_URL", "GOOGLE_"))]:
    del os.environ[_chave]

from banco import conexao as db  # noqa: E402

TEMP = Path(tempfile.mkdtemp())
db.SQLITE = TEMP / "fase6.db"

from app import analises, auth, servidor  # noqa: E402
from banco import backup, migracoes, repositorio  # noqa: E402
from nucleo import importacao as imp  # noqa: E402
from nucleo.configuracao import PASTA_DADOS  # noqa: E402

backup.PASTA_BACKUPS = TEMP / "backups"
H = {"X-Requested-With": "NEXO"}
auth.iniciar_banco()
assert 8 in migracoes.versoes_aplicadas()
auth.cadastrar("52998224725", "Ana Admin", "ana@nexo.test", "11912345678", "Senha123", "Senha123",
               cargo="administrador", email_confirmado=True)
auth.cadastrar("11144477735", "Beto Analista", "beto@nexo.test", "11912345679", "Senha123", "Senha123",
               cargo="analista", email_confirmado=True)


def cliente(login):
    servidor._tentativas_ip.clear()
    c = servidor.app.test_client()
    assert c.post("/auth/entrar", headers=H, json={"login": login, "senha": "Senha123"}).status_code == 200
    return c


ana, beto = cliente("ana@nexo.test"), cliente("beto@nexo.test")


def enviar(cliente_, nome, conteudo):
    return cliente_.post("/api/importacao/arquivo", headers=H, content_type="multipart/form-data",
                         data={"arquivo": (io.BytesIO(conteudo), nome)})


def corpo_de(resposta, **extra):
    s = resposta.get_json()["sugestao"]
    return {"aba_transacoes": s["aba_transacoes"], "mapa_transacoes": s["mapa_transacoes"],
            "aba_contas": s["aba_contas"], "mapa_contas": s["mapa_contas"], **extra}


# ------------------------------------------------------------------ 1. normalização dos valores
assert imp.ler_valor("R$ 1.234,56") == imp.ler_valor("1,234.56") == imp.ler_valor(1234.56) == 123456
assert imp.ler_valor("1.000.000") == 100000000
for ruim in ("abc", "0", "-5", "", None):
    try:
        imp.ler_valor(ruim)
        raise AssertionError(ruim)
    except ValueError:
        pass
assert str(imp.ler_data("01/08/2026")) == str(imp.ler_data("2026-08-01")) == str(imp.ler_data(46235)) == "2026-08-01"
for ruim, trecho in (("31/02/2026", "não existe"), ("ontem", "formato desconhecido")):
    try:
        imp.ler_data(ruim)
        raise AssertionError(ruim)
    except ValueError as erro:
        assert trecho in str(erro)
assert imp.ler_hora("14h05") == imp.ler_hora("14:05:59") == imp.ler_hora(14.0 / 24 + 5 / 1440) == "14:05"
assert imp.ler_hora(None) is None and imp.ler_hora(None, "01/08/2026 09:30") == "09:30"
assert [imp.ler_tipo(x) for x in ("pix", "TED", "transferencia", "Transf.", None)] == \
    ["PIX", "TED", "Transferência", "Transferência", "Não informado"]
assert [imp.ler_titular(x) for x in ("PF", "pessoa jurídica", "CNPJ", "conta digital", "")] == \
    ["Pessoa Física", "Pessoa Jurídica", "Pessoa Jurídica", "Conta Digital", "Não informado"]
assert imp.ler_codigo(12345.0, "conta") == "12345"                                # número do Excel vira código
print("ok — valores, datas (inclusive do Excel), horas, modalidades e titulares em vários formatos")

# ------------------------------------------------------------------ 2. a planilha original reproduz a base exata
planilha = (PASTA_DADOS / "NEXO_Base_Transacoes.xlsx").read_bytes()
arquivo = imp.ler_arquivo("NEXO_Base_Transacoes.xlsx", planilha)
s = imp.sugerir(arquivo)
assert arquivo["abas"][s["aba_transacoes"]]["nome"] == "Transacoes" and arquivo["abas"][s["aba_contas"]]["nome"] == "Contas"
r = imp.preparar(arquivo, s["aba_transacoes"], s["mapa_transacoes"], s["aba_contas"], s["mapa_contas"])
assert r["pode_importar"] and (r["contas"], r["transacoes"]) == repositorio.carregar_csv()
print("ok — planilha original: abas certas (Leia-me e Dicionário ignorados) e base idêntica aos CSVs")

# ------------------------------------------------------------------ 3. permissões e limites
assert beto.get("/api/base").status_code == 200 and "historico" not in beto.get("/api/base").get_json()
assert enviar(beto, "x.csv", b"a;b\n1;2\n").status_code == 403                       # só o administrador importa
assert beto.post("/api/base/demonstracao", headers=H, json={"confirmacao": "SUBSTITUIR"}).status_code == 403
assert ana.post("/api/importacao/previa", headers=H, json={}).status_code == 400      # sem arquivo enviado
for nome, conteudo, trecho in (("x.xls", b"abc", ".xls"), ("x.pdf", b"abc", "Formato"), ("x.csv", b"", "vazio"),
                               ("x.xlsx", b"nao sou planilha", "planilha"), ("x.csv", b"so uma coluna\n1\n", "cabeçalho")):
    r = enviar(ana, nome, conteudo)
    assert r.status_code == 400 and trecho in r.get_json()["erro"], (nome, r.get_json())
grande = enviar(ana, "x.csv", b"a;b\n" + b"1;2\n" * 800_000)
assert grande.status_code == 413 and "2 MB" in grande.get_json()["erro"]
muitas = "origem;destino;valor;data\n" + "".join(f"A{i % 7};B{i % 5};10;01/08/2026\n" for i in range(301))
r = enviar(ana, "muitas.csv", muitas.encode())
assert not r.get_json()["resultado"]["pode_importar"] and "300" in r.get_json()["resultado"]["erros"][0]["mensagem"]
print("ok — permissões (só o administrador importa), formatos recusados, 2 MB e 300 transações")

# ------------------------------------------------------------------ 4. CSV com erros: prévia aponta a linha
csv_ruim = ("Pagador;Favorecido;Valor (R$);Data da operação;Horário;Meio\n"
            "Ana;Bruno;R$ 1.234,56;01/08/2026;14h05;pix\n"
            "Bruno;Carla;abc;02/08/2026;10:00;ted\n"
            "Carla;Carla;10;03/08/2026;10:00;PIX\n").encode("cp1252")
r = enviar(ana, "ruim.csv", csv_ruim)
res = r.get_json()["resultado"]
assert set(r.get_json()["sugestao"]["mapa_transacoes"]) == {"conta_origem", "conta_destino", "valor", "data", "hora", "tipo_transacao"}
assert not res["pode_importar"] and [e["linha"] for e in res["erros"]] == [3, 4]
assert "abc" in res["erros"][0]["mensagem"] and "mesma conta" in res["erros"][1]["mensagem"]
assert res["previa"][0]["de"] == "Ana" and res["previa"][0]["valor"] == 1234.56 and res["previa"][1]["erro"]
confirmar = ana.post("/api/importacao/confirmar", headers=H, json=corpo_de(r, nome="Ruim", confirmacao="SUBSTITUIR", aceite=True))
assert confirmar.status_code == 400 and "erros" in confirmar.get_json()["erro"]
print("ok — CSV (Windows-1252, ;) com outros nomes de coluna: sugestão automática e erros por linha")

# ------------------------------------------------------------------ 5. importação válida troca a base e limpa o que dependia dela
ana.post("/api/transacoes", headers=H, json={"de": "C001", "para": "C030", "valor": "100", "data": "2026-09-14",
                                             "hora": "12:00", "tipo": "PIX"})
assert ana.post("/api/cenarios", headers=H, json={"nome": "Cenário antigo", "recorte": {}}).status_code in (200, 201)
assert ana.post("/api/casos/C025", headers=H, json={"situacao": "em_analise", "comentario": "Conferir os repasses"}).status_code == 200
ana.post("/api/parametros-risco", headers=H, json={"valores": {"fan_min_contas": 3}})
antes = ana.get("/api/base").get_json()
assert antes["base"]["origem"] == "demonstracao" and antes["base"]["transacoes"] == 160
assert antes["apagados_na_troca"]["cenarios"] == 1 and antes["apagados_na_troca"]["investigacoes"] == 1

pessoas = ["Ana", "Bruno", "Carla", "Davi", "Eva", "Fábio"]
linhas = ["Pagador;Favorecido;Valor (R$);Data da operação;Horário;Meio"]
for i in range(40):
    linhas.append(f"{pessoas[i % 6]};{pessoas[(i * 2 + 1) % 6]};{100 + i * 37},50;{1 + i % 28:02d}/10/2026;{8 + i % 12}:15;"
                  f"{['pix', 'TED', 'transferência'][i % 3]}")
linhas = [l for l in linhas if l.split(";")[0] != l.split(";")[1]]
bom = "\n".join(linhas).encode("utf-8")
r = enviar(ana, "empresa_x.csv", bom)
res = r.get_json()["resultado"]
assert res["pode_importar"], res["erros"]
assert res["resumo"]["contas"] == 6 and res["resumo"]["transacoes"] == len(linhas) - 1
assert any("Sem aba de contas" in a for a in res["avisos"]) and any("T0001" in a for a in res["avisos"])
for faltando, trecho in (({"confirmacao": "sim"}, "SUBSTITUIR"), ({"aceite": False}, "autorização"), ({"nome": "x"}, "nome")):
    j = corpo_de(r, **{"nome": "Empresa X — outubro", "confirmacao": "SUBSTITUIR", "aceite": True, **faltando})
    resp = ana.post("/api/importacao/confirmar", headers=H, json=j)
    assert resp.status_code == 400 and trecho in resp.get_json()["erro"], (faltando, resp.get_json())
resp = ana.post("/api/importacao/confirmar", headers=H, json=corpo_de(r, nome="Empresa X — outubro",
                                                                      confirmacao="substituir", aceite=True))
assert resp.status_code == 200, resp.get_json()
assert (backup.PASTA_BACKUPS / resp.get_json()["backup"]).is_file()                 # backup automático antes da troca

dados = beto.get("/api/resultados").get_json()                                      # vale na hora, para todos
assert dados["dashboard"]["total_contas"] == 6 and dados["dashboard"]["total_transacoes"] == len(linhas) - 1
assert dados["base"]["nome"] == "Empresa X — outubro" and dados["simulacao"]["transacoes_simuladas"] == 0
assert {c["id"] for c in dados["contas"]} == set(pessoas)
assert dados["risco"]["parametros"]["fan_min_contas"] == 3                          # limites das regras ficam
depois = ana.get("/api/base").get_json()
assert depois["apagados_na_troca"] == {"rascunhos": 0, "cenarios": 0, "transacoes_simuladas": 0, "analises": 1,
                                       "investigacoes": 0}                          # só a análise nova da base
assert len(auth.listar_usuarios()) == 2                                             # usuários ficam
assert [h["situacao"] for h in depois["historico"]] == ["ativa"] and depois["historico"][0]["importado_por"] == "Ana Admin"
evento = next(e for e in auth.listar_auditoria() if e["evento"] == "base_importada")
assert "Empresa X" in evento["detalhe"] and "empresa_x.csv" in evento["detalhe"]
r = beto.get("/api/relatorio?tipo=analise&formato=xlsx")
assert r.status_code == 200                                                         # relatórios na base nova
import openpyxl  # noqa: E402
linhas_id = {l[0]: l[1] for l in openpyxl.load_workbook(io.BytesIO(r.data))["Resumo"].iter_rows(values_only=True) if l[0]}
assert linhas_id["Base"] == "Empresa X — outubro"
print("ok — importação válida: backup automático, troca em uma transação, base nova para todos, "
      "simulações/cenários/investigações apagados, usuários e limites mantidos, auditoria e relatório")

# ------------------------------------------------------------------ 6. mapeamento salvo, mascaramento e mesmo arquivo
estranho = "col_a;col_b;col_c;col_d\nX1;X2;50;01/09/2026\nX2;X3;60;02/09/2026\nX3;X1;70;03/09/2026\n".encode()
r = enviar(ana, "estranho.csv", estranho)
assert not r.get_json()["resultado"]["pode_importar"]                              # colunas sem nome conhecido
mapa = {"conta_origem": 0, "conta_destino": 1, "valor": 2, "data": 3}
p = ana.post("/api/importacao/previa", headers=H, json={"aba_transacoes": 0, "mapa_transacoes": mapa, "mascarar": True})
res = p.get_json()["resultado"]
assert res["pode_importar"] and res["previa"][0]["de"] == "C001" and any("mascarados" in a for a in res["avisos"])
resp = ana.post("/api/importacao/confirmar", headers=H, json={"aba_transacoes": 0, "mapa_transacoes": mapa, "mascarar": True,
                                                               "nome": "Base mascarada", "confirmacao": "SUBSTITUIR", "aceite": True})
assert resp.status_code == 200
with db.conectar() as c:
    codigos = {l["id_conta"] for l in c.execute("SELECT id_conta FROM contas").fetchall()}
assert codigos == {"C001", "C002", "C003"}                                         # os códigos originais não ficaram
r = enviar(ana, "estranho.csv", estranho)                                           # o mesmo layout de novo:
assert r.get_json()["mapeamento_salvo"] and r.get_json()["resultado"]["pode_importar"]   # usa o mapeamento salvo
assert r.get_json()["mesmo_arquivo_da_base"]
print("ok — mapeamento manual salvo e reaproveitado, mascaramento (C001…) e aviso de arquivo repetido")

# ------------------------------------------------------------------ 7. modelo e volta à base de demonstração
modelo = ana.get("/api/importacao/modelo")
assert modelo.status_code == 200 and modelo.data[:2] == b"PK"
r = enviar(ana, "modelo.xlsx", modelo.data)
res = r.get_json()["resultado"]
assert res["pode_importar"] and res["resumo"]["contas"] == 3 and res["resumo"]["transacoes"] == 3
assert r.get_json()["abas"][r.get_json()["sugestao"]["aba_transacoes"]]["nome"] == "Transacoes"
assert ana.post("/api/base/demonstracao", headers=H, json={"confirmacao": "nao"}).status_code == 400
resp = ana.post("/api/base/demonstracao", headers=H, json={"confirmacao": "SUBSTITUIR"})
assert resp.status_code == 200 and resp.get_json()["base"]["origem"] == "demonstracao"
dados = ana.get("/api/resultados").get_json()
assert dados["dashboard"]["total_transacoes"] == 160 and dados["contas"][0]["id"] == "C025"   # gabarito de volta
hist = ana.get("/api/base").get_json()["historico"]
assert [h["situacao"] for h in hist] == ["ativa", "substituida", "substituida"] and hist[0]["origem"] == "demonstracao"
assert len(list(backup.PASTA_BACKUPS.iterdir())) == 3                              # um backup por troca
analises.limpar_cache()
print("ok — modelo .xlsx importável, volta à base de demonstração (gabarito C025) e histórico das trocas")

# ------------------------------------------------------------------ 8. texto importado nunca vira fórmula nos relatórios
import zipfile  # noqa: E402

from app import exportacao  # noqa: E402
from nucleo import relatorio  # noqa: E402

doc = {"titulo": "T", "subtitulo": "S", "aviso": "A", "arquivo": "x", "identificacao": [("Base", "=SOMA(1;2)")],
       "secoes": [relatorio.secao("1", relatorio.tabela("Contas", "Contas", [("Conta", "txt")], [["=HIPERLINK(\"x\")"], ["C001"]]))]}
xlsx, _, _ = exportacao.gerar(doc, "xlsx")
with zipfile.ZipFile(io.BytesIO(xlsx)) as z:
    assert not any(b"<f>" in z.read(n) for n in z.namelist() if n.startswith("xl/worksheets/"))
celulas = [c.value for l in openpyxl.load_workbook(io.BytesIO(xlsx))["Contas"].iter_rows(min_row=4) for c in l]
assert celulas == ['=HIPERLINK("x")', "C001"]
zipado, _, _ = exportacao.gerar(doc, "csv")
with zipfile.ZipFile(io.BytesIO(zipado)) as z:
    texto = z.read(next(n for n in z.namelist() if n.endswith("contas.csv"))).decode("utf-8-sig")
assert "'=HIPERLINK" in texto
print("ok — textos vindos da base (ex.: “=HIPERLINK(…)”) ficam texto no Excel e no CSV, nunca fórmula")

print("TESTES OK: Fase 6 — importação simples (xlsx/csv, mapeamento, erros por linha, limites, mascaramento, "
      "backup automático, troca atômica, base de demonstração e permissões).")
