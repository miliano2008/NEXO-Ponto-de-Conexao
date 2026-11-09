/* NEXO — tela Simulador: nova transação simulada, impacto no score e lista para desfazer.
   A simulação é de cada usuário e fica guardada no servidor; a base oficial não muda. */
import {api} from "../nucleo/api.js";
import {carregar} from "../nucleo/dados.js";
import {estado} from "../nucleo/estado.js";
import {irPara} from "../nucleo/roteador.js";
import {ui} from "../nucleo/ui.js";
import {el, esc, fmtBRL, fmtData, fmtNum, pill} from "../nucleo/utilidades.js";

let verTodas = false;

function render(){
  const d = estado.dados, sim = d.simulacao;
  const opcoes = d.contas.map(c=>c.id).sort().map(id=>`<option value="${id}">${id} · ${esc(estado.porId[id].titular)}</option>`).join("");
  const de = el("simDe").value, para = el("simPara").value, tipo = el("simTipo").value;
  el("simDe").innerHTML = opcoes; el("simPara").innerHTML = opcoes;
  el("simTipo").innerHTML = sim.tipos_transacao.map(t=>`<option>${esc(t)}</option>`).join("");
  if(de) el("simDe").value = de;
  el("simPara").value = para || "C002";
  if(tipo) el("simTipo").value = tipo;
  if(!el("simData").value) el("simData").value = sim.data_referencia;

  el("simEstado").innerHTML = `<dl class="kv" style="grid-template-columns:170px 1fr;font-size:12.5px">
      <dt>Base original</dt><dd>${d.dashboard.total_contas} contas · ${sim.total_base_original} transações</dd>
      <dt>Transações simuladas</dt><dd>${sim.transacoes_simuladas}</dd>
      <dt>Data de referência</dt><dd>${fmtData(sim.data_referencia)}</dd>
      <dt>Período analisado</dt><dd>${sim.periodo_dias ? `últimos ${sim.periodo_dias} dias` : "base completa"}</dd>
      <dt>Comunidades / modularidade</dt><dd>${d.dashboard.total_comunidades} · ${fmtNum(d.dashboard.modularidade_louvain,3)}</dd>
      <dt>Líder do ranking</dt><dd><a href="#" data-conta="${d.contas[0].id}" class="mono-id">${d.contas[0].id}</a> · score ${fmtNum(d.contas[0].score,1)}</dd>
    </dl>
    <a class="btn ghost sm" style="display:inline-block;margin-top:14px;text-decoration:none" href="/api/exportar?dias=${estado.periodo}">Baixar resultados (JSON)</a>`;

  el("simLista").innerHTML = sim.lista_simuladas.length ? sim.lista_simuladas.map(s=>`
    <tr><td class="mono-id">${s.id_transacao}</td><td>${fmtData(s.data)} ${esc(s.hora)}</td>
      <td><a href="#" data-conta="${s.conta_origem}" class="mono-id">${s.conta_origem}</a></td>
      <td><a href="#" data-conta="${s.conta_destino}" class="mono-id">${s.conta_destino}</a></td>
      <td class="num">${fmtBRL(+s.valor)}</td><td>${esc(s.tipo_transacao)}</td>
      <td class="num"><button class="btn ghost sm" data-remover="${s.id_transacao}">Desfazer</button></td></tr>`).join("")
    : `<tr><td colspan="7" class="empty">Nenhuma transação simulada. A rede está igual à base original.</td></tr>`;
  renderImpacto();
}

function renderImpacto(){
  const r = estado.ultimoImpacto;
  el("simVerRede").style.display = r ? "" : "none";
  if(!r){ el("simImpacto").innerHTML = `<tr><td colspan="8" class="empty">Nenhuma transação simulada ainda.</td></tr>`; return; }
  const t = r.transacao;
  const cab = `<tr><td colspan="8" style="background:var(--bg);font-size:12.5px"><b>${t.id_transacao}</b>: ${t.conta_origem} → ${t.conta_destino} · ${fmtBRL(+t.valor)} · ${fmtData(t.data)} ${esc(t.hora)} — ${r.impacto.length} conta(s) afetada(s)</td></tr>`;
  const lista = verTodas ? r.impacto : r.impacto.slice(0,12);
  const mais = r.impacto.length > 12 ? `<tr><td colspan="8" style="text-align:center"><button class="btn ghost sm" id="simVerTodas">${verTodas?"Mostrar só as 12 maiores variações":`Ver todas as ${r.impacto.length} contas`}</button></td></tr>` : "";
  el("simImpacto").innerHTML = cab + (lista.length ? lista.map(i=>`
    <tr class="clickable" data-conta="${i.id}">
      <td class="mono-id">${i.id}${i.id===t.conta_origem||i.id===t.conta_destino?' <span class="chip sim">envolvida</span>':""}</td>
      <td class="num">${fmtNum(i.antes.score,2)}</td><td class="num"><strong>${fmtNum(i.depois.score,2)}</strong></td>
      <td class="num ${i.delta_score>0?"up":"down"}">${i.delta_score>0?"+":""}${fmtNum(i.delta_score,2)}</td>
      <td class="num">#${i.antes.ranking} → #${i.depois.ranking}</td>
      <td class="num">${i.antes.com}${i.antes.com!==i.depois.com?` → <b>${i.depois.com}</b>`:""}</td>
      <td>${pill(i.antes.status)}</td><td>${pill(i.depois.status)}</td></tr>`).join("")
    : `<tr><td colspan="8" class="empty">Nenhuma conta mudou de score, status ou comunidade.</td></tr>`) + mais;
}

