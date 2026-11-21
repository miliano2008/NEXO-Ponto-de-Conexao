"""PowerPoint (.pptx, 16:9) para apresentação: capa, um slide por gráfico (gráfico NATIVO do
PowerPoint, editável), indicadores, tabelas divididas em slides de até 10 linhas e conclusões.
O texto de apoio de cada seção vai para as anotações do apresentador."""
import io

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Cm, Emu, Pt

from app.exportacao.comum import AMBAR, AZUL, AZUL_CLARO, CINZA, NAVY, TINTA, formatar, larguras_colunas, secoes_visiveis
from app.exportacao.graficos_office import dados, estilizar

LARGURA, ALTURA = Cm(33.867), Cm(19.05)
MARGEM = Cm(1.4)
LINHAS_POR_SLIDE = 10
MAX_SLIDES_TABELA = 2   # numa apresentação, tabelas longas mostram o início; a lista completa vai no Excel/CSV


def _rgb(h):
    return RGBColor.from_string(h)


def _caixa(slide, x, y, w, h, texto="", *, tamanho=14, cor=TINTA, negrito=False, alinhar=PP_ALIGN.LEFT, fundo=None):
    forma = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h) if fundo else slide.shapes.add_textbox(x, y, w, h)
    if fundo:
        forma.fill.solid(); forma.fill.fore_color.rgb = _rgb(fundo)
        forma.line.fill.background()
        forma.shadow.inherit = False
    tf = forma.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Cm(0.3)
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    p.alignment = alinhar
    r = p.add_run()
    r.text = texto
    r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(tamanho), negrito, _rgb(cor), "Calibri"
    return forma


