"""CSV: um arquivo por tabela (inclusive as completas), dentro de um .zip.

Separador ";" e vírgula decimal, em UTF-8 com BOM: o Excel em português abre com os
acentos e os números certos com dois cliques; o Power BI importa com "Português (Brasil)".
"""
import csv
import io
import re
import unicodedata
import zipfile

from app.exportacao.comum import celula


def _nome(texto):
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_")


def _texto(valor, fmt):
    valor, fmt = celula(valor, fmt)
    if valor is None:
        return ""
    if isinstance(valor, float):
        texto = f"{valor:.2f}" if fmt == "brl" else f"{valor:.6f}".rstrip("0").rstrip(".")
        return texto.replace(".", ",")
    return str(valor)


def _csv(cabecalho, linhas):
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(cabecalho)
    escritor.writerows(linhas)
    return "﻿" + saida.getvalue()


def gerar(documento):
    arquivos, usados = {}, set()
    arquivos["00_identificacao.csv"] = _csv(["Campo", "Valor"], documento["identificacao"])
    n = 1
    for secao in documento["secoes"]:
        for bloco in secao["blocos"]:
            if bloco["tipo"] == "tabela":
                fmts = [c["fmt"] for c in bloco["colunas"]]
                nome = _nome(bloco["nome"])
                if nome in usados:
                    continue
                usados.add(nome)
                arquivos[f"{n:02d}_{nome}.csv"] = _csv([c["nome"] for c in bloco["colunas"]],
                                                       [[_texto(v, f) for v, f in zip(l, fmts)] for l in bloco["linhas"]])
                n += 1
            elif bloco["tipo"] == "grafico":
                linhas = [[cat] + [_texto(s["valores"][i], bloco["fmt"]) for s in bloco["series"]]
                          for i, cat in enumerate(bloco["categorias"])]
                arquivos[f"{n:02d}_grafico_{_nome(bloco['titulo'])}.csv"] = _csv(
                    ["Categoria"] + [s["nome"] for s in bloco["series"]], linhas)
                n += 1
    leia = (f"{documento['titulo']}\r\n{documento['subtitulo']}\r\n\r\n"
            "Um arquivo CSV por tabela e por gráfico do relatório.\r\n"
            "Separador: ponto e vírgula (;) · decimal: vírgula · codificação: UTF-8.\r\n"
            "Excel: abra com dois cliques. Power BI: Obter dados > Texto/CSV, origem 'Português (Brasil)'.\r\n\r\n"
            f"{documento['aviso']}\r\n")
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("LEIA-ME.txt", "﻿" + leia)
        for nome, conteudo in arquivos.items():
            z.writestr(nome, conteudo.encode("utf-8"))
    return memoria.getvalue()
