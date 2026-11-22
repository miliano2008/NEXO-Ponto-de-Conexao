"""Excel (.xlsx): aba Resumo, aba Gráficos (gráficos nativos do Excel com os dados ao lado)
e uma aba por tabela, com números de verdade (somáveis), filtros e cabeçalho fixo."""
import io

import xlsxwriter

from app.exportacao.comum import AZUL, AZUL_CLARO, FORMATO_OFFICE, LINHA, NAVY, SERIES, celula, cores_do_grafico, formatar

TIPO = {"colunas": "column", "colunas_agrupadas": "column", "barras": "bar", "pizza": "doughnut", "linha": "line"}


def _nome_aba(nome, usados):
    base = "".join(ch for ch in nome if ch not in '[]:*?/\\')[:28] or "Tabela"
    nome, i = base, 2
    while nome.lower() in usados:
        nome, i = f"{base[:26]} {i}", i + 1
    usados.add(nome.lower())
    return nome


def gerar(documento):
    memoria = io.BytesIO()
    # strings_to_formulas=False: um texto da base importada que comece com "=" fica texto, nunca fórmula
    wb = xlsxwriter.Workbook(memoria, {"in_memory": True, "strings_to_numbers": False, "strings_to_formulas": False})
    wb.set_properties({"title": documento["titulo"], "subject": documento["subtitulo"], "author": "NEXO",
                       "comments": documento["aviso"]})
    f = {
        "titulo": wb.add_format({"bold": True, "font_size": 16, "font_color": f"#{NAVY}"}),
        "sub": wb.add_format({"font_size": 10, "font_color": "#4A5A6E"}),
        "secao": wb.add_format({"bold": True, "font_size": 12, "font_color": f"#{AZUL}", "bottom": 1, "bottom_color": f"#{LINHA}"}),
        "rotulo": wb.add_format({"bold": True, "font_color": "#4A5A6E", "valign": "top"}),
        "texto": wb.add_format({"text_wrap": True, "valign": "top"}),
        "aviso": wb.add_format({"text_wrap": True, "italic": True, "font_color": "#8A5A00", "bg_color": "#FCF3E1", "valign": "top"}),
        "kpi": wb.add_format({"bold": True, "font_size": 14, "font_color": f"#{NAVY}", "bg_color": f"#{AZUL_CLARO}", "align": "left"}),
        "kpi_r": wb.add_format({"font_size": 9, "font_color": "#4A5A6E", "bg_color": f"#{AZUL_CLARO}"}),
        "cab": wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": f"#{NAVY}", "text_wrap": True, "valign": "vcenter", "border": 1, "border_color": f"#{NAVY}"}),
    }
    num = {fmt: wb.add_format({"num_format": codigo, "valign": "top"}) for fmt, codigo in FORMATO_OFFICE.items()}
    usados = set()

    # ---------- Resumo
    resumo = wb.add_worksheet(_nome_aba("Resumo", usados))
    resumo.hide_gridlines(2)
    resumo.set_column(0, 0, 26); resumo.set_column(1, 1, 100)
    resumo.write(0, 0, documento["titulo"], f["titulo"])
    resumo.write(1, 0, documento["subtitulo"], f["sub"])
    linha = 3
    for rotulo, valor in documento["identificacao"]:
        resumo.write(linha, 0, rotulo, f["rotulo"]); resumo.write(linha, 1, valor, f["texto"]); linha += 1
    linha += 1
    graficos = []
    for secao in documento["secoes"]:
        textos = [b for b in secao["blocos"] if b["tipo"] in ("paragrafo", "aviso", "lista", "indicadores")]
        graficos += [b for b in secao["blocos"] if b["tipo"] == "grafico"]
        if not textos:
            continue
        resumo.write(linha, 0, secao["titulo"], f["secao"]); resumo.write(linha, 1, "", f["secao"]); linha += 1
        for b in textos:
            if b["tipo"] == "indicadores":
                for it in b["itens"]:
                    resumo.write(linha, 0, it["rotulo"], f["kpi_r"])
                    resumo.write(linha, 1, it["valor"] + (f"   ({it['nota']})" if it["nota"] else ""), f["kpi"]); linha += 1
            elif b["tipo"] == "lista":
                for item in b["itens"]:
                    resumo.write(linha, 1, f"• {item}", f["texto"]); resumo.set_row(linha, 15 * (1 + len(item) // 110)); linha += 1
            else:
                resumo.write(linha, 1, b["texto"], f["aviso" if b["tipo"] == "aviso" else "texto"])
                resumo.set_row(linha, 15 * (1 + len(b["texto"]) // 110)); linha += 1
        linha += 1
    tabelas = [b for s in documento["secoes"] for b in s["blocos"] if b["tipo"] == "tabela"]
    resumo.write(linha, 0, "Abas", f["secao"]); resumo.write(linha, 1, "", f["secao"]); linha += 1
    resumo.write(linha, 0, "Gráficos", f["rotulo"]); resumo.write(linha, 1, f"{len(graficos)} gráfico(s) nativo(s) com os dados ao lado", f["texto"]); linha += 1
    for b in tabelas:
        resumo.write(linha, 0, b["nome"], f["rotulo"]); resumo.write(linha, 1, f"{b['titulo']} — {len(b['linhas'])} linha(s)", f["texto"]); linha += 1

    # ---------- Gráficos (dados na coluna A–D, gráfico ao lado)
    if graficos:
        aba = wb.add_worksheet(_nome_aba("Gráficos", usados))
        nome_aba = aba.get_name()
        aba.set_column(0, 0, 30); aba.set_column(1, 3, 16)
        linha = 0
        for g in graficos:
            aba.write(linha, 0, g["titulo"], f["secao"])
            aba.write_row(linha + 1, 0, ["Categoria"] + [s["nome"] for s in g["series"]], f["cab"])
            for i, cat in enumerate(g["categorias"]):
                aba.write(linha + 2 + i, 0, cat)
                for j, s in enumerate(g["series"]):
                    aba.write_number(linha + 2 + i, 1 + j, s["valores"][i], num.get(g["fmt"], num["dec2"]))
            tipo = TIPO[g["forma"]]
            grafico = wb.add_chart({"type": tipo})
            cores = cores_do_grafico(g)
            n = len(g["categorias"])
            for j, s in enumerate(g["series"]):
                serie = {"name": s["nome"], "categories": [nome_aba, linha + 2, 0, linha + 1 + n, 0],
                         "values": [nome_aba, linha + 2, 1 + j, linha + 1 + n, 1 + j],
                         "data_labels": ({"percentage": True, "num_format": "0%"} if tipo == "doughnut" else
                                         {"value": n <= (5 if g["fmt"] == "brl" else 12),
                                          "num_format": FORMATO_OFFICE.get(g["fmt"], "#,##0.00")})}
                if tipo == "doughnut" or cores is not SERIES:   # uma cor por fatia / por prioridade
                    serie["points"] = [{"fill": {"color": f"#{c}"}} for c in cores[:n]]
                elif tipo == "line":
                    serie["line"] = {"color": f"#{cores[j % len(cores)]}", "width": 2.25}
                    serie["marker"] = {"type": "circle", "size": 6, "fill": {"color": f"#{cores[j % len(cores)]}"}, "border": {"none": True}}
                else:
                    serie["fill"] = {"color": f"#{cores[j % len(cores)]}"}
                grafico.add_series(serie)
            grafico.set_title({"name": g["titulo"], "name_font": {"size": 12, "bold": True, "color": f"#{NAVY}"}})
            grafico.set_legend({"position": "bottom"} if len(g["series"]) > 1 or tipo == "doughnut" else {"none": True})
            if tipo != "doughnut":
                eixo_valor = {"num_format": FORMATO_OFFICE.get(g["fmt"], "#,##0"), "major_gridlines": {"visible": True, "line": {"color": f"#{LINHA}"}}}
                if tipo == "bar":
                    grafico.set_y_axis({"reverse": True}); grafico.set_x_axis(eixo_valor)
                else:
                    grafico.set_y_axis(eixo_valor)
            else:
                grafico.set_hole_size(55)
            grafico.set_size({"width": 620, "height": 320 if n <= 10 else 380})
            aba.insert_chart(linha, 5, grafico)
            linha += max(n + 4, 19 if n <= 10 else 22)

    # ---------- uma aba por tabela
    for b in tabelas:
        aba = wb.add_worksheet(_nome_aba(b["nome"], usados))
        aba.write(0, 0, b["titulo"], f["titulo"])
        if b["nota"]:
            aba.write(1, 0, b["nota"], f["sub"])
        aba.write_row(2, 0, [c["nome"] for c in b["colunas"]], f["cab"])
        larguras = [max(10, len(c["nome"]) + 2) for c in b["colunas"]]
        for i, l in enumerate(b["linhas"]):
            for j, (v, col) in enumerate(zip(l, b["colunas"])):
                valor, fmt = celula(v, col["fmt"])
                if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                    aba.write_number(3 + i, j, valor, num.get(fmt, num["dec2"]))
                    larguras[j] = max(larguras[j], min(len(formatar(valor, fmt)) + 2, 40))
                elif fmt == "data" and valor:
                    aba.write(3 + i, j, formatar(valor, "data"))
                else:
                    aba.write_string(3 + i, j, "" if valor is None else str(valor), f["texto"])
                    larguras[j] = max(larguras[j], min(len(str(valor)) + 2, 60))
        for j, w in enumerate(larguras):
            aba.set_column(j, j, w)
        aba.freeze_panes(3, 1)
        if b["linhas"]:
            aba.autofilter(2, 0, 2 + len(b["linhas"]), len(b["colunas"]) - 1)
    wb.close()
    return memoria.getvalue()
