/* NEXO — tela Detalhe da conta: métricas, composição do score, entradas/saídas e volume semanal. */
import {charts} from "../nucleo/graficos.js";
import {estado} from "../nucleo/estado.js";
import {el, esc, fmtBRL, fmtData, fmtNum, pill} from "../nucleo/utilidades.js";

const nomes = {degree:"Degree", betweenness:"Betweenness", closeness:"Closeness", flow:"Flow", imbalance:"Imbalance"};
let atual = null;
function render(id){
  atual = id;
  const c = estado.porId[id], d = estado.dados, pesos = d.simulacao.pesos;
  const enviadas = d.transacoes.filter(t=>t.de===id);
  const recebidas = d.transacoes.filter(t=>t.para===id);
  const volume = enviadas.concat(recebidas).reduce((a,t)=>a+t.valor,0);

  const resumo = c.status==="Alta relevância"
    ? "A conta apresenta elevada conectividade e posição relevante na estrutura da rede analisada. Os indicadores sugerem que ela necessita investigação complementar."
    : c.status==="Em análise"
    ? "A conta apresenta indicadores acima da média da rede, com posição intermediária entre diferentes grupos de contas."
    : "A conta apresenta comportamento estrutural compatível com a média da rede analisada no período.";

  const composicao = Object.keys(nomes).map(k=>{
    const contrib = 100*pesos[k]*c.normalizado[k];
    return `<div style="display:grid;grid-template-columns:110px 1fr 120px;gap:10px;align-items:center;font-size:12.5px;margin-bottom:7px">
      <span>${nomes[k]}</span>
      <div style="background:var(--bg);border-radius:4px;height:10px;overflow:hidden"><div style="width:${(c.normalizado[k]*100).toFixed(1)}%;height:100%;background:var(--blue)"></div></div>
      <span style="color:var(--ink-3)">${fmtNum(c.normalizado[k],3)} × ${pesos[k]} = <b style="color:var(--ink)">${fmtNum(contrib,1)}</b></span></div>`;
  }).join("");

  const linhas = (lista, campo) => lista.length ? lista.map(t=>`<tr class="clickable" data-conta="${t[campo]}"><td class="mono-id">${t[campo]}</td><td>${fmtData(t.data)}</td><td>${esc(t.tipo)}</td><td class="num">${fmtBRL(t.valor)}</td></tr>`).join("")
    : `<tr><td colspan="4" class="empty">Nenhuma no período.</td></tr>`;

  el("contaDetalhe").innerHTML = `
    <div style="display:flex;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:18px">
      <div>
        <div style="font-size:12px;color:var(--ink-3)">Conta · ranking #${c.ranking} de ${d.contas.length}</div>
        <h2 style="margin:2px 0 6px;font-size:26px;letter-spacing:-.02em">${c.id}</h2>
        <div>${pill(c.status)} <span style="font-size:12.5px;color:var(--ink-3);margin-left:8px">${esc(c.titular)} · aberta em ${fmtData(c.data_abertura)} · comunidade ${c.com}</span></div>
      </div>
      <div style="flex:1"></div>
      <button class="btn ghost" data-goto="contas">Voltar ao ranking</button>
      <button class="btn ghost" data-simular="${c.id}">Simular transação</button>
      <button class="btn" data-goto="rede">Ver na rede</button>
    </div>

    <div class="grid g4">
      <div class="kpi"><h4>Degree</h4><div class="val">${c.degree}</div><div class="sub">${c.inDeg} entradas · ${c.outDeg} saídas (contas distintas)</div></div>
      <div class="kpi"><h4>Betweenness</h4><div class="val">${fmtNum(c.betw,3)}</div><div class="sub">intermediação normalizada</div></div>
      <div class="kpi"><h4>Closeness</h4><div class="val">${fmtNum(c.close,3)}</div><div class="sub">proximidade de saída</div></div>
      <div class="kpi ${c.status==="Alta relevância"?"alert":c.status==="Em análise"?"warn":""}"><h4>Score NEXO*</h4><div class="val">${fmtNum(c.score,1)}</div><div class="sub">indicador provisório</div></div>
    </div>

    <div class="grid g2 mt">
      <div class="card"><div class="card-head"><div><h3>Resumo estrutural</h3></div></div>
        <div class="card-body"><p style="margin:0;font-size:13.5px;line-height:1.7">${resumo}</p>
        <p style="margin:12px 0 0;font-size:12px;color:var(--ink-3)">Entrada ${fmtBRL(c.entrada)} · Saída ${fmtBRL(c.saida)} · Imbalance ${fmtNum(c.imbalance,3)} · Autovetor ${fmtNum(c.eig,3)} · Volume no período ${fmtBRL(volume)}</p></div></div>
      <div class="card"><div class="card-head"><div><h3>Composição do score</h3><p>minmax(métrica) × peso × 100</p></div></div>
        <div class="card-body">${composicao}</div></div>
    </div>

    <div class="grid g2 mt">
      <div class="card"><div class="card-head"><div><h3>Contas que enviaram valores</h3><p>${recebidas.length} transferências recebidas</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Conta</th><th>Data</th><th>Tipo</th><th class="num">Valor</th></tr></thead><tbody>${linhas(recebidas,"de")}</tbody></table></div></div>
      <div class="card"><div class="card-head"><div><h3>Contas que receberam valores</h3><p>${enviadas.length} transferências enviadas</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Conta</th><th>Data</th><th>Tipo</th><th class="num">Valor</th></tr></thead><tbody>${linhas(enviadas,"para")}</tbody></table></div></div>
    </div>

    <div class="card mt"><div class="card-head"><div><h3>Volume de transações ao longo do tempo</h3><p>Soma movimentada pela conta por semana (S-0 = semana da data de referência)</p></div></div>
      <div class="card-body"><div id="contaHist"></div></div></div>

    <p style="font-size:12px;color:var(--ink-3);margin-top:12px">* Score NEXO provisório. A fórmula definitiva será definida, documentada e validada matematicamente pela equipe.</p>`;

  const maxDias = Math.max(...d.transacoes.map(t=>t.dias), 0);
  const nSem = Math.max(1, Math.ceil((estado.periodo || maxDias+1)/7));
  const semanas = Array.from({length:nSem}, (_,s)=>{
    const tx = d.transacoes.filter(t=>(t.de===id||t.para===id) && t.dias>=s*7 && t.dias<(s+1)*7);
    return {rotulo:`S-${s}`, valor: tx.reduce((a,t)=>a+t.valor,0)};
  }).reverse();
  charts.barras(el("contaHist"), semanas);
}

export function mostrar(id){ if(estado.porId[id]) render(id); }
// nova análise com a tela aberta: redesenha a mesma conta com os números novos
export function atualizar(){ if(el("page-conta").classList.contains("active") && atual && estado.porId[atual]) render(atual); }
