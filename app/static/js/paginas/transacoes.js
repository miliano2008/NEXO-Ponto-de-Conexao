/* NEXO — tela Transações: busca, filtros, paginação e detalhe de cada transação. */
import {estado} from "../nucleo/estado.js";
import {ui} from "../nucleo/ui.js";
import {el, esc, fmtBRL, fmtData, fmtNum, pill} from "../nucleo/utilidades.js";

const porPagina = 12;
let pagina = 1, ligado = false;

function filtrar(){
  const busca = el("txSearch").value.trim().toUpperCase();
  const conta = el("txConta").value, status = el("txStatus").value;
  const tipo = el("txTipo").value, min = parseFloat(el("txMin").value) || 0;
  return estado.dados.transacoes.filter(t =>
    (!busca || t.id.includes(busca) || t.de.includes(busca) || t.para.includes(busca)) &&
    (!conta || t.de===conta || t.para===conta) &&
    (!status || t.status===status) &&
    (!tipo || t.tipo===tipo) &&
    t.valor >= min
  ).sort((a,b)=> (b.data+b.hora).localeCompare(a.data+a.hora));
}

function render(){
  const lista = filtrar();
  const totalPag = Math.max(1, Math.ceil(lista.length/porPagina));
  if(pagina>totalPag) pagina = totalPag;
  const fatia = lista.slice((pagina-1)*porPagina, pagina*porPagina);

  el("txBody").innerHTML = fatia.length ? fatia.map(t=>`
    <tr class="clickable" data-tx="${t.id}">
      <td class="mono-id">${t.id} ${t.simulada?'<span class="chip sim">simulada</span>':""}</td><td>${fmtData(t.data)} ${t.hora}</td>
      <td>${t.de}</td><td>${t.para}</td><td class="num">${fmtBRL(t.valor)}</td>
      <td>${esc(t.tipo)}</td><td>${pill(t.status)}</td></tr>`).join("")
    : `<tr><td colspan="7" class="empty">Nenhuma transação atende a esses filtros. Ajuste a busca ou limpe os filtros.</td></tr>`;

  const btn = (rot,p,ativo,desab)=>`<button ${desab?"disabled":""} data-pg="${p}" class="${ativo?"active":""}">${rot}</button>`;
  let pg = `<span style="font-size:12px;color:var(--ink-3);margin-right:auto">${lista.length} transações no período</span>`;
  pg += btn("‹", pagina-1, false, pagina===1);
  for(let i=1;i<=totalPag;i++){
    if(i===1 || i===totalPag || Math.abs(i-pagina)<=2) pg += btn(i, i, i===pagina, false);
    else if(Math.abs(i-pagina)===3) pg += `<span style="color:var(--ink-3)">…</span>`;
  }
  pg += btn("›", pagina+1, false, pagina===totalPag);
  el("txPager").innerHTML = pg;
}

function detalhe(id){
  const t = estado.dados.transacoes.find(x=>x.id===id);
  const relacionadas = estado.dados.transacoes.filter(x=>x.id!==id && (x.de===t.de||x.para===t.de||x.de===t.para||x.para===t.para));
  ui.modal(`Transação ${t.id}`, `
    <dl class="kv">
      <dt>Identificador</dt><dd>${t.id} ${t.simulada?'<span class="chip sim">simulada</span>':""}</dd>
      <dt>Conta de origem</dt><dd><a href="#" data-conta="${t.de}" class="mono-id">${t.de}</a> · ${esc(estado.porId[t.de].titular)} · score ${fmtNum(estado.porId[t.de].score,1)}</dd>
      <dt>Conta de destino</dt><dd><a href="#" data-conta="${t.para}" class="mono-id">${t.para}</a> · ${esc(estado.porId[t.para].titular)} · score ${fmtNum(estado.porId[t.para].score,1)}</dd>
      <dt>Valor</dt><dd>${fmtBRL(t.valor)}</dd>
      <dt>Data</dt><dd>${fmtData(t.data)}</dd>
      <dt>Hora</dt><dd>${t.hora}</dd>
      <dt>Tipo</dt><dd>${esc(t.tipo)}</dd>
      <dt>Status</dt><dd>${pill(t.status)}</dd>
    </dl>
    <p style="font-size:12px;color:var(--ink-3)">O status da transação herda a maior classificação das duas contas; não indica irregularidade da operação.</p>
    <h4 style="margin:18px 0 8px;font-size:13.5px">Conexões relacionadas (${relacionadas.length})</h4>
    <div class="table-wrap" style="border:1px solid var(--line);border-radius:8px;max-height:220px;overflow:auto">
    <table><thead><tr><th>ID</th><th>Data</th><th>Origem</th><th>Destino</th><th class="num">Valor</th></tr></thead><tbody>
    ${relacionadas.slice(0,12).map(r=>`<tr><td class="mono-id">${r.id}</td><td>${fmtData(r.data)}</td><td>${r.de}</td><td>${r.para}</td><td class="num">${fmtBRL(r.valor)}</td></tr>`).join("")}
    </tbody></table></div>`);
}

function init(){
  const contaSel = el("txConta").value, tipoSel = el("txTipo").value;
  el("txConta").innerHTML = `<option value="">Todas</option>` + estado.dados.contas.map(c=>c.id).sort().map(c=>`<option>${c}</option>`).join("");
  const tipos = [...new Set(estado.dados.transacoes.map(t=>t.tipo))].sort();
  el("txTipo").innerHTML = `<option value="">Todos</option>` + tipos.map(t=>`<option>${esc(t)}</option>`).join("");
  el("txConta").value = contaSel; el("txTipo").value = tipos.includes(tipoSel) ? tipoSel : "";
  if(!ligado){
    ligado = true;
    ["txSearch","txConta","txStatus","txTipo","txMin"].forEach(id =>
      el(id).addEventListener("input", ()=>{ pagina=1; render(); }));
    el("txReset").addEventListener("click", ()=>{
      ["txSearch","txMin","txConta","txStatus","txTipo"].forEach(id=>el(id).value="");
      pagina=1; render();
    });
    el("txPager").addEventListener("click", e=>{
      const b = e.target.closest("button[data-pg]"); if(!b||b.disabled) return;
      pagina = parseInt(b.dataset.pg,10); render();
    });
    el("txBody").addEventListener("click", e=>{
      const tr = e.target.closest("tr[data-tx]"); if(tr) detalhe(tr.dataset.tx);
    });
  }
  render();
}

export const atualizar = init;
export const reclassificar = render;
