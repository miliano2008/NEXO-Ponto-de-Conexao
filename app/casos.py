"""NEXO — investigação humana: situação de cada conta e histórico das decisões (Fase 2).

Uma conta sem registro está "Não iniciada". Cada mudança exige um comentário, guarda
quem decidiu e quando, e vai para a auditoria. O NEXO só registra a decisão do analista:
nenhuma situação é atribuída automaticamente pelas regras.
"""

from app import auth
from banco.conexao import conectar

SITUACOES = {
    "nao_iniciada": "Não iniciada",
    "em_analise": "Em análise",
    "investigada": "Investigada",
    "sem_indicio": "Sem indício",
    "encaminhada": "Encaminhada",
}
MIN_COMENTARIO = 5


def _texto_data(valor):
    return auth.para_texto(valor)


def listar():
    """Situação atual de todas as contas com registro: {conta: {...}}."""
    with conectar() as c:
        linhas = c.execute("SELECT c.conta_id, c.situacao, c.atualizado_em, u.nome AS responsavel "
                           "FROM casos c LEFT JOIN usuarios u ON u.id = c.responsavel_id").fetchall()
    return {l["conta_id"]: {"situacao": l["situacao"], "situacao_nome": SITUACOES.get(l["situacao"], l["situacao"]),
                            "atualizado_em": _texto_data(l["atualizado_em"]), "responsavel": l["responsavel"]}
            for l in linhas}


def detalhe(conta_id):
    with conectar() as c:
        caso = c.execute("SELECT c.*, u.nome AS responsavel FROM casos c LEFT JOIN usuarios u ON u.id = c.responsavel_id "
                         "WHERE c.conta_id = ?", (conta_id,)).fetchone()
        historico = [] if caso is None else c.execute(
            "SELECT * FROM casos_historico WHERE caso_id = ? ORDER BY id DESC", (caso["id"],)).fetchall()
    situacao = caso["situacao"] if caso else "nao_iniciada"
    return {"conta": conta_id, "situacao": situacao, "situacao_nome": SITUACOES[situacao],
            "responsavel": caso["responsavel"] if caso else None,
            "atualizado_em": _texto_data(caso["atualizado_em"]) if caso else None,
            "historico": [{"de": h["situacao_anterior"], "de_nome": SITUACOES.get(h["situacao_anterior"] or "nao_iniciada"),
                           "para": h["situacao_nova"], "para_nome": SITUACOES.get(h["situacao_nova"]),
                           "comentario": h["comentario"], "usuario": h["usuario_nome"],
                           "data": _texto_data(h["criado_em"])} for h in historico]}


def atualizar(conta_id, situacao, comentario, usuario, contas_validas, ip=None):
    """Registra a decisão do analista. Lança auth.ErroAuth com mensagem pronta."""
    if conta_id not in contas_validas:
        raise auth.ErroAuth("Conta inexistente na base.")
    if situacao not in SITUACOES or situacao == "nao_iniciada":
        raise auth.ErroAuth("Situação inválida.")
    comentario = " ".join(str(comentario or "").split())
    if len(comentario) < MIN_COMENTARIO:
        raise auth.ErroAuth("Escreva um comentário explicando a decisão (mínimo de 5 caracteres).")
    comentario = comentario[:500]
    agora = auth.agora().isoformat()
    with conectar() as c:
        caso = c.execute("SELECT * FROM casos WHERE conta_id = ?", (conta_id,)).fetchone()
        anterior = caso["situacao"] if caso else None
        if caso is None:
            caso_id = c.execute("INSERT INTO casos (conta_id, situacao, responsavel_id, criado_em, atualizado_em) "
                                "VALUES (?, ?, ?, ?, ?)", (conta_id, situacao, usuario["id"], agora, agora)).lastrowid
        else:
            caso_id = caso["id"]
            c.execute("UPDATE casos SET situacao = ?, responsavel_id = ?, atualizado_em = ? WHERE id = ?",
                      (situacao, usuario["id"], agora, caso_id))
        c.execute("INSERT INTO casos_historico (caso_id, situacao_anterior, situacao_nova, comentario, usuario_id, "
                  "usuario_nome, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (caso_id, anterior, situacao, comentario, usuario["id"], usuario["nome"], agora))
    auth.registrar("caso_atualizado", None,
                   f"{conta_id}: {SITUACOES.get(anterior or 'nao_iniciada')} → {SITUACOES[situacao]} por {usuario['nome']}", ip)
    return detalhe(conta_id)
