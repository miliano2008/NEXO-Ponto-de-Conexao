"""Gráficos NATIVOS do Office (DrawingML), usados pelo Word e pelo PowerPoint.

O python-pptx monta o XML do gráfico e a planilha com os dados; no PowerPoint ele é inserido
direto; no Word o mesmo XML vira uma parte "chart" do documento (word.py). Nos dois casos o
gráfico é editável: clique com o botão direito → Editar dados.
"""
from lxml import etree
from pptx.chart.chart import Chart
from pptx.chart.data import CategoryChartData
from pptx.chart.xmlwriter import ChartXmlWriter
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.oxml import parse_xml
from pptx.util import Pt

from app.exportacao.comum import FORMATO_OFFICE, LINHA, NAVY, SERIES, cores_do_grafico

TIPO = {"colunas": XL_CHART_TYPE.COLUMN_CLUSTERED, "colunas_agrupadas": XL_CHART_TYPE.COLUMN_CLUSTERED,
        "barras": XL_CHART_TYPE.BAR_CLUSTERED, "pizza": XL_CHART_TYPE.DOUGHNUT, "linha": XL_CHART_TYPE.LINE_MARKERS}
NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"


def dados(bloco):
    """(tipo do gráfico, CategoryChartData). Barras horizontais: invertidas para ler de cima para baixo."""
    cd = CategoryChartData(number_format=FORMATO_OFFICE.get(bloco["fmt"], "General"))
    inverter = bloco["forma"] == "barras"
    cd.categories = list(reversed(bloco["categorias"])) if inverter else bloco["categorias"]
    for s in bloco["series"]:
        cd.add_series(s["nome"], list(reversed(s["valores"])) if inverter else s["valores"])
    return TIPO[bloco["forma"]], cd


def _rgb(h):
    return RGBColor.from_string(h)


def estilizar(chart, bloco, *, com_titulo=True, fonte=9):
    """Cores NEXO, rótulos de dados, eixos e legenda num gráfico do python-pptx."""
    forma, n = bloco["forma"], len(bloco["categorias"])
    cores = cores_do_grafico(bloco)
    if forma == "barras" and cores is not SERIES:
        cores = list(reversed(cores))
    chart.font.size, chart.font.name = Pt(fonte), "Calibri"
    chart.has_title = com_titulo
    if com_titulo:
        chart.chart_title.text_frame.text = bloco["titulo"]
        titulo = chart.chart_title.text_frame.paragraphs[0].runs[0].font
        titulo.size, titulo.bold, titulo.color.rgb = Pt(fonte + 3), True, _rgb(NAVY)
    plot = chart.plots[0]
    multiplas = len(bloco["series"]) > 1
    chart.has_legend = multiplas or forma == "pizza"
    if chart.has_legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM if forma != "pizza" else XL_LEGEND_POSITION.RIGHT
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(fonte)
    if forma != "pizza":
        plot.vary_by_categories = False
    for j, serie in enumerate(plot.series):
        cor = _rgb(SERIES[j % len(SERIES)])
        if forma == "linha":
            serie.format.line.color.rgb, serie.format.line.width = cor, Pt(2.25)
            serie.smooth = False
            serie.marker.format.fill.solid(); serie.marker.format.fill.fore_color.rgb = cor
            serie.marker.format.line.color.rgb = cor
        elif forma == "pizza" or cores is not SERIES:
            for i in range(n):
                ponto = serie.points[i]
                ponto.format.fill.solid(); ponto.format.fill.fore_color.rgb = _rgb(cores[i % len(cores)])
                if forma == "pizza":
                    ponto.format.line.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        else:
            serie.format.fill.solid(); serie.format.fill.fore_color.rgb = cor
    if forma in ("colunas", "colunas_agrupadas", "barras"):
        plot.gap_width = 60 if not multiplas else 80
        if multiplas:
            plot.overlap = -10
    # rótulos de dados: poucos pontos (em R$, só até 5 para não poluir); na rosca, a porcentagem
    if forma == "pizza":
        plot.has_data_labels = True
        rotulos = plot.data_labels
        rotulos.show_percentage, rotulos.show_value, rotulos.show_category_name = True, False, False
        rotulos.number_format, rotulos.number_format_is_linked = "0%", False
        rotulos.font.size, rotulos.font.bold = Pt(fonte), True
        rotulos.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        buraco = plot._element.find(f"{{{NS_C}}}holeSize")
        if buraco is not None:
            buraco.set("val", "55")
    elif n <= (5 if bloco["fmt"] == "brl" else 12):
        plot.has_data_labels = True
        rotulos = plot.data_labels
        rotulos.number_format = FORMATO_OFFICE.get(bloco["fmt"], "General")
        rotulos.number_format_is_linked = False
        rotulos.font.size = Pt(fonte - 1)
        rotulos.position = XL_LABEL_POSITION.OUTSIDE_END if forma != "linha" else XL_LABEL_POSITION.ABOVE
    if forma != "pizza":
        eixo = chart.value_axis
        eixo.has_major_gridlines = True
        eixo.major_gridlines.format.line.color.rgb = _rgb(LINHA)
        eixo.tick_labels.number_format = FORMATO_OFFICE.get(bloco["fmt"], "General")
        eixo.tick_labels.number_format_is_linked = False
        eixo.tick_labels.font.size = Pt(fonte - 1)
        eixo.format.line.fill.background()
        cat = chart.category_axis
        cat.tick_labels.font.size = Pt(fonte - 1)
        cat.format.line.color.rgb = _rgb(LINHA)
        if any(v < 0 for s in bloco["series"] for v in s["valores"]):
            from pptx.enum.chart import XL_TICK_LABEL_POSITION
            cat.tick_label_position = XL_TICK_LABEL_POSITION.LOW


def xml_para_word(bloco, rid_planilha):
    """(XML do gráfico pronto para uma parte do Word, planilha .xlsx com os dados)."""
    tipo, cd = dados(bloco)
    espaco = parse_xml(ChartXmlWriter(tipo, cd).xml.encode("utf-8"))
    estilizar(Chart(espaco, None), bloco)
    externo = etree.SubElement(espaco, f"{{{NS_C}}}externalData")
    externo.set("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", rid_planilha)
    etree.SubElement(externo, f"{{{NS_C}}}autoUpdate").set("val", "0")
    return etree.tostring(espaco, xml_declaration=True, encoding="UTF-8", standalone=True), cd.xlsx_blob
