"""PDF (A4) com reportlab: capa com a identificação, seções numeradas, indicadores, tabelas e
gráficos VETORIAIS desenhados pelo próprio reportlab (nítidos em qualquer zoom; não são imagens).
Rodapé com a análise de origem e o número da página em todas as folhas."""
import io
import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.doughnut import Doughnut
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from app.exportacao.comum import AMBAR, AZUL, AZUL_CLARO, CINZA, LINHA, NAVY, SERIES, TINTA, cores_do_grafico, formatar, larguras_colunas, secoes_visiveis

C = lambda h: colors.HexColor(f"#{h}")  # noqa: E731

# ---------------------------------------------------------------- fonte com acentos e símbolos (→ ≥ λ)
_CANDIDATAS = [  # (normal, negrito): Windows, Linux, macOS
    ("segoeui.ttf", "segoeuib.ttf"), ("arial.ttf", "arialbd.ttf"),
    ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"), ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"),
    ("Arial.ttf", "Arial Bold.ttf"),
]
_PASTAS = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts", Path("/usr/share/fonts/truetype/dejavu"),
           Path("/usr/share/fonts/truetype/liberation"), Path("/usr/share/fonts/TTF"), Path("/Library/Fonts"),
           Path("/System/Library/Fonts/Supplemental")]
_TROCAS = {"→": "->", "λ": "l", "✓": "ok"}   # só se nenhuma fonte do sistema for encontrada
FONTE, NEGRITO, SUBSTITUIR = "NexoSans", "NexoSans-Bold", False


