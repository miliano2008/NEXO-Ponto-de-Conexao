"""NEXO — importação de bases (Fase 6, importação simples): lê o arquivo, sugere o mapeamento
das colunas, normaliza os valores e aponta os erros linha a linha. Não grava nada: quem grava é
banco/repositorio.substituir_base, depois da confirmação.

Aceita:
- .xlsx com uma aba de transações e, opcionalmente, uma aba de contas (as outras abas, como
  "Leia-me", são ignoradas);
- .csv só de transações (separador ; , tab ou |, UTF-8 ou Windows-1252).

Limites (decisão D6): 300 transações, 300 contas e 2 MB.

Formatos aceitos nas células:
- valor: 1234.56 · 1.234,56 · R$ 1.234,56 · número do Excel
- data: 2026-08-01 · 01/08/2026 · 01-08-2026 · data do Excel
- hora: 14:05 · 14:05:30 · 14h05 · hora do Excel (sem hora: 00:00, com aviso)
- modalidade: pix, ted, transferência/transferencia, doc, boleto (sem modalidade: "Não informado")
- titular: pf/pessoa física/cpf · pj/pessoa jurídica/cnpj · conta digital
"""

import csv
import hashlib
import io
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from nucleo import analise

MAX_TRANSACOES = 300
MAX_CONTAS = 300
MAX_BYTES = 2 * 1024 * 1024
MAX_ID = 40
LINHAS_PREVIA = 50
MAX_ERROS = 200

# campo: (rótulo na tela, obrigatório, sinônimos já normalizados — sem acento, minúsculos, só letras e números)
CAMPOS_TRANSACAO = {
    "id_transacao": ("Código da transação", False, ["idtransacao", "transacao", "id", "codigo", "codtransacao", "numero",
                                                    "nsu", "identificador", "idtx", "txid"]),
    "conta_origem": ("Conta de origem", True, ["contaorigem", "origem", "de", "pagador", "remetente", "contadebito",
                                              "debito", "from", "source", "ordenante"]),
    "conta_destino": ("Conta de destino", True, ["contadestino", "destino", "para", "recebedor", "favorecido",
                                                "beneficiario", "contacredito", "credito", "to", "target"]),
    "valor": ("Valor (R$)", True, ["valor", "valorrs", "montante", "quantia", "amount", "vlr", "valortransacao"]),
    "data": ("Data", True, ["data", "datatransacao", "dt", "date", "dia", "datahora"]),
    "hora": ("Hora", False, ["hora", "horario", "time", "hr"]),
    "tipo_transacao": ("Modalidade (PIX, TED…)", False, ["tipotransacao", "tipo", "modalidade", "meio", "canal",
                                                         "forma", "type"]),
}
CAMPOS_CONTA = {
    "id_conta": ("Código da conta", True, ["idconta", "conta", "id", "codigo", "numeroconta", "account"]),
    "tipo_titular": ("Tipo de titular", False, ["tipotitular", "titular", "tipo", "tipopessoa", "pessoa", "natureza"]),
    "data_abertura": ("Data de abertura", False, ["dataabertura", "abertura", "aberturaconta", "datacriacao", "desde"]),
}
TIPOS = {"pix": "PIX", "ted": "TED", "doc": "DOC", "transferencia": "Transferência", "transf": "Transferência",
         "tef": "Transferência", "boleto": "Boleto", "cartao": "Cartão"}
TITULARES = {"pf": "Pessoa Física", "pessoafisica": "Pessoa Física", "fisica": "Pessoa Física", "cpf": "Pessoa Física",
             "pj": "Pessoa Jurídica", "pessoajuridica": "Pessoa Jurídica", "juridica": "Pessoa Jurídica",
             "cnpj": "Pessoa Jurídica", "empresa": "Pessoa Jurídica", "contadigital": "Conta Digital",
             "digital": "Conta Digital"}


class ErroArquivo(ValueError):
    """Arquivo que não dá para ler (formato, tamanho, vazio)."""


def normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


