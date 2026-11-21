"""NEXO — exportação dos relatórios (Fase 5): o mesmo documento (nucleo/relatorio.py) em
PDF, Excel, CSV, Word e PowerPoint, com gráficos nativos de cada formato.

Cada formato fica num módulo próprio e só é importado quando alguém exporta naquele
formato: as bibliotecas (reportlab, XlsxWriter, python-docx, python-pptx) não pesam na
abertura do NEXO nem nas outras telas.
"""
import importlib

FORMATOS = {
    "pdf": ("pdf", "application/pdf", "pdf"),
    "xlsx": ("excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "csv": ("csv", "application/zip", "zip"),
    "docx": ("word", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "pptx": ("powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx"),
}
NOMES = {"pdf": "PDF", "xlsx": "Excel", "csv": "CSV", "docx": "Word", "pptx": "PowerPoint"}


def gerar(documento, formato):
    """Retorna (bytes, tipo MIME, nome do arquivo). ValueError se o formato não existir."""
    if formato not in FORMATOS:
        raise ValueError("Formato inválido: use pdf, xlsx, csv, docx ou pptx.")
    modulo, mime, extensao = FORMATOS[formato]
    try:
        gerador = importlib.import_module(f"app.exportacao.{modulo}")
    except ImportError as erro:
        raise RuntimeError(f"Biblioteca do formato {NOMES[formato]} não instalada ({erro.name}). "
                           "Feche o NEXO e abra de novo pelo iniciar.bat (ele instala o que faltar).") from erro
    return gerador.gerar(documento), mime, f"{documento['arquivo']}.{extensao}"
