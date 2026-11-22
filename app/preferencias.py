"""NEXO — preferências de cada usuário (Fase 5): aparência, acessibilidade, grafo e relatórios.

Ficam no banco (tabela preferencias_usuario) e acompanham o usuário em qualquer computador.
Só valores conhecidos são aceitos; o que vier fora da lista é recusado com mensagem clara.
"""

from banco import repositorio

# chave: (padrão, valores aceitos | (mínimo, máximo) para números | bool)
OPCOES = {
    "tema": ("sistema", ("sistema", "claro", "escuro")),
    "texto": ("normal", ("normal", "grande", "maior")),
    "fonte": ("inter", ("inter", "sistema", "legivel")),
    "contraste": (False, bool),
    "menos_animacao": (False, bool),
    "foco_reforcado": (False, bool),
    "grafo_esquema": ("status", ("status", "risco", "com", "papel")),
    "grafo_paleta": ("padrao", ("padrao", "daltonismo")),
    "grafo_rotulos": (True, bool),
    "graficos_valores": (True, bool),
    "alertas_status": (True, bool),
    "limiar_analise": (45, (20, 80)),
    "limiar_alta": (70, (40, 100)),
    "relatorio_formato": ("pdf", ("pdf", "xlsx", "docx", "pptx", "csv")),
}
PADRAO = {k: v[0] for k, v in OPCOES.items()}

NOMES = {"tema": "Tema", "texto": "Tamanho do texto", "fonte": "Fonte", "grafo_esquema": "Cores do grafo",
         "grafo_paleta": "Paleta do grafo", "relatorio_formato": "Formato do relatório",
         "limiar_analise": "Limiar de “em análise”", "limiar_alta": "Limiar de “alta relevância”"}


def validar(novas):
    """Confere as preferências enviadas (parciais). Retorna o dicionário limpo ou lança ValueError."""
    if not isinstance(novas, dict):
        raise ValueError("Preferências inválidas.")
    limpas = {}
    for chave, valor in novas.items():
        if chave not in OPCOES:
            raise ValueError(f"Preferência desconhecida: {chave}.")
        _, aceitos = OPCOES[chave]
        nome = NOMES.get(chave, chave)
        if aceitos is bool:
            if not isinstance(valor, bool):
                raise ValueError(f"{nome}: use verdadeiro ou falso.")
        elif isinstance(aceitos, tuple) and len(aceitos) == 2 and all(isinstance(x, int) for x in aceitos):
            if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor != int(valor):
                raise ValueError(f"{nome}: informe um número inteiro.")
            valor = int(valor)
            if not aceitos[0] <= valor <= aceitos[1]:
                raise ValueError(f"{nome}: use um valor de {aceitos[0]} a {aceitos[1]}.")
        elif valor not in aceitos:
            raise ValueError(f"{nome}: opção inválida.")
        limpas[chave] = valor
    return limpas


def ler(usuario_id):
    """Padrão + o que o usuário salvou (valores antigos que deixaram de valer são ignorados)."""
    salvas = repositorio.ler_preferencias(usuario_id)
    efetivas = dict(PADRAO)
    for chave, valor in salvas.items():
        try:
            efetivas.update(validar({chave: valor}))
        except ValueError:
            continue
    return efetivas


def salvar(usuario_id, novas):
    """Junta as novas preferências às atuais e grava. Retorna as preferências efetivas."""
    atuais = ler(usuario_id)
    atuais.update(validar(novas))
    if atuais["limiar_alta"] < atuais["limiar_analise"] + 5:
        raise ValueError("O limiar de “alta relevância” precisa ficar ao menos 5 pontos acima do de “em análise”.")
    repositorio.salvar_preferencias(usuario_id, {k: v for k, v in atuais.items() if v != PADRAO[k]})
    return atuais
