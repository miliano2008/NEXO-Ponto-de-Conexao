/* NEXO — filtros globais (Fase 2), em duas camadas:

   1. RECORTE da análise (recalcula a rede no servidor): período (data inicial e final),
      tipos de transação e faixa de valor. Mudou → nova análise (/api/resultados?...).
   2. VISUALIZAÇÃO (não recalcula, só filtra o que aparece): conta de origem/destino,
      comunidade, prioridade de risco, status de relevância, situação da investigação e
      mínimo de transações por conta. Mudou → evento "filtros".
*/
import {estado} from "./estado.js";
import {fmtBRL, fmtData} from "./utilidades.js";

export const RECORTE_VAZIO = {dias:0, inicio:"", fim:"", tipos:[], valor_min:"", valor_max:""};
export const FILTROS_VAZIOS = {origem:"", destino:"", comunidade:"", risco:[], status:"", investigacao:"", minTx:0};

estado.recorte ||= {...RECORTE_VAZIO};
estado.filtros ||= {...FILTROS_VAZIOS, risco:[]};
estado.casos ||= {};

/* ---------- recorte ---------- */
export function consulta(){
  const r = estado.recorte, p = new URLSearchParams();
  if(r.inicio || r.fim){ if(r.inicio) p.set("inicio", r.inicio); if(r.fim) p.set("fim", r.fim); }
  else if(r.dias) p.set("dias", r.dias);
  if(r.tipos.length) p.set("tipos", r.tipos.join(","));
  if(r.valor_min !== "" && r.valor_min != null) p.set("valor_min", r.valor_min);
  if(r.valor_max !== "" && r.valor_max != null) p.set("valor_max", r.valor_max);
  return p.toString();
}

export function descreverPeriodo(){
  const r = estado.recorte, rec = estado.dados?.simulacao?.recorte;
  if(r.inicio || r.fim){
    const ini = r.inicio || rec?.inicio_efetivo, fim = r.fim || rec?.fim_efetivo;
    return ini === fim ? `dia ${fmtData(ini)}` : `${fmtData(ini)} a ${fmtData(fim)}`;
  }
  return r.dias ? `últimos ${r.dias} dias` : "base completa";
}

export function descreverRecorte(){
  const r = estado.recorte, partes = [descreverPeriodo()];
  if(r.tipos.length) partes.push(r.tipos.join(", "));
  if(r.valor_min !== "" && r.valor_min != null) partes.push(`≥ ${fmtBRL(r.valor_min)}`);
  if(r.valor_max !== "" && r.valor_max != null) partes.push(`≤ ${fmtBRL(r.valor_max)}`);
  return partes.join(" · ");
}

/* ---------- visualização ---------- */
export function situacao(conta){ return estado.casos[conta]?.situacao || "nao_iniciada"; }

function contaPassa(c){
  const f = estado.filtros;
  return (!f.comunidade || String(c.com) === String(f.comunidade))
    && (!f.risco.length || f.risco.includes(c.nivel_risco))
    && (!f.status || c.status === f.status)
    && (!f.investigacao || situacao(c.id) === f.investigacao)
    && (!f.minTx || (c.qtd_transacoes_entrada + c.qtd_transacoes_saida) >= f.minTx);
}

/* contas visíveis: atendem aos filtros de conta e, se houver origem/destino, participam dessas transações */
export function contasVisiveis(){
  const f = estado.filtros, d = estado.dados;
  let lista = d.contas.filter(contaPassa);
  if(f.origem || f.destino){
    const envolvidas = new Set();
    transacoesVisiveis().forEach(t => { envolvidas.add(t.de); envolvidas.add(t.para); });
    lista = lista.filter(c => envolvidas.has(c.id));
  }
  return lista;
}

/* transações visíveis: origem/destino exatos; a comunidade, a prioridade e a investigação valem
   quando QUALQUER uma das duas contas atende (a transação liga a conta filtrada a outra) */
export function transacoesVisiveis(){
  const f = estado.filtros, por = estado.porId;
  const contaFiltrada = f.comunidade || f.risco.length || f.status || f.investigacao || f.minTx;
  return estado.dados.transacoes.filter(t =>
    (!f.origem || t.de === f.origem) && (!f.destino || t.para === f.destino) &&
    (!contaFiltrada || contaPassa(por[t.de]) || contaPassa(por[t.para])));
}

export function quantidadeAtivos(){
  const r = estado.recorte, f = estado.filtros;
  return [r.inicio || r.fim || r.dias, r.tipos.length, r.valor_min !== "" && r.valor_min != null,
          r.valor_max !== "" && r.valor_max != null, f.origem, f.destino, f.comunidade, f.risco.length,
          f.status, f.investigacao, f.minTx].filter(Boolean).length;
}

export const filtrosDeVisualizacaoAtivos = () => {
  const f = estado.filtros;
  return Boolean(f.origem || f.destino || f.comunidade || f.risco.length || f.status || f.investigacao || f.minTx);
};