# ---------------------------------------------------------------- leitura do arquivo

def _celula(v):
    if isinstance(v, str):
        return v.strip()
    return v


def _cortar_cabecalho(linhas):
    """Acha a linha do cabeçalho (a primeira com 2+ células de texto entre as 15 primeiras) e devolve
    (cabeçalho, linhas de dados, número da linha do cabeçalho na planilha)."""
    for i, linha in enumerate(linhas[:15]):
        textos = [c for c in linha if isinstance(c, str) and c.strip()]
        if len(textos) >= 2:
            dados = [l for l in linhas[i + 1:] if any(c not in (None, "") for c in l)]
            return [str(c).strip() if c is not None else "" for c in linha], dados, i + 1
    return [], [], 0


def ler_arquivo(nome, conteudo):
    """{"abas": [{"nome", "cabecalho", "linhas", "linha_cabecalho"}], "hash", "nome"}."""
    if len(conteudo) > MAX_BYTES:
        raise ErroArquivo(f"O arquivo tem {len(conteudo) / 1024 / 1024:.1f} MB; o limite é 2 MB.")
    if not conteudo:
        raise ErroArquivo("O arquivo está vazio.")
    extensao = nome.lower().rsplit(".", 1)[-1] if "." in nome else ""
    if extensao == "xlsx":
        abas = _ler_xlsx(conteudo)
    elif extensao in ("csv", "txt"):
        abas = [_ler_csv(conteudo, nome)]
    elif extensao == "xls":
        raise ErroArquivo("Arquivos .xls (Excel antigo) não são aceitos. No Excel: Arquivo → Salvar como → .xlsx.")
    else:
        raise ErroArquivo("Formato não aceito: envie um .xlsx ou um .csv.")
    abas = [a for a in abas if a["cabecalho"]]
    if not abas:
        raise ErroArquivo("Não encontrei uma linha de cabeçalho (nomes das colunas) no arquivo.")
    return {"nome": nome, "hash": hashlib.sha256(conteudo).hexdigest(), "abas": abas}


def _ler_xlsx(conteudo):
    import openpyxl
    try:
        livro = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except Exception as erro:  # noqa: BLE001 — arquivo corrompido ou que não é xlsx de verdade
        raise ErroArquivo("Não foi possível abrir a planilha. Confira se é um .xlsx válido (abra e salve de novo no Excel).") from erro
    abas = []
    for folha in livro.worksheets:
        linhas = []
        for linha in folha.iter_rows(values_only=True):
            linhas.append([_celula(c) for c in linha])
            if len(linhas) > MAX_TRANSACOES + 50:   # basta para detectar que passou do limite
                break
        cabecalho, dados, n = _cortar_cabecalho(linhas)
        largura = len(cabecalho)
        abas.append({"nome": folha.title, "cabecalho": cabecalho, "linha_cabecalho": n,
                     "linhas": [list(l[:largura]) + [None] * (largura - len(l)) for l in dados]})
    livro.close()
    return abas


def _ler_csv(conteudo, nome):
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            texto = conteudo.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    amostra = texto[:4096]
    try:
        separador = csv.Sniffer().sniff(amostra, delimiters=";,\t|").delimiter
    except csv.Error:
        separador = ";" if amostra.count(";") >= amostra.count(",") else ","
    linhas = [[_celula(c) for c in l] for l in csv.reader(io.StringIO(texto), delimiter=separador)]
    cabecalho, dados, n = _cortar_cabecalho(linhas)
    largura = len(cabecalho)
    return {"nome": nome, "cabecalho": cabecalho, "linha_cabecalho": n,
            "linhas": [list(l[:largura]) + [None] * (largura - len(l)) for l in dados]}


# ---------------------------------------------------------------- sugestões