def _registrar_fonte():
    global SUBSTITUIR
    if FONTE in pdfmetrics.getRegisteredFontNames():
        return
    for normal, negrito in _CANDIDATAS:
        for pasta in _PASTAS:
            if (pasta / normal).is_file() and (pasta / negrito).is_file():
                try:
                    pdfmetrics.registerFont(TTFont(FONTE, str(pasta / normal)))
                    pdfmetrics.registerFont(TTFont(NEGRITO, str(pasta / negrito)))
                    pdfmetrics.registerFontFamily(FONTE, normal=FONTE, bold=NEGRITO, italic=FONTE, boldItalic=NEGRITO)
                    return
                except Exception:  # noqa: BLE001 — fonte corrompida: tenta a próxima
                    continue
    # reserva: Vera, que vem com o reportlab (tem acentos, mas não → nem λ)
    import reportlab
    pasta = Path(reportlab.__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont(FONTE, str(pasta / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont(NEGRITO, str(pasta / "VeraBd.ttf")))
    pdfmetrics.registerFontFamily(FONTE, normal=FONTE, bold=NEGRITO, italic=FONTE, boldItalic=NEGRITO)
    SUBSTITUIR = True


def _t(texto):
    texto = str(texto)
    if SUBSTITUIR:
        for a, b in _TROCAS.items():
            texto = texto.replace(a, b)
    return texto


def _p(texto, estilo):
    return Paragraph(escape(_t(texto)), estilo)


# ---------------------------------------------------------------- estilos
def _estilos():
    base = dict(fontName=FONTE, textColor=C(TINTA), leading=13, fontSize=9.5, alignment=TA_LEFT)
    return {
        "titulo": ParagraphStyle("titulo", **{**base, "fontName": NEGRITO, "fontSize": 22, "leading": 27, "textColor": colors.white}),
        "subtitulo": ParagraphStyle("sub", **{**base, "fontSize": 11, "leading": 15, "textColor": C("C3D4E8")}),
        "h1": ParagraphStyle("h1", **{**base, "fontName": NEGRITO, "fontSize": 14, "leading": 18, "textColor": C(NAVY),
                                      "spaceBefore": 14, "spaceAfter": 6}),
        "h2": ParagraphStyle("h2", **{**base, "fontName": NEGRITO, "fontSize": 10.5, "leading": 14, "textColor": C(AZUL),
                                      "spaceBefore": 8, "spaceAfter": 4}),
        "texto": ParagraphStyle("texto", **{**base, "spaceAfter": 6}),
        "celula": ParagraphStyle("celula", **{**base, "fontSize": 8, "leading": 10}),
        "celula_num": ParagraphStyle("celula_num", **{**base, "fontSize": 8, "leading": 10, "alignment": 2}),
        "cab": ParagraphStyle("cab", **{**base, "fontName": NEGRITO, "fontSize": 8, "leading": 10, "textColor": colors.white}),
        "kpi_v": ParagraphStyle("kpi_v", **{**base, "fontName": NEGRITO, "fontSize": 15, "leading": 18, "textColor": C(NAVY)}),
        "kpi_r": ParagraphStyle("kpi_r", **{**base, "fontSize": 8, "leading": 10, "textColor": C("4A5A6E")}),
        "aviso": ParagraphStyle("aviso", **{**base, "fontSize": 8.5, "leading": 11.5, "textColor": C("6B4A00")}),
        "rotulo": ParagraphStyle("rotulo", **{**base, "fontName": NEGRITO, "fontSize": 8.5, "textColor": C("4A5A6E")}),
        "nota": ParagraphStyle("nota", **{**base, "fontSize": 7.5, "leading": 10, "textColor": C(CINZA)}),
    }


LARGURA = A4[0] - 36 * mm


# ---------------------------------------------------------------- blocos
def _indicadores(itens, e):
    cards = [[_p(it["valor"], e["kpi_v"]), _p(it["rotulo"] + (f" · {it['nota']}" if it["nota"] else ""), e["kpi_r"])] for it in itens]
    linhas = []
    for i in range(0, len(cards), 3):
        grupo = cards[i:i + 3] + [["", ""]] * (3 - len(cards[i:i + 3]))
        linhas.append([Table([[c[0]], [c[1]]], colWidths=[LARGURA / 3 - 8]) if c[0] else "" for c in grupo])
    t = Table(linhas, colWidths=[LARGURA / 3] * 3)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), C(AZUL_CLARO)), ("LINEBELOW", (0, 0), (-1, -2), 4, colors.white),
                           ("LINEAFTER", (0, 0), (-2, -1), 4, colors.white), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def _tabela(bloco, e):
    colunas = bloco["colunas"]
    numericas = [c["fmt"] not in ("txt", "data") for c in colunas]
    textos = [[formatar(v, c["fmt"]) for v, c in zip(l, colunas)] for l in bloco["linhas"]]
    larguras = larguras_colunas(bloco, LARGURA,
                                lambda txt, negrito: pdfmetrics.stringWidth(_t(txt), NEGRITO if negrito else FONTE, 8) + 9)
    dados = [[_p(c["nome"], e["cab"]) for c in colunas]]
    dados += [[_p(t, e["celula_num"] if numericas[j] else e["celula"]) for j, t in enumerate(l)] for l in textos]
    t = Table(dados, colWidths=larguras, repeatRows=1)
    estilo = [("BACKGROUND", (0, 0), (-1, 0), C(NAVY)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("LINEBELOW", (0, 1), (-1, -1), 0.4, C(LINHA)), ("TOPPADDING", (0, 0), (-1, -1), 3.5),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    estilo += [("BACKGROUND", (0, i), (-1, i), C("F6F8FB")) for i in range(2, len(dados), 2)]
    t.setStyle(TableStyle(estilo))
    return t


def _formatador(fmt):
    def f(v):
        if fmt == "brl":
            return _t(formatar(v, "brl")) if abs(v) < 1000 else f"R$ {formatar(v / 1000, 'dec0')} mil"
        return _t(formatar(v, fmt))
    return f


def _grafico(bloco, e):
    forma, n = bloco["forma"], len(bloco["categorias"])
    cores = cores_do_grafico(bloco)
    fmt = _formatador(bloco["fmt"])
    altura = 190 if forma != "barras" else max(150, 22 * n + 40)
    d = Drawing(LARGURA, altura + 26)
    d.add(String(0, altura + 12, _t(bloco["titulo"]), fontName=NEGRITO, fontSize=10.5, fillColor=C(NAVY)))
    if forma == "pizza":
        g = Doughnut()
        g.x, g.y, g.width, g.height = 30, 10, altura - 20, altura - 20
        g.data = bloco["series"][0]["valores"]
        g.innerRadiusFraction = 0.55
        g.strokeColor, g.strokeWidth = colors.white, 1.5
        total = sum(g.data) or 1
        for i in range(n):
            g.slices[i].fillColor = C(cores[i % len(cores)])
        g.labels = [f"{round(v / total * 100)}%" if v else "" for v in g.data]
        g.slices.fontName, g.slices.fontSize = FONTE, 8
        d.add(g)
        leg = Legend()
        leg.x, leg.y, leg.alignment, leg.columnMaximum = altura + 60, altura - 40, "right", n
        leg.fontName, leg.fontSize, leg.dx, leg.dy, leg.deltay = FONTE, 9.5, 9, 9, 18
        leg.colorNamePairs = [(C(cores[i % len(cores)]), _t(f"{c}: {formatar(bloco['series'][0]['valores'][i], bloco['fmt'])}"))
                              for i, c in enumerate(bloco["categorias"])]
        d.add(leg)
        return d
    if forma == "linha":
        g = HorizontalLineChart()
        g.joinedLines = 1
    elif forma == "barras":
        g = HorizontalBarChart()
    else:
        g = VerticalBarChart()
    dados = [s["valores"] for s in bloco["series"]]
    categorias = [_t(c) for c in bloco["categorias"]]
    if forma == "barras":   # de cima para baixo, na ordem do relatório
        dados = [list(reversed(v)) for v in dados]
        categorias = list(reversed(categorias))
    esquerda = 110 if forma == "barras" else 62
    g.x, g.y, g.width, g.height = esquerda, 22, LARGURA - esquerda - 12, altura - 40
    g.data = dados
    g.categoryAxis.categoryNames = categorias
    for eixo in (g.categoryAxis, g.valueAxis):
        eixo.labels.fontName, eixo.labels.fontSize, eixo.labels.fillColor = FONTE, 7.5, C("4A5A6E")
        eixo.strokeColor = C(LINHA)
    vmin = min(0, min(min(v) for v in dados))
    vmax = max(max(v) for v in dados) or 1
    g.valueAxis.valueMin = vmin * 1.15 if vmin < 0 else 0
    g.valueAxis.valueMax = vmax * 1.15
    g.valueAxis.labelTextFormat = fmt
    g.valueAxis.visibleGrid, g.valueAxis.gridStrokeColor = 1, C(LINHA)
    if vmin < 0:   # valores negativos: rótulos das categorias na borda, longe das barras
        g.categoryAxis.labelAxisMode = "low"
    if forma != "barras" and n > 8:
        g.categoryAxis.labels.angle, g.categoryAxis.labels.boxAnchor = 30, "ne"
    if forma == "linha":
        for j in range(len(dados)):
            g.lines[j].strokeColor, g.lines[j].strokeWidth = C(SERIES[j % len(SERIES)]), 2
    else:
        g.barSpacing, g.groupSpacing = 2, 6
        for j in range(len(dados)):
            g.bars[j].fillColor, g.bars[j].strokeColor = C(SERIES[j % len(SERIES)]), None
        if cores is not SERIES:
            for i in range(n):
                g.bars[(0, i)].fillColor = C(cores[i % len(cores)])
        if n <= 12 and bloco["fmt"] != "brl" or n <= 6:
            g.barLabelFormat = fmt
            g.barLabels.fontName, g.barLabels.fontSize, g.barLabels.fillColor = FONTE, 7, C("4A5A6E")
            g.barLabels.nudge = 12
    d.add(g)
    if len(dados) > 1:
        leg = Legend()
        leg.x, leg.y, leg.alignment = LARGURA - 120, altura + 14, "right"
        leg.columnMaximum, leg.fontName, leg.fontSize = 1, FONTE, 8
        leg.colorNamePairs = [(C(SERIES[j]), _t(s["nome"])) for j, s in enumerate(bloco["series"])]
        leg.deltax = 50
        d.add(leg)
    return d


def _aviso(texto, e):
    t = Table([[_p(texto, e["aviso"])]], colWidths=[LARGURA])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), C("FCF3E1")), ("LINEBEFORE", (0, 0), (0, -1), 3, C(AMBAR)),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LEFTPADDING", (0, 0), (-1, -1), 9)]))
    return t


