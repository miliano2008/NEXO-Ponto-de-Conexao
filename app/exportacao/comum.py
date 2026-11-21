"""Cores, formatos de número e utilidades compartilhadas pelos formatos de exportação."""

from nucleo.relatorio import celula, formatar  # noqa: F401  (reexportados para os formatos)

# identidade NEXO (mesmas cores da interface)
NAVY, AZUL, AZUL_CLARO, CINZA, LINHA = "0B1F3A", "1B5FA8", "E7F0FA", "7C8B9E", "E1E7EF"
VERMELHO, AMBAR, VERDE, TINTA = "C2263C", "D99311", "1E7A5A", "16202E"
SERIES = ["1B5FA8", "D99311", "1E7A5A", "C2263C", "6B4FA0", "0F8B8D", "7C8B9E", "B5568D", "4D94DD", "8A6D3B"]
CORES_NIVEL = {"Alta": VERMELHO, "Moderada": AMBAR, "Baixa": AZUL, "Sem indícios": "B8C2CF"}

# formato de número no Excel/Office (os códigos são universais; o Office mostra no idioma do computador)
FORMATO_OFFICE = {"brl": '"R$" #,##0.00', "int": "#,##0", "dec1": "#,##0.0", "dec2": "#,##0.00", "dec3": "0.000",
                  "dec4": "0.0000", "pct": "0.0%", "delta": "+0.0;-0.0;0.0", "data": "dd/mm/yyyy", "txt": "@"}


def cores_do_grafico(bloco):
    """Uma cor por ponto (pizza/prioridade) ou por série."""
    if all(c in CORES_NIVEL for c in bloco["categorias"]) and len(bloco["series"]) == 1:
        return [CORES_NIVEL[c] for c in bloco["categorias"]]
    return SERIES


def blocos(documento, *, incluir_dados=False):
    """(seção, bloco) em ordem; as tabelas completas (so_dados) só entram se incluir_dados."""
    for secao in documento["secoes"]:
        for bloco in secao["blocos"]:
            if bloco["tipo"] == "tabela" and bloco["so_dados"] and not incluir_dados:
                continue
            yield secao, bloco


def secoes_visiveis(documento, *, incluir_dados=False):
    """Seções que têm algum bloco no formato (o anexo só aparece no Excel e no CSV)."""
    for secao in documento["secoes"]:
        itens = [b for b in secao["blocos"] if incluir_dados or not (b["tipo"] == "tabela" and b["so_dados"])]
        if itens:
            yield secao["titulo"], itens


def larguras_colunas(bloco, total, medir):
    """Largura de cada coluna de uma tabela (mesma unidade de `total`).

    Cada coluna recebe ao menos a largura da maior palavra (o cabeçalho e códigos como "C016"
    nunca quebram no meio); o que sobra vai para as colunas de texto longo, proporcional ao
    conteúdo. medir(texto, negrito) devolve a largura do texto na unidade de `total`."""
    colunas = bloco["colunas"]
    textos = [[formatar(v, c["fmt"]) for v, c in zip(l, colunas)] for l in bloco["linhas"][:80]]
    minimos = []
    for j, c in enumerate(colunas):
        palavras = [w for t in textos for w in t[j].split()]
        curtas = [t[j] for t in textos if len(t[j]) <= 14]
        minimos.append(max([medir(w, True) for w in c["nome"].split()] + [medir(w, False) for w in palavras + curtas] + [0]))
    sobra = total - sum(minimos)
    if sobra <= 0:
        return [total * m / sum(minimos) for m in minimos]
    extra = [max(0, max([len(c["nome"])] + [len(t[j]) for t in textos]) - 14) for j, c in enumerate(colunas)]
    if not sum(extra):
        extra = [1] * len(colunas)
    return [m + sobra * x / sum(extra) for m, x in zip(minimos, extra)]
