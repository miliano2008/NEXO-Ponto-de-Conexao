/* NEXO — estado compartilhado da aplicação e avisos entre telas.

   O estado guarda o que vem da API (dados da análise, usuário, permissões) e as
   escolhas da tela (período, limiares, contas destacadas).

   As telas não chamam umas às outras: avisam por eventos.
     "dados"         → chegou uma análise nova (outro período, simulação...)
     "reclassificado"→ os limiares mudaram; só é preciso redesenhar as cores/status
     "tema"          → claro/escuro mudou
     "rotulos"       → mostrar/esconder os nomes das contas no grafo
*/

export const estado = {
  usuario: null, cargos: {}, permissoes: {}, emailConfigurado: false,
  periodo: 0, dados: null, porId: {}, limiares: {analise:45, alta:70},
  destaque: new Set(), ultimoImpacto: null,
  versaoDados: 0            // muda a cada análise nova (usado para invalidar as matrizes)
};

const ouvintes = {};

export function ouvir(evento, funcao){
  (ouvintes[evento] ||= []).push(funcao);
}

export function emitir(evento, valor){
  (ouvintes[evento] || []).forEach(f => f(valor));
}
