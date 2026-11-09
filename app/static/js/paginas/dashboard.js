/* NEXO — tela Dashboard: indicadores, volume diário, distribuição e contas mais relevantes. */
import {charts} from "../nucleo/graficos.js";
import {estado} from "../nucleo/estado.js";
import {el, fmtBRL, fmtNum, paraData, pill} from "../nucleo/utilidades.js";

function render(){
  const d = estado.dados, tx = d.transacoes, sim = d.simulacao;
  const emAnalise = d.contas.filter(c=>c.status==="Em análise"||c.status==="Alta relevância").length;
  el("dashKpis").innerHTML = `
    <div class="kpi"><h4>Transações analisadas</h4><div class="val">${tx.length}</div><div class="sub">${fmtBRL(d.dashboard.volume_total)} · ${sim.transacoes_simuladas} simulada(s)</div></div>
    <div class="kpi"><h4>Contas analisadas</h4><div class="val">${d.dashboard.total_contas}</div><div class="sub">${d.dashboard.total_arestas_dirigidas_distintas} conexões dirigidas distintas</div></div>
    <div class="kpi warn"><h4>Contas em análise</h4><div class="val">${emAnalise}</div><div class="sub">score ≥ ${estado.limiares.analise} (limiar provisório)</div></div>
    <div class="kpi"><h4>Comunidades identificadas</h4><div class="val">${d.dashboard.total_comunidades}</div><div class="sub">Louvain · modularidade ${fmtNum(d.dashboard.modularidade_louvain,3)}</div></div>`;

  // série diária real a partir das transações do período
  const porDia = {};
  tx.forEach(t => { (porDia[t.data] ||= {valor:0,qtd:0}); porDia[t.data].valor += t.valor; porDia[t.data].qtd++; });
  const datas = Object.keys(porDia).sort();
  const serie = [];
  if(datas.length){
    const fim = paraData(sim.data_referencia);
    const ini = estado.periodo ? new Date(fim.getFullYear(), fim.getMonth(), fim.getDate()-estado.periodo+1) : paraData(datas[0]);
    for(let dt = new Date(ini); dt <= fim; dt.setDate(dt.getDate()+1)){
      const iso = `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,"0")}-${String(dt.getDate()).padStart(2,"0")}`;
      serie.push({data:new Date(dt), valor: porDia[iso]?.valor || 0, qtd: porDia[iso]?.qtd || 0});
    }
  }
  charts.area(el("chartVolume"), serie);
  charts.rosca(el("chartDist"), [
    {nome:"Normal", valor:tx.filter(t=>t.status==="Normal").length, cor:"var(--blue)"},
    {nome:"Em análise", valor:tx.filter(t=>t.status==="Em análise").length, cor:"var(--amber)"},
    {nome:"Alta relevância estrutural", valor:tx.filter(t=>t.status==="Alta relevância").length, cor:"var(--red)"}
  ]);
  el("dashTop").innerHTML = [...d.contas].sort((a,b)=>b.score-a.score).slice(0,8).map(c=>`
    <tr class="clickable" data-conta="${c.id}">
      <td class="mono-id">${c.id}</td><td class="num"><strong>${fmtNum(c.score,1)}</strong></td><td class="num">${c.degree}</td>
      <td class="num">${fmtNum(c.betw,3)}</td><td class="num">${fmtNum(c.close,3)}</td>
      <td class="num">${c.com}</td><td>${pill(c.status)}</td></tr>`).join("");
}

export const atualizar = render;
export const reclassificar = render;