# ---------------------------------------------------------------- documento
def gerar(documento):
    _registrar_fonte()
    e = _estilos()
    origem = [v for r, v in documento["identificacao"] if r in ("Análise", "Assinatura")]
    rodape = _t(" · ".join([documento["titulo"], *origem]))

    def capa(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(C(NAVY))
        canvas.rect(0, A4[1] - 62 * mm, A4[0], 62 * mm, stroke=0, fill=1)
        canvas.setFillColor(C(AMBAR))
        canvas.rect(0, A4[1] - 63.5 * mm, A4[0], 1.5 * mm, stroke=0, fill=1)
        pagina(canvas, doc, capa=True)
        canvas.restoreState()

    def pagina(canvas, doc, capa=False):
        canvas.saveState()
        canvas.setFont(FONTE, 7.5)
        canvas.setFillColor(C(CINZA))
        canvas.drawString(18 * mm, 10 * mm, rodape[:120])
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {doc.page}")
        canvas.setStrokeColor(C(LINHA))
        canvas.line(18 * mm, 13.5 * mm, A4[0] - 18 * mm, 13.5 * mm)
        canvas.restoreState()

    historia = [Spacer(1, 2 * mm), _p(documento["titulo"], e["titulo"]), Spacer(1, 2 * mm),
                _p(documento["subtitulo"], e["subtitulo"]), Spacer(1, 26 * mm)]
    ident = Table([[_p(r, e["rotulo"]), _p(v, e["texto"])] for r, v in documento["identificacao"]],
                  colWidths=[42 * mm, LARGURA - 42 * mm])
    ident.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, C(LINHA)), ("TOPPADDING", (0, 0), (-1, -1), 3),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    historia += [_p("Identificação", e["h2"]), ident, Spacer(1, 4 * mm), _aviso(documento["aviso"], e)]

    for titulo, itens in secoes_visiveis(documento):
        cabeca = _p(titulo, e["h1"])
        primeiro = True
        for b in itens:
            if b["tipo"] == "paragrafo":
                f = _p(b["texto"], e["texto"])
            elif b["tipo"] == "aviso":
                f = _aviso(b["texto"], e)
            elif b["tipo"] == "lista":
                f = ListFlowable([ListItem(_p(x, e["texto"]), leftIndent=12, value="•") for x in b["itens"]],
                                 bulletType="bullet", bulletFontName=FONTE, bulletColor=C(AZUL), leftIndent=12)
            elif b["tipo"] == "indicadores":
                f = _indicadores(b["itens"], e)
            elif b["tipo"] == "tabela":
                partes = [_p(b["titulo"], e["h2"]), _tabela(b, e)] if b["linhas"] else [_p(b["titulo"], e["h2"]), _p("Nenhum registro.", e["texto"])]
                if b["nota"]:
                    partes.append(_p(b["nota"], e["nota"]))
                f = partes
            else:
                f = [_grafico(b, e)] + ([_p(b["nota"], e["nota"])] if b["nota"] else [])
            f = f if isinstance(f, list) else [f]
            if primeiro:   # o título da seção nunca fica sozinho no pé da página
                historia.append(KeepTogether([cabeca, *f[:2]]))
                historia += f[2:]
                primeiro = False
            elif b["tipo"] in ("grafico", "indicadores"):
                historia.append(KeepTogether(f))
            else:
                historia += f[:1] if b["tipo"] != "tabela" else [KeepTogether(f[:1] + [Spacer(1, 1)])]
                historia += f[1:]
            historia.append(Spacer(1, 3 * mm))
        if titulo.startswith("1."):
            historia.append(PageBreak())

    memoria = io.BytesIO()
    doc = SimpleDocTemplate(memoria, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
                            title=_t(documento["titulo"]), author="NEXO", subject=_t(documento["subtitulo"]),
                            creator="NEXO — Ponto de Conexão")
    doc.build(historia, onFirstPage=capa, onLaterPages=pagina)
    return memoria.getvalue()