async function enviar(e){
  e.preventDefault();
  const corpo = {de:el("simDe").value, para:el("simPara").value, valor:el("simValor").value,
                 data:el("simData").value, hora:el("simHora").value, tipo:el("simTipo").value};
  if(corpo.de===corpo.para){ ui.toast("Origem e destino precisam ser contas diferentes.", true); return; }
  el("simEnviar").disabled = true;
  try{
    const r = await api("/api/transacoes", {method:"POST", body:JSON.stringify(corpo)});
    estado.ultimoImpacto = r; verTodas = false;
    estado.destaque = new Set([corpo.de, corpo.para]);
    await carregar();
    const mudaram = r.impacto.filter(i=>i.antes.status!==i.depois.status);
    ui.toast(`Transação ${r.transacao.id_transacao} simulada · ${r.impacto.length} conta(s) com score alterado` +
      (el("swAlerts").classList.contains("on") && mudaram.length
        ? `<br>⚠ Mudança de status: ${mudaram.map(i=>`${i.id} (${i.antes.status} → ${i.depois.status})`).join(", ")}` : ""));
  } catch(err){ ui.toast(esc(err.message), true); }
  finally{ el("simEnviar").disabled = false; }
}

function aleatoria(){
  const ids = estado.dados.contas.map(c=>c.id);
  const de = ids[Math.floor(Math.random()*ids.length)];
  let para; do { para = ids[Math.floor(Math.random()*ids.length)]; } while(para===de);
  el("simDe").value = de; el("simPara").value = para;
  el("simValor").value = (500 + Math.random()*29500).toFixed(2);
  el("simData").value = estado.dados.simulacao.data_referencia;
  el("simHora").value = `${String(Math.floor(Math.random()*24)).padStart(2,"0")}:${String(Math.floor(Math.random()*60)).padStart(2,"0")}`;
  const tipos = estado.dados.simulacao.tipos_transacao;
  el("simTipo").value = tipos[Math.floor(Math.random()*tipos.length)];
}

async function remover(id){
  try{
    await api(`/api/transacoes/${encodeURIComponent(id)}`, {method:"DELETE"});
    if(estado.ultimoImpacto?.transacao.id_transacao===id){ estado.ultimoImpacto = null; estado.destaque = new Set(); }
    await carregar(); ui.toast(`Transação ${id} desfeita.`);
  } catch(err){ ui.toast(esc(err.message), true); }
}

async function restaurar(){
  await api("/api/simulacao/restaurar", {method:"POST"});
  estado.ultimoImpacto = null; estado.destaque = new Set(); el("simData").value = "";
  await carregar(); ui.toast("Base original restaurada (40 contas, 160 transações).");
}

export function iniciar(){
  el("simForm").addEventListener("submit", enviar);
  el("simAleatoria").addEventListener("click", aleatoria);
  el("simRestaurar").addEventListener("click", restaurar);
  el("simVerRede").addEventListener("click", ()=>irPara("rede"));
  el("simImpacto").addEventListener("click", e=>{
    if(e.target.id==="simVerTodas"){ verTodas = !verTodas; renderImpacto(); }
  });
  el("simLista").addEventListener("click", e=>{
    const b = e.target.closest("[data-remover]"); if(b) remover(b.dataset.remover);
  });
}

export const atualizar = render;
// vindo de "Simular transação a partir desta conta": já escolhe a origem
export function mostrar(contaOrigem){ if(contaOrigem && estado.porId[contaOrigem]) el("simDe").value = contaOrigem; }