class _Deck:
    def __init__(self, documento):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = LARGURA, ALTURA
        self.vazio = self.prs.slide_layouts[6]
        self.doc = documento
        origem = [v for r, v in documento["identificacao"] if r in ("Análise", "Assinatura")]
        self.rodape = " · ".join([documento["titulo"], *origem])

    def slide(self, secao, titulo, notas=""):
        s = self.prs.slides.add_slide(self.vazio)
        faixa = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, LARGURA, Cm(0.35))
        faixa.fill.solid(); faixa.fill.fore_color.rgb = _rgb(NAVY); faixa.line.fill.background()
        _caixa(s, MARGEM, Cm(0.7), LARGURA - 2 * MARGEM, Cm(0.8), secao.upper(), tamanho=11, cor=AZUL, negrito=True)
        _caixa(s, MARGEM, Cm(1.35), LARGURA - 2 * MARGEM, Cm(1.4), titulo, tamanho=24, cor=NAVY, negrito=True)
        n = len(self.prs.slides)
        _caixa(s, MARGEM, ALTURA - Cm(1.0), LARGURA - 2 * MARGEM - Cm(2), Cm(0.7), self.rodape, tamanho=9, cor=CINZA)
        _caixa(s, LARGURA - MARGEM - Cm(2), ALTURA - Cm(1.0), Cm(2), Cm(0.7), str(n), tamanho=9, cor=CINZA, alinhar=PP_ALIGN.RIGHT)
        if notas:
            s.notes_slide.notes_text_frame.text = notas
        return s

    # ---------- capa
    def capa(self):
        s = self.prs.slides.add_slide(self.vazio)
        fundo = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, LARGURA, ALTURA)
        fundo.fill.solid(); fundo.fill.fore_color.rgb = _rgb(NAVY); fundo.line.fill.background()
        detalhe = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Cm(9.2), LARGURA, Cm(0.18))
        detalhe.fill.solid(); detalhe.fill.fore_color.rgb = _rgb(AMBAR); detalhe.line.fill.background()
        _caixa(s, Cm(2), Cm(3.6), LARGURA - Cm(4), Cm(2.4), self.doc["titulo"], tamanho=38, cor="FFFFFF", negrito=True)
        _caixa(s, Cm(2), Cm(6.4), LARGURA - Cm(4), Cm(1.5), self.doc["subtitulo"], tamanho=18, cor="C3D4E8")
        y = Cm(10.2)
        for rotulo, valor in self.doc["identificacao"]:
            if rotulo == "Relatório":
                continue
            _caixa(s, Cm(2), y, Cm(6), Cm(0.8), rotulo, tamanho=12, cor="7FA4CE", negrito=True)
            _caixa(s, Cm(8), y, LARGURA - Cm(10), Cm(0.8), valor, tamanho=12, cor="FFFFFF")
            y += Cm(0.85)
        s.notes_slide.notes_text_frame.text = self.doc["aviso"]

    # ---------- blocos
    def indicadores(self, secao, bloco, notas):
        s = self.slide(secao, "Indicadores", notas)
        itens = bloco["itens"]
        colunas = 3
        w = (LARGURA - 2 * MARGEM - Cm(1.0) * (colunas - 1)) / colunas
        for i, it in enumerate(itens):
            x = MARGEM + (i % colunas) * (w + Cm(1.0))
            y = Cm(3.8) + (i // colunas) * Cm(5.4)
            card = _caixa(s, Emu(int(x)), y, Emu(int(w)), Cm(4.6), it["valor"], tamanho=34, cor=NAVY, negrito=True, fundo=AZUL_CLARO)
            p = card.text_frame.add_paragraph()
            r = p.add_run()
            r.text = it["rotulo"] + (f"\n{it['nota']}" if it["nota"] else "")
            r.font.size, r.font.color.rgb = Pt(14), _rgb("4A5A6E")
            card.text_frame.margin_top = Cm(0.6)

    def grafico(self, secao, bloco, notas):
        s = self.slide(secao, bloco["titulo"], notas)
        tipo, cd = dados(bloco)
        largura = LARGURA - 2 * MARGEM if bloco["forma"] != "pizza" else Cm(22)
        x = MARGEM if bloco["forma"] != "pizza" else (LARGURA - largura) / 2
        quadro = s.shapes.add_chart(tipo, Emu(int(x)), Cm(3.4), Emu(int(largura)), ALTURA - Cm(5.0), cd)
        estilizar(quadro.chart, bloco, com_titulo=False, fonte=13)
        if bloco["nota"]:
            _caixa(s, MARGEM, ALTURA - Cm(1.7), LARGURA - 2 * MARGEM, Cm(0.7), bloco["nota"], tamanho=10, cor=CINZA)

    def tabela(self, secao, bloco, notas):
        colunas, linhas = bloco["colunas"], bloco["linhas"]
        if not linhas:
            s = self.slide(secao, bloco["titulo"], notas)
            _caixa(s, MARGEM, Cm(4), LARGURA - 2 * MARGEM, Cm(1), "Nenhum registro.", tamanho=16)
            return
        numericas = [c["fmt"] not in ("txt", "data") for c in colunas]
        total = LARGURA - 2 * MARGEM
        larguras = larguras_colunas(bloco, total, lambda txt, negrito: Pt(12).emu * (0.6 if negrito else 0.55) * len(txt) + Cm(0.6))
        partes = [linhas[i:i + LINHAS_POR_SLIDE] for i in range(0, len(linhas), LINHAS_POR_SLIDE)]
        cortadas = len(partes) > MAX_SLIDES_TABELA
        partes = partes[:MAX_SLIDES_TABELA]
        if cortadas:
            mostradas = sum(len(p) for p in partes)
            bloco = {**bloco, "nota": f"Mostrando {mostradas} de {len(linhas)} linhas. A lista completa está no relatório em Excel, CSV, PDF ou Word."}
        for k, parte in enumerate(partes):
            titulo = bloco["titulo"] + (f" ({k + 1}/{len(partes)})" if len(partes) > 1 else "")
            s = self.slide(secao, titulo, notas if k == 0 else "")
            altura = Cm(1.1) * (len(parte) + 1)
            t = s.shapes.add_table(len(parte) + 1, len(colunas), MARGEM, Cm(3.6), Emu(int(total)), Emu(int(altura))).table
            for j, w in enumerate(larguras):
                t.columns[j].width = Emu(int(w))
            for j, c in enumerate(colunas):
                cel = t.cell(0, j)
                cel.fill.solid(); cel.fill.fore_color.rgb = _rgb(NAVY)
                cel.text = c["nome"]
                p = cel.text_frame.paragraphs[0]
                p.alignment = PP_ALIGN.RIGHT if numericas[j] else PP_ALIGN.LEFT
                p.runs[0].font.size, p.runs[0].font.bold, p.runs[0].font.color.rgb = Pt(12), True, _rgb("FFFFFF")
            for i, linha in enumerate(parte, start=1):
                for j, (v, c) in enumerate(zip(linha, colunas)):
                    cel = t.cell(i, j)
                    cel.fill.solid(); cel.fill.fore_color.rgb = _rgb("F6F8FB" if i % 2 == 0 else "FFFFFF")
                    cel.text = formatar(v, c["fmt"])
                    p = cel.text_frame.paragraphs[0]
                    p.alignment = PP_ALIGN.RIGHT if numericas[j] else PP_ALIGN.LEFT
                    p.runs[0].font.size, p.runs[0].font.color.rgb = Pt(12), _rgb(TINTA)
                    cel.margin_top = cel.margin_bottom = Cm(0.08)
            if bloco["nota"] and k == len(partes) - 1:
                _caixa(s, MARGEM, ALTURA - Cm(1.7), LARGURA - 2 * MARGEM, Cm(0.7), bloco["nota"], tamanho=10, cor=CINZA)

    def textos(self, secao, blocos):
        s = self.slide(secao, secao.split(". ", 1)[-1])
        caixa = s.shapes.add_textbox(MARGEM, Cm(3.6), LARGURA - 2 * MARGEM, ALTURA - Cm(5.2))
        tf = caixa.text_frame
        tf.word_wrap = True
        primeiro = True
        for b in blocos:
            itens = b["itens"] if b["tipo"] == "lista" else [b["texto"]]
            for texto in itens:
                p = tf.paragraphs[0] if primeiro else tf.add_paragraph()
                primeiro = False
                r = p.add_run()
                r.text = ("•  " if b["tipo"] == "lista" else "") + texto
                aviso = b["tipo"] == "aviso"
                r.font.size = Pt(13 if not aviso else 11)
                r.font.color.rgb = _rgb("8A5A00" if aviso else TINTA)
                r.font.italic = aviso
                p.space_after = Pt(7)

    def salvar(self):
        memoria = io.BytesIO()
        self.prs.save(memoria)
        return memoria.getvalue()


def gerar(documento):
    deck = _Deck(documento)
    deck.capa()
    for titulo, itens in secoes_visiveis(documento):
        textos = [b for b in itens if b["tipo"] in ("paragrafo", "aviso", "lista")]
        visuais = [b for b in itens if b["tipo"] in ("indicadores", "grafico", "tabela")]
        notas = "\n".join(b["texto"] if b["tipo"] != "lista" else "\n".join(b["itens"]) for b in textos)
        if not visuais or any(b["tipo"] == "lista" for b in textos):
            deck.textos(titulo, textos)   # conclusões: o texto é o conteúdo do slide
            notas = ""
        for b in visuais:
            getattr(deck, b["tipo"])(titulo, b, notas)
            notas = ""
    return deck.salvar()
