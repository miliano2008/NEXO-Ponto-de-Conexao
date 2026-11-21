"""Word (.docx): documento editável com títulos navegáveis (painel de navegação), tabelas
formatadas e gráficos NATIVOS do Word (editáveis: botão direito → Editar dados)."""
import io
from xml.sax.saxutils import quoteattr

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor

from app.exportacao.comum import AZUL, AZUL_CLARO, CINZA, NAVY, formatar, larguras_colunas, secoes_visiveis
from app.exportacao.graficos_office import xml_para_word

CT_GRAFICO = "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"
CT_PLANILHA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
LARGURA_CM = 17.0


def _cor(h):
    return RGBColor.from_string(h)


def _sombrear(celula, cor):
    celula._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{cor}"/>'))


def _texto_celula(celula, texto, *, negrito=False, cor=None, tamanho=8.5, direita=False):
    p = celula.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    if direita:
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run(texto)
    r.font.size, r.bold = Pt(tamanho), negrito
    if cor:
        r.font.color.rgb = _cor(cor)


def _estilos(doc):
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    for nome, tamanho, cor in (("Title", 24, NAVY), ("Heading 1", 15, NAVY), ("Heading 2", 11.5, AZUL)):
        estilo = doc.styles[nome]
        estilo.font.name, estilo.font.size, estilo.font.color.rgb, estilo.font.bold = "Calibri", Pt(tamanho), _cor(cor), True


def _campo_pagina(paragrafo):
    """Número da página (campo PAGE do Word)."""
    for parte in (f'<w:r {nsdecls("w")}><w:fldChar w:fldCharType="begin"/></w:r>',
                  f'<w:r {nsdecls("w")}><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>',
                  f'<w:r {nsdecls("w")}><w:fldChar w:fldCharType="end"/></w:r>'):
        paragrafo._p.append(parse_xml(parte))


class _Graficos:
    """Insere gráficos nativos: uma parte chart + a planilha embutida com os dados."""

    def __init__(self, doc):
        self.doc, self.n = doc, 0

    def inserir(self, bloco):
        self.n += 1
        pacote = self.doc.part.package
        parte = Part(PackURI(f"/word/charts/chart{self.n}.xml"), CT_GRAFICO, b"", pacote)
        # a planilha precisa existir antes para o XML do gráfico citar o identificador dela
        planilha_parte = Part(PackURI(f"/word/embeddings/Dados_grafico_{self.n}.xlsx"), CT_PLANILHA, b"", pacote)
        planilha_rid = parte.relate_to(planilha_parte, RT.PACKAGE)
        xml, planilha = xml_para_word(bloco, planilha_rid)
        parte._blob, planilha_parte._blob = xml, planilha
        rid = self.doc.part.relate_to(parte, RT.CHART)
        altura = Cm(7.5 if bloco["forma"] != "barras" else max(6.5, 0.75 * len(bloco["categorias"]) + 2.5))
        largura = Cm(LARGURA_CM if bloco["forma"] != "pizza" else 13)
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        inline = parse_xml(
            f'<wp:inline distT="0" distB="0" distL="0" distR="0" {nsdecls("wp", "a", "r")}>'
            f'<wp:extent cx="{int(largura)}" cy="{int(altura)}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
            f'<wp:docPr id="{1000 + self.n}" name="Gráfico {self.n}" descr={quoteattr(bloco["titulo"])}/><wp:cNvGraphicFramePr/>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
            f'<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" r:id="{rid}"/>'
            f'</a:graphicData></a:graphic></wp:inline>')
        desenho = parse_xml(f'<w:drawing {nsdecls("w")}/>')
        desenho.append(inline)
        p.add_run()._r.append(desenho)


def _tabela(doc, bloco):
    colunas = bloco["colunas"]
    numericas = [c["fmt"] not in ("txt", "data") for c in colunas]
    t = doc.add_table(rows=1, cols=len(colunas))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = doc.styles["Table Grid"]
    cab = t.rows[0]
    cab._tr.get_or_add_trPr().append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))   # repete em cada página
    for j, c in enumerate(colunas):
        _sombrear(cab.cells[j], NAVY)
        _texto_celula(cab.cells[j], c["nome"], negrito=True, cor="FFFFFF", direita=numericas[j])
    for i, linha in enumerate(bloco["linhas"]):
        celulas = t.add_row().cells
        for j, (v, c) in enumerate(zip(linha, colunas)):
            _texto_celula(celulas[j], formatar(v, c["fmt"]), direita=numericas[j])
            if i % 2:
                _sombrear(celulas[j], "F6F8FB")
    # larguras pelo conteúdo (cm): ~0,19 cm por caractere em 8,5 pt, mais as margens da célula
    larguras = larguras_colunas(bloco, LARGURA_CM, lambda txt, negrito: len(txt) * (0.2 if negrito else 0.185) + 0.3)
    t.autofit = False
    t._tbl.tblPr.append(parse_xml(f'<w:tblLayout {nsdecls("w")} w:type="fixed"/>'))
    grade = t._tbl.tblGrid
    for j, col in enumerate(grade.findall(qn("w:gridCol"))):
        col.set(qn("w:w"), str(int(larguras[j] * 567)))
    for linha in t.rows:
        for j, celula in enumerate(linha.cells):
            celula.width = Cm(larguras[j])
    # bordas claras
    bordas = parse_xml(f'<w:tblBorders {nsdecls("w")}>' + "".join(
        f'<w:{lado} w:val="single" w:sz="4" w:space="0" w:color="E1E7EF"/>'
        for lado in ("top", "left", "bottom", "right", "insideH", "insideV")) + "</w:tblBorders>")
    t._tbl.tblPr.append(bordas)
    return t


