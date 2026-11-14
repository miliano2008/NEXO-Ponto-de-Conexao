/* NEXO — Painel de risco (Fase 2): indícios por regra, prioridade de verificação,
   contas priorizadas com evidências, comunidades em destaque e as regras com seus limites.
   Tudo vem do backend (nucleo/risco.py); esta tela só organiza e filtra. */
import {charts} from "../nucleo/graficos.js";
import {estado} from "../nucleo/estado.js";
import {contasVisiveis, situacao} from "../nucleo/filtros.js";
import {chipInvestigacao, el, esc, fmtBRL, fmtNum, pillRisco} from "../nucleo/utilidades.js";

const CORES = {"Alta":"var(--red)", "Moderada":"var(--amber)", "Baixa":"var(--blue)", "Sem indícios":"var(--line)"};
let regraFiltro = "", aberta = null, ligado = false;

const risco = () => estado.dados.risco;
const nomeRegra = id => risco().regras.find(r => r.id === id)?.nome || id;

function kpis(contas){
  const r = risco(), n = nivel => contas.filter(c => c.nivel_risco === nivel).length;
  const achados = contas.reduce((a, c) => a + c.indicios.length, 0);
  const atipicas = estado.dados.transacoes.filter(t => t.atipica).length;
  el("riscoKpis").innerHTML = `
    <div class="kpi alert"><h4>Prioridade alta</h4><div class="val">${n("Alta")}</div><div class="sub">contas com 60 pontos ou mais</div></div>
    <div class="kpi warn"><h4>Prioridade moderada</h4><div class="val">${n("Moderada")}</div><div class="sub">contas com 30 a 59 pontos</div></div>
    <div class="kpi"><h4>Indícios encontrados</h4><div class="val">${achados}</div><div class="sub">em ${contas.filter(c => c.indicios.length).length} contas · ${r.regras.length} regras</div></div>
    <div class="kpi"><h4>Comunidades em destaque</h4><div class="val">${r.resumo.comunidades_destaque}</div><div class="sub">${atipicas} transação(ões) de valor atípico</div></div>`;
}

function porRegra(contas){
  const regras = risco().regras.map(r => ({...r, qtd: contas.filter(c => c.indicios.includes(r.id)).length}));
  const max = Math.max(1, ...regras.map(r => r.qtd));
  el("riscoPorRegra").innerHTML = regras.map(r => `
    <button class="barra-regra ${regraFiltro === r.id ? "on" : ""}" data-regra="${r.id}" title="${esc(r.mede)}">
      <span class="nome">${esc(r.nome)}</span>
      <span class="trilho"><i style="width:${(r.qtd / max * 100).toFixed(1)}%"></i></span>
      <b>${r.qtd}</b></button>`).join("");
  charts.rosca(el("riscoNiveis"), ["Alta", "Moderada", "Baixa", "Sem indícios"].map(nome =>
    ({nome, valor: contas.filter(c => c.nivel_risco === nome).length, cor: CORES[nome]})), "contas");
}

function evidencias(id){
  const r = estado.dados.risco.contas[id];
  if(!r.indicios.length) return `<p class="empty" style="margin:0">Nenhuma regra encontrou indícios para esta conta no recorte atual.</p>`;
  return `<ul class="evidencias">${r.indicios.map(i => `
    <li><b>${esc(i.nome)}</b> <span class="peso">+${i.peso}</span><br>${esc(i.evidencia)}
      ${i.transacoes?.length ? `<span class="tx">Transações: ${i.transacoes.slice(0, 8).map(esc).join(", ")}${i.transacoes.length > 8 ? "…" : ""}</span>` : ""}</li>`).join("")}</ul>`;
}

function tabela(contas){
  const lista = contas.filter(c => c.risco > 0 && (!regraFiltro || c.indicios.includes(regraFiltro)))
    .sort((a, b) => b.risco - a.risco || a.id.localeCompare(b.id));
  el("riscoSub").textContent = `${lista.length} conta(s) com indícios${regraFiltro ? ` na regra "${nomeRegra(regraFiltro)}"` : ""}. Clique para ver as evidências.`;
  el("riscoFiltroRegra").innerHTML = regraFiltro
    ? `<span class="chip">Regra: ${esc(nomeRegra(regraFiltro))}</span><button class="btn ghost sm" data-regra="">Mostrar todas</button>` : "";
  el("riscoBody").innerHTML = lista.length ? lista.map(c => `
    <tr class="clickable ${aberta === c.id ? "aberta" : ""}" data-abrir="${c.id}">
      <td class="mono-id">${c.id}</td><td>${pillRisco(c.nivel_risco)}</td><td class="num"><strong>${c.risco}</strong></td>
      <td><div class="chip-row">${c.indicios.map(i => `<span class="chip">${esc(nomeRegra(i))}</span>`).join("")}</div></td>
      <td class="num">${c.com}</td>
      <td>${chipInvestigacao(situacao(c.id), estado.casos[c.id]?.situacao_nome)}</td></tr>
    ${aberta === c.id ? `<tr class="linha-evidencia"><td colspan="6">${evidencias(c.id)}
      <div style="margin-top:10px;display:flex;gap:8px"><button class="btn sm" data-conta="${c.id}">Abrir a conta e registrar a investigação</button></div></td></tr>` : ""}`).join("")
    : `<tr><td colspan="6" class="empty">Nenhuma conta com indícios para os filtros atuais.</td></tr>`;
}

function comunidades(contas){
  const visiveis = new Set(contas.map(c => c.com));
  el("riscoComBody").innerHTML = risco().comunidades.filter(c => visiveis.has(c.comunidade)).map(c => `
    <tr class="${c.destaque ? "destaque" : ""}"><td class="num">${c.comunidade}</td><td class="num">${c.contas.length}</td>
      <td>${c.sinalizadas.length ? c.sinalizadas.map(id => `<a href="#" data-conta="${id}" class="mono-id">${id}</a>`).join(", ") : "—"}
        ${c.destaque ? ` <span class="pill analise">destaque</span>` : ""}</td>
      <td class="num">${fmtNum(c.densidade, 2)}</td><td class="num">${fmtBRL(c.volume_interno)}</td></tr>`).join("");
}

function regras(){
  el("riscoRegrasBody").innerHTML = risco().regras.map(r => `
    <tr><td><b>${esc(r.nome)}</b><br><span style="font-size:12px;color:var(--ink-3)">${esc(r.mede)}</span></td>
      <td style="font-size:12.5px">${esc(r.limite)}</td><td class="num">${r.peso}</td></tr>`).join("");
}

function render(){
  if(!estado.dados?.risco) return;
  const contas = contasVisiveis();
  kpis(contas); porRegra(contas); tabela(contas); comunidades(contas); regras();
}

export function iniciar(){
  if(ligado) return;
  ligado = true;
  el("page-risco").addEventListener("click", e => {
    const regra = e.target.closest("[data-regra]");
    if(regra){ regraFiltro = regraFiltro === regra.dataset.regra ? "" : regra.dataset.regra; render(); return; }
    const linha = e.target.closest("[data-abrir]");
    if(linha && !e.target.closest("[data-conta]")){ aberta = aberta === linha.dataset.abrir ? null : linha.dataset.abrir; render(); }
  });
}
export const atualizar = render;
export const filtrar = render;
export const casos = render;