def _pontuar(cabecalho, campos):
    """Mapeamento sugerido {campo: índice da coluna} e quantos campos obrigatórios foram achados."""
    normalizados = [normalizar(c) for c in cabecalho]
    mapa, usados = {}, set()
    for exato in (True, False):   # primeiro o nome exato, depois "contém"
        for campo, (_, _, sinonimos) in campos.items():
            if campo in mapa:
                continue
            for i, nome in enumerate(normalizados):
                if i in usados or not nome:
                    continue
                if (nome in sinonimos or nome == normalizar(campo)) if exato else any(
                        len(s) >= 4 and s in nome for s in sinonimos):
                    mapa[campo] = i
                    usados.add(i)
                    break
    obrigatorios = sum(1 for campo, (_, obrig, _) in campos.items() if obrig and campo in mapa)
    return mapa, obrigatorios


def assinatura_colunas(cabecalho):
    """Identifica um "layout" de arquivo pelos nomes das colunas (para reaproveitar o mapeamento salvo)."""
    return hashlib.sha256("|".join(normalizar(c) for c in cabecalho).encode()).hexdigest()


def sugerir(arquivo):
    """Aba de transações, aba de contas (ou None) e o mapeamento sugerido de cada uma."""
    melhor_tx, melhor_ct = None, None
    for i, aba in enumerate(arquivo["abas"]):
        mapa_tx, n_tx = _pontuar(aba["cabecalho"], CAMPOS_TRANSACAO)
        mapa_ct, n_ct = _pontuar(aba["cabecalho"], CAMPOS_CONTA)
        nome = normalizar(aba["nome"])
        bonus_tx = 1 if "transac" in nome or "moviment" in nome else 0
        bonus_ct = 1 if "conta" in nome and "transac" not in nome else 0
        if n_tx == 4 and (melhor_tx is None or n_tx + bonus_tx > melhor_tx[0]):
            melhor_tx = (n_tx + bonus_tx, i, mapa_tx)
        # aba de contas: tem o código da conta e não tem cara de transações
        if n_ct >= 1 and n_tx < 3 and (melhor_ct is None or n_ct + bonus_ct > melhor_ct[0]):
            melhor_ct = (n_ct + bonus_ct, i, mapa_ct)
    if melhor_tx is None:   # nenhuma aba tem as 4 colunas obrigatórias: sugere a primeira, para ajuste manual
        mapa_tx, _ = _pontuar(arquivo["abas"][0]["cabecalho"], CAMPOS_TRANSACAO)
        melhor_tx = (0, 0, mapa_tx)
    if melhor_ct is not None and melhor_ct[1] == melhor_tx[1]:
        melhor_ct = None
    return {"aba_transacoes": melhor_tx[1], "mapa_transacoes": melhor_tx[2],
            "aba_contas": melhor_ct[1] if melhor_ct else None, "mapa_contas": melhor_ct[2] if melhor_ct else {}}


# ---------------------------------------------------------------- normalização de cada valor

def ler_valor(v):
    if v is None or v == "":
        raise ValueError("valor vazio")
    if isinstance(v, bool):
        raise ValueError("valor inválido")
    if isinstance(v, (int, float, Decimal)):
        numero = Decimal(str(v))
    else:
        texto = re.sub(r"[R$\s]", "", str(v).replace(" ", ""))
        if "," in texto and "." in texto:
            texto = texto.replace(".", "").replace(",", ".") if texto.rfind(",") > texto.rfind(".") else texto.replace(",", "")
        elif "," in texto:
            texto = texto.replace(",", ".")
        elif texto.count(".") > 1:
            texto = texto.replace(".", "")
        try:
            numero = Decimal(texto)
        except InvalidOperation as erro:
            raise ValueError(f"valor “{v}” não é um número") from erro
    centavos = int((numero * 100).quantize(Decimal("1")))
    if centavos <= 0:
        raise ValueError("o valor precisa ser maior que zero")
    if centavos >= 10 ** 12:
        raise ValueError("valor grande demais")
    return centavos