def gerar(documento):
    doc = Document()
    secao = doc.sections[0]
    secao.left_margin = secao.right_margin = Cm(2)
    secao.top_margin, secao.bottom_margin = Cm(1.8), Cm(1.8)
    _estilos(doc)
    doc.core_properties.title = documento["titulo"]
    doc.core_properties.subject = documento["subtitulo"]
    doc.core_properties.author = "NEXO"
    doc.core_properties.comments = documento["aviso"]

    rodape = secao.footer.paragraphs[0]
    origem = [v for r, v in documento["identificacao"] if r in ("Análise", "Assinatura")]
    r = rodape.add_run(" · ".join([documento["titulo"], *origem]) + "  ·  Página ")
    r.font.size, r.font.color.rgb = Pt(8), _cor(CINZA)
    _campo_pagina(rodape)

    doc.add_paragraph(documento["titulo"], style="Title")
    sub = doc.add_paragraph(documento["subtitulo"])
    sub.runs[0].font.color.rgb, sub.runs[0].font.size = _cor("4A5A6E"), Pt(12)

    ident = doc.add_table(rows=0, cols=2)
    for rotulo, valor in documento["identificacao"]:
        c = ident.add_row().cells
        _texto_celula(c[0], rotulo, negrito=True, cor="4A5A6E", tamanho=9.5)
        _texto_celula(c[1], valor, tamanho=9.5)
    for linha in ident.rows:
        linha.cells[0].width, linha.cells[1].width = Cm(4.5), Cm(12.5)

    def aviso(texto):
        t = doc.add_table(rows=1, cols=1)
        _sombrear(t.cell(0, 0), "FCF3E1")
        _texto_celula(t.cell(0, 0), texto, cor="6B4A00", tamanho=9)
        doc.add_paragraph()

    doc.add_paragraph()
    aviso(documento["aviso"])
    graficos = _Graficos(doc)

    for titulo, itens in secoes_visiveis(documento):
        doc.add_heading(titulo, level=1)
        for b in itens:
            if b["tipo"] == "paragrafo":
                doc.add_paragraph(b["texto"])
            elif b["tipo"] == "aviso":
                aviso(b["texto"])
            elif b["tipo"] == "lista":
                for item in b["itens"]:
                    doc.add_paragraph(item, style="List Bullet")
            elif b["tipo"] == "indicadores":
                t = doc.add_table(rows=0, cols=3)
                t.alignment = WD_TABLE_ALIGNMENT.CENTER
                itens_k = b["itens"]
                for i in range(0, len(itens_k), 3):
                    celulas = t.add_row().cells
                    for j, it in enumerate(itens_k[i:i + 3]):
                        _sombrear(celulas[j], AZUL_CLARO)
                        _texto_celula(celulas[j], it["valor"], negrito=True, cor=NAVY, tamanho=15)
                        p = celulas[j].add_paragraph()
                        r = p.add_run(it["rotulo"] + (f" · {it['nota']}" if it["nota"] else ""))
                        r.font.size, r.font.color.rgb = Pt(8.5), _cor("4A5A6E")
                doc.add_paragraph()
            elif b["tipo"] == "tabela":
                doc.add_heading(b["titulo"], level=2)
                if b["linhas"]:
                    _tabela(doc, b)
                else:
                    doc.add_paragraph("Nenhum registro.")
                if b["nota"]:
                    nota = doc.add_paragraph(b["nota"])
                    nota.runs[0].font.size, nota.runs[0].font.color.rgb = Pt(8.5), _cor(CINZA)
                doc.add_paragraph()
            elif b["tipo"] == "grafico":
                graficos.inserir(b)
                if b["nota"]:
                    doc.add_paragraph(b["nota"])

    memoria = io.BytesIO()
    doc.save(memoria)
    return memoria.getvalue()