def ler_data(v):
    if v is None or v == "":
        raise ValueError("data vazia")
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)) and 20000 < v < 80000:   # número de série do Excel
        return date(1899, 12, 30) + timedelta(days=int(v))
    texto = str(v).strip().split(" ")[0].split("T")[0]
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    if re.fullmatch(r"\d{1,4}[/.-]\d{1,2}[/.-]\d{2,4}", texto):
        raise ValueError(f"a data “{v}” não existe no calendário")
    raise ValueError(f"data “{v}” em formato desconhecido (use 01/08/2026 ou 2026-08-01)")


def ler_hora(v, data_original=None):
    """Hora da transação; se a coluna de data trouxer a hora junto (data e hora), ela é usada."""
    if (v is None or v == "") and isinstance(data_original, datetime) and data_original.time() != time(0, 0):
        return data_original.strftime("%H:%M")
    if (v is None or v == "") and isinstance(data_original, str) and re.search(r"\d{1,2}:\d{2}", data_original):
        v = re.search(r"\d{1,2}:\d{2}", data_original).group(0)
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.strftime("%H:%M")
    if isinstance(v, time):
        return v.strftime("%H:%M")
    if isinstance(v, timedelta):
        minutos = int(v.total_seconds()) // 60
        return f"{minutos // 60 % 24:02d}:{minutos % 60:02d}"
    if isinstance(v, (int, float)) and 0 <= v < 1:   # fração do dia do Excel
        minutos = round(v * 24 * 60)
        return f"{minutos // 60 % 24:02d}:{minutos % 60:02d}"
    m = re.fullmatch(r"(\d{1,2})\s*[:hH]\s*(\d{2})(?::\d{2})?(?:\s*min)?", str(v).strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ValueError(f"hora “{v}” inválida (use 14:05)")
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def ler_tipo(v):
    if v is None or str(v).strip() == "":
        return "Não informado"
    chave = normalizar(v)
    for prefixo, tipo in TIPOS.items():
        if chave == prefixo or chave.startswith(prefixo):
            return tipo
    return str(v).strip()[:30]


def ler_titular(v):
    if v is None or str(v).strip() == "":
        return "Não informado"
    return TITULARES.get(normalizar(v), str(v).strip()[:40])


def ler_codigo(v, rotulo):
    if v is None or str(v).strip() == "":
        raise ValueError(f"{rotulo} vazio")
    if isinstance(v, float) and v.is_integer():
        v = int(v)   # o Excel guarda números de conta como 12345.0
    texto = str(v).strip()
    if len(texto) > MAX_ID:
        raise ValueError(f"{rotulo} com mais de {MAX_ID} caracteres")
    return texto


# ---------------------------------------------------------------- preparação completa

def _coluna(linha, mapa, campo):
    i = mapa.get(campo)
    return linha[i] if i is not None and i < len(linha) else None


def preparar(arquivo, aba_transacoes, mapa_transacoes, aba_contas=None, mapa_contas=None, mascarar=False):
    """Normaliza e valida tudo. Retorna um dicionário com:
    contas/transacoes (prontas para gravar, já validadas pelo motor) se não houver erros; erros e avisos;
    prévia (até 50 linhas, com os valores interpretados e o erro de cada linha); resumo."""
    abas = arquivo["abas"]
    if not 0 <= aba_transacoes < len(abas):
        raise ErroArquivo("Escolha a aba das transações.")
    aba = abas[aba_transacoes]
    mapa = {k: int(v) for k, v in (mapa_transacoes or {}).items() if v not in (None, "", -1) and k in CAMPOS_TRANSACAO}
    erros, avisos = [], []

    def erro(linha, campo, mensagem):
        if len(erros) < MAX_ERROS:
            erros.append({"linha": linha, "campo": campo, "mensagem": mensagem})

    faltando = [CAMPOS_TRANSACAO[c][0] for c, (_, obrig, _) in CAMPOS_TRANSACAO.items() if obrig and c not in mapa]
    if faltando:
        return {"pode_importar": False, "erros": [{"linha": None, "campo": None,
                                                   "mensagem": "Indique a coluna de: " + ", ".join(faltando) + "."}],
                "avisos": [], "previa": [], "resumo": None}
    if len(aba["linhas"]) > MAX_TRANSACOES:
        return {"pode_importar": False, "previa": [], "resumo": None, "avisos": [],
                "erros": [{"linha": None, "campo": None, "mensagem":
                           f"O arquivo tem mais de {MAX_TRANSACOES} transações (limite do protótipo). Divida o arquivo ou filtre um período."}]}

    # transações
    transacoes, previa, vistos, sem_hora, ids_gerados = [], [], set(), 0, False
    for n, linha in enumerate(aba["linhas"], start=aba["linha_cabecalho"] + 1):
        problema = None
        registro = {"linha": n}
        try:
            tid = _coluna(linha, mapa, "id_transacao")
            if "id_transacao" not in mapa or tid in (None, ""):
                tid, ids_gerados = f"T{len(transacoes) + 1:04d}", True
            tid = ler_codigo(tid, "código da transação")
            if tid in vistos:
                raise ValueError(f"código da transação {tid} repetido")
            origem = ler_codigo(_coluna(linha, mapa, "conta_origem"), "conta de origem")
            destino = ler_codigo(_coluna(linha, mapa, "conta_destino"), "conta de destino")
            if origem == destino:
                raise ValueError("origem e destino são a mesma conta")
            centavos = ler_valor(_coluna(linha, mapa, "valor"))
            bruto_data = _coluna(linha, mapa, "data")
            dia = ler_data(bruto_data)
            hora = ler_hora(_coluna(linha, mapa, "hora"), bruto_data)
            if hora is None:
                hora, sem_hora = "00:00", sem_hora + 1
            tipo = ler_tipo(_coluna(linha, mapa, "tipo_transacao"))
            vistos.add(tid)
            t = {"id": tid, "de": origem, "para": destino, "centavos": centavos, "valor": centavos / 100,
                 "data": dia.isoformat(), "hora": hora, "tipo": tipo}
            transacoes.append(t)
            registro.update(t)
        except ValueError as e:
            problema = str(e)
            erro(n, None, problema[0].upper() + problema[1:] + ".")
        if len(previa) < LINHAS_PREVIA:
            previa.append({**registro, "erro": problema})
    if sem_hora:
        avisos.append(f"{sem_hora} transação(ões) sem hora: usei 00:00. As regras que dependem do horário "
                      "(concentração no tempo, PIX noturno) ficam menos precisas.")
    if ids_gerados:
        avisos.append("Transações sem código: o NEXO numerou como T0001, T0002…")
    sem_tipo = sum(1 for t in transacoes if t["tipo"] == "Não informado")
    if sem_tipo:
        avisos.append(f"{sem_tipo} transação(ões) sem modalidade: aparecem como “Não informado”.")

    # contas: da aba de contas (se houver) ou deduzidas das transações
    contas, usadas = {}, {c for t in transacoes for c in (t["de"], t["para"])}
    primeira_data = {}
    for t in sorted(transacoes, key=lambda t: t["data"]):
        primeira_data.setdefault(t["de"], t["data"]); primeira_data.setdefault(t["para"], t["data"])
    if aba_contas is not None and aba_contas != "" and int(aba_contas) >= 0:
        aba_c = abas[int(aba_contas)]
        mapa_c = {k: int(v) for k, v in (mapa_contas or {}).items() if v not in (None, "", -1) and k in CAMPOS_CONTA}
        if "id_conta" not in mapa_c:
            erro(None, None, "Indique a coluna com o código da conta na aba de contas (ou não use aba de contas).")
        elif len(aba_c["linhas"]) > MAX_CONTAS:
            erro(None, None, f"A aba de contas tem mais de {MAX_CONTAS} contas (limite do protótipo).")
        else:
            for n, linha in enumerate(aba_c["linhas"], start=aba_c["linha_cabecalho"] + 1):
                try:
                    cid = ler_codigo(_coluna(linha, mapa_c, "id_conta"), "código da conta")
                    if cid in contas:
                        raise ValueError(f"conta {cid} repetida na aba de contas")
                    bruto = _coluna(linha, mapa_c, "data_abertura")
                    abertura = ler_data(bruto).isoformat() if bruto not in (None, "") else None
                    contas[cid] = {"id_conta": cid, "tipo_titular": ler_titular(_coluna(linha, mapa_c, "tipo_titular")),
                                   "data_abertura": abertura}
                except ValueError as e:
                    erro(n, "contas", f"Aba “{aba_c['nome']}”: {str(e)[0].upper() + str(e)[1:]}.")
            faltam = sorted(usadas - set(contas))
            if faltam:
                erro(None, None, f"{len(faltam)} conta(s) das transações não estão na aba de contas: "
                                 f"{', '.join(faltam[:10])}{'…' if len(faltam) > 10 else ''}.")
            sem_mov = len(set(contas) - usadas)
            if sem_mov:
                avisos.append(f"{sem_mov} conta(s) da aba de contas não aparecem em nenhuma transação (entram na rede sem conexões).")
    else:
        contas = {cid: {"id_conta": cid, "tipo_titular": "Não informado", "data_abertura": None} for cid in sorted(usadas)}
        if contas:
            avisos.append("Sem aba de contas: as contas foram tiradas das transações, com o tipo de titular “Não informado”.")
    sem_abertura = [c for c in contas.values() if not c["data_abertura"]]
    for c in sem_abertura:
        c["data_abertura"] = primeira_data.get(c["id_conta"], min(primeira_data.values(), default=date.today().isoformat()))
    if sem_abertura and aba_contas not in (None, ""):
        avisos.append(f"{len(sem_abertura)} conta(s) sem data de abertura: usei a data da primeira transação.")
    if len(contas) > MAX_CONTAS:
        erro(None, None, f"A base tem {len(contas)} contas; o limite do protótipo é {MAX_CONTAS}.")
    if not transacoes and not erros:
        erro(None, None, "Nenhuma transação encontrada no arquivo.")
    if len(contas) < 3 and not erros:
        erro(None, None, "A base precisa de pelo menos 3 contas para formar uma rede.")

    # LGPD: troca os códigos por pseudônimos (C001…, T0001…) antes de gravar; a tabela de troca não é guardada
    if mascarar and not erros:
        novo = {cid: f"C{i:03d}" for i, cid in enumerate(sorted(contas, key=lambda c: (primeira_data.get(c, "9999"), c)), start=1)}
        contas = {novo[k]: {**v, "id_conta": novo[k]} for k, v in contas.items()}
        transacoes = [{**t, "id": f"T{i:04d}", "de": novo[t["de"]], "para": novo[t["para"]]}
                      for i, t in enumerate(sorted(transacoes, key=lambda t: (t["data"], t["hora"], t["id"])), start=1)]
        for p in previa:
            if not p.get("erro") and "de" in p:
                p.update(de=novo[p["de"]], para=novo[p["para"]])
        avisos.append("Códigos mascarados: contas viraram C001, C002… e transações T0001, T0002… "
                      "A correspondência com os códigos originais não é guardada.")

    resumo = None
    pronto_contas, pronto_tx = None, None
    if transacoes:
        datas = sorted(t["data"] for t in transacoes)
        por_tipo = {}
        for t in transacoes:
            por_tipo[t["tipo"]] = por_tipo.get(t["tipo"], 0) + 1
        resumo = {"transacoes": len(transacoes), "linhas": len(aba["linhas"]), "contas": len(contas),
                  "periodo": [datas[0], datas[-1]], "volume": round(sum(t["centavos"] for t in transacoes) / 100, 2),
                  "por_tipo": por_tipo,
                  "por_titular": {k: sum(1 for c in contas.values() if c["tipo_titular"] == k)
                                  for k in sorted({c["tipo_titular"] for c in contas.values()})}}
    if not erros:
        # rede final passa pela mesma validação do motor (garantia de que a análise vai rodar)
        try:
            linhas_csv = [{"id_transacao": t["id"], "conta_origem": t["de"], "conta_destino": t["para"],
                           "valor": f"{t['centavos'] / 100:.2f}", "data": t["data"], "hora": t["hora"],
                           "tipo_transacao": t["tipo"]} for t in transacoes]
            pronto_contas, pronto_tx = analise.validar_dados(list(contas.values()), linhas_csv)
        except ValueError as e:
            erro(None, None, str(e))
    return {"pode_importar": not erros, "erros": erros, "avisos": avisos, "previa": previa, "resumo": resumo,
            "contas": pronto_contas if not erros else None, "transacoes": pronto_tx if not erros else None}


# ---------------------------------------------------------------- modelo para baixar

def modelo_xlsx():
    """Planilha modelo: abas Transacoes e Contas com exemplos e uma aba de instruções."""
    import xlsxwriter
    memoria = io.BytesIO()
    wb = xlsxwriter.Workbook(memoria, {"in_memory": True})
    cab = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#0B1F3A"})
    data, hora, brl = wb.add_format({"num_format": "dd/mm/yyyy"}), wb.add_format({"num_format": "hh:mm"}), \
        wb.add_format({"num_format": '"R$" #,##0.00'})
    tx = wb.add_worksheet("Transacoes")
    tx.write_row(0, 0, ["id_transacao", "conta_origem", "conta_destino", "valor", "data", "hora", "tipo_transacao"], cab)
    exemplos = [("T0001", "C001", "C002", 1500.00, date(2026, 8, 1), time(9, 30), "PIX"),
                ("T0002", "C002", "C003", 1450.00, date(2026, 8, 1), time(10, 5), "TED"),
                ("T0003", "C003", "C001", 980.50, date(2026, 8, 2), time(16, 45), "Transferência")]
    for i, (tid, de, para, valor, dia, hr, tipo) in enumerate(exemplos, start=1):
        tx.write(i, 0, tid); tx.write(i, 1, de); tx.write(i, 2, para); tx.write_number(i, 3, valor, brl)
        tx.write_datetime(i, 4, datetime.combine(dia, time()), data)
        tx.write_datetime(i, 5, datetime.combine(date(1899, 12, 31), hr), hora); tx.write(i, 6, tipo)
    tx.set_column(0, 6, 16)
    ct = wb.add_worksheet("Contas")
    ct.write_row(0, 0, ["id_conta", "tipo_titular", "data_abertura"], cab)
    for i, (cid, tipo, dia) in enumerate([("C001", "Pessoa Física", date(2020, 5, 10)),
                                          ("C002", "Pessoa Jurídica", date(2018, 1, 22)),
                                          ("C003", "Conta Digital", date(2024, 3, 3))], start=1):
        ct.write(i, 0, cid); ct.write(i, 1, tipo); ct.write_datetime(i, 2, datetime.combine(dia, time()), data)
    ct.set_column(0, 2, 18)
    ajuda = wb.add_worksheet("Instrucoes")
    ajuda.set_column(0, 0, 110)
    textos = ["Modelo de base para o NEXO (importação simples).",
              "Aba Transacoes (obrigatória): conta_origem, conta_destino, valor e data são obrigatórios; "
              "id_transacao, hora e tipo_transacao são opcionais.",
              "Aba Contas (opcional): id_conta obrigatório; tipo_titular (Pessoa Física, Pessoa Jurídica ou Conta Digital) "
              "e data_abertura opcionais. Sem esta aba, as contas são tiradas das transações.",
              "Valor: 1500,00 ou 1.500,00 ou R$ 1.500,00. Data: 01/08/2026. Hora: 14:05. Modalidade: PIX, TED, Transferência…",
              f"Limites: {MAX_TRANSACOES} transações, {MAX_CONTAS} contas, 2 MB. Os nomes das colunas podem ser outros: "
              "o NEXO sugere a correspondência e você ajusta na tela.",
              "Não use dados pessoais reais sem autorização. Se precisar, marque “Mascarar códigos” na importação."]
    for i, t in enumerate(textos):
        ajuda.write(i, 0, t)
    wb.close()
    return memoria.getvalue()
