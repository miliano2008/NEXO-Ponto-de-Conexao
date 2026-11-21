/* NEXO — Histórico e comparação (Fase 4).
   Cenários salvos: cada execução guardada com o próprio resultado (não é recalculada).
   Comparar lado a lado: duas análises (base, meses, datas, simulação atual, cenários) com os
   dois grafos nas MESMAS posições, indicadores, destaques e a tabela de mudanças por conta. */
import {api} from "../nucleo/api.js";
import {carregar} from "../nucleo/dados.js";
import {estado} from "../nucleo/estado.js";
import {LAYOUT, carregarCytoscape, corDe, estilo, posicaoInicial} from "../nucleo/grafo.js";
import {irPara} from "../nucleo/roteador.js";
import {pode} from "../nucleo/sessao.js";
import {ui} from "../nucleo/ui.js";
import {el, esc, fmtBRL, fmtData, fmtDataHora, fmtNum, pillRisco} from "../nucleo/utilidades.js";

const MESES = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"];
let cenarios = [], grafos = [], ultima = null;

/* ---------- abas ---------- */
function abrirAba(nome){
  [...el("histTabs").children].forEach(b => b.classList.toggle("active", b.dataset.tab === nome));
  ["cenarios", "comparar"].forEach(t => el("tab-" + t).style.display = t === nome ? "" : "none");
  if(nome === "comparar") requestAnimationFrame(() => grafos.forEach(g => { g.resize(); g.fit(undefined, 20); }));
}

/* ---------- cenários salvos ---------- */
function descreverRecorte(r){
  if(!r || (!r.inicio && !r.fim && !r.dias && !(r.tipos || []).length && r.valor_min == null && r.valor_max == null)) return "base completa";
  const partes = [];
  if(r.inicio || r.fim) partes.push(`${fmtData(r.inicio)} a ${fmtData(r.fim)}`);
  else if(r.dias) partes.push(`últimos ${r.dias} dias`);
  if((r.tipos || []).length) partes.push(r.tipos.join(", "));
  if(r.valor_min != null) partes.push(`≥ ${fmtBRL(r.valor_min)}`);
  if(r.valor_max != null) partes.push(`≤ ${fmtBRL(r.valor_max)}`);
  return partes.join(" · ");
}

async function carregarCenarios(){
  if(!pode("simular")) return;
  try{ cenarios = (await api("/api/cenarios")).cenarios; }
  catch(err){ el("cenariosLista").innerHTML = `<p class="empty">${esc(err.message)}</p>`; return; }
  el("cenariosLista").innerHTML = cenarios.length ? cenarios.map(c => {
    const r = c.resumo, alta = r.prioridade_alta || [0, 0];
    return `<div class="card cenario"><div class="card-body">
      <h4>${esc(c.nome)}</h4><div class="quando">Salvo em ${fmtDataHora(c.salvo_em)} · recorte: ${esc(descreverRecorte(c.recorte))}</div>
      ${c.descricao ? `<p style="font-size:13px;margin:8px 0 0">${esc(c.descricao)}</p>` : ""}
      <dl><dt>Transações simuladas</dt><dd>${c.transacoes}</dd>
        <dt>Contas afetadas</dt><dd>${r.contas_alteradas}</dd>
        <dt>Maior variação</dt><dd>${r.maior_variacao ? `${r.maior_variacao.conta} (${r.maior_variacao.delta > 0 ? "+" : ""}${fmtNum(r.maior_variacao.delta, 2)} no score)` : "—"}</dd>
        <dt>Prioridade alta</dt><dd>${alta[0]} → <b>${alta[1]}</b> conta(s)</dd>
        <dt>Comunidades</dt><dd>${r.comunidades[0]} → ${r.comunidades[1]}</dd></dl>
      <div class="acoes"><button class="btn sm" data-ver-cenario="${c.id}">Ver execução</button>
        <button class="btn ghost sm" data-restaurar-cenario="${c.id}">Restaurar no simulador</button>
        <button class="btn ghost sm" data-excluir-cenario="${c.id}">Excluir</button></div></div></div>`;
  }).join("") : `<p class="empty" style="grid-column:1/-1">Nenhum cenário salvo ainda. No Simulador, inclua transações e clique em <b>💾 Salvar como cenário</b>.</p>`;
  preencherFontes();
}

async function restaurar(id){
  const c = cenarios.find(x => x.id === +id);
  if(!confirm(`Restaurar "${c.nome}" no simulador? A simulação atual será substituída pelas ${c.transacoes} transação(ões) do cenário.`)) return;
  try{ await api(`/api/cenarios/${id}/restaurar`, {method: "POST"}); await carregar(); ui.toast("✓ Cenário restaurado no simulador."); irPara("simulador"); }
  catch(err){ ui.toast(esc(err.message), true); }
}
async function excluir(id){
  const c = cenarios.find(x => x.id === +id);
  if(!confirm(`Excluir o cenário "${c.nome}"? Esta ação não pode ser desfeita.`)) return;
  try{ await api(`/api/cenarios/${id}`, {method: "DELETE"}); ui.toast("Cenário excluído."); carregarCenarios(); }
  catch(err){ ui.toast(esc(err.message), true); }
}

/* ---------- fontes da comparação ---------- */
function meses(){
  const b = estado.dados.simulacao.datas_base, lista = [];
  let [a, m] = b.primeira.split("-").map(Number);
  while(`${a}-${String(m).padStart(2, "0")}` <= b.ultima.slice(0, 7)){
    const mm = String(m).padStart(2, "0"), ult = new Date(a, m, 0).getDate();
    const ini = `${a}-${mm}-01` < b.primeira ? b.primeira : `${a}-${mm}-01`;
    const fim = `${a}-${mm}-${ult}` > b.ultima ? b.ultima : `${a}-${mm}-${ult}`;
    lista.push({valor: `recorte:${ini}:${fim}`, rotulo: `${MESES[m - 1][0].toUpperCase()}${MESES[m - 1].slice(1)}/${a} (${fmtData(ini).slice(0, 5)} a ${fmtData(fim).slice(0, 5)})`});
    m === 12 ? (a++, m = 1) : m++;
  }
  return lista;
}

function preencherFontes(){
  if(!estado.dados) return;
  const grupos = [["Base", [{valor: "base", rotulo: "Base completa"}, ...meses(), {valor: "personalizado", rotulo: "Período personalizado…"}]]];
  if(pode("simular")){
    grupos.push(["Simulação", [{valor: "rascunho", rotulo: `Minha simulação atual (${estado.dados.simulacao.transacoes_simuladas} transação(ões))`}]]);
    if(cenarios.length) grupos.push(["Cenários salvos", cenarios.flatMap(c => [
      {valor: `cenario:${c.id}`, rotulo: `${c.nome}`}, {valor: `cenario:${c.id}:base`, rotulo: `${c.nome} — base daquele momento`}])]);
  }
  const html = grupos.map(([g, ops]) => `<optgroup label="${g}">${ops.map(o => `<option value="${esc(o.valor)}">${esc(o.rotulo)}</option>`).join("")}</optgroup>`).join("");
  ["cmpA", "cmpB"].forEach((id, i) => {
    const atual = el(id).value;
    el(id).innerHTML = html;
    const ms = meses();
    el(id).value = atual && [...el(id).options].some(o => o.value === atual) ? atual : (ms[i]?.valor || "base");
    alternarDatas(id);
  });
  const b = estado.dados.simulacao.datas_base;
  ["cmpAIni", "cmpAFim", "cmpBIni", "cmpBFim"].forEach(id => { el(id).min = b.primeira; el(id).max = b.ultima; if(!el(id).value) el(id).value = id.endsWith("Ini") ? b.primeira : b.ultima; });
}
function alternarDatas(id){ el(id + "Datas").hidden = el(id).value !== "personalizado"; }
function fonteDe(id){
  return el(id).value === "personalizado" ? `recorte:${el(id + "Ini").value}:${el(id + "Fim").value}` : el(id).value;
}

/* ---------- comparação ---------- */
const sinal = (v, casas = 2) => v > 0 ? `+${fmtNum(v, casas)}` : fmtNum(v, casas);
const delta = (v, casas = 2, inverso = false) => !v ? `<span style="color:var(--ink-3)">0</span>`
  : `<span class="delta ${(v > 0) !== inverso ? "up" : "down"}">${sinal(v, casas)}</span>`;

async function comparar(a, b){
  if(a === b){ ui.toast("Escolha duas análises diferentes para comparar.", true); return; }
  el("cmpIr").disabled = true;
  el("cmpResultado").innerHTML = `<p class="empty">Calculando as duas análises…</p>`;
  try{ ultima = await api(`/api/comparar?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`); }
  catch(err){ el("cmpResultado").innerHTML = `<div class="note warn mt">${esc(err.message)}</div>`; return; }
  finally{ el("cmpIr").disabled = false; }
  await desenhar(ultima);
}

const ROTULOS = {total_transacoes: ["Transações", 0], volume_total: ["Volume", "brl"], total_comunidades: ["Comunidades", 0],
  total_arestas_dirigidas_distintas: ["Conexões dirigidas", 0], contas_em_analise: ["Contas em análise (score)", 0],
  modularidade_louvain: ["Modularidade", 3]};

async function desenhar(r){
  const d = r.diferencas, ind = d.indicadores;
  const linhaInd = Object.entries(ROTULOS).map(([k, [nome, casas]]) => {
    const [x, y] = ind[k], f = v => casas === "brl" ? fmtBRL(v) : fmtNum(v, casas);
    return `<tr><td>${nome}</td><td class="num">${f(x)}</td><td class="num">${f(y)}</td><td class="num">${casas === "brl" ? delta(y - x, 2) : delta(+(y - x).toFixed(casas === 0 ? 0 : casas), casas === 0 ? 0 : casas)}</td></tr>`;
  }).join("") + ["Alta", "Moderada"].map(n => {
    const x = d.risco_por_nivel[0][n] || 0, y = d.risco_por_nivel[1][n] || 0;
    return `<tr><td>Prioridade de risco ${n.toLowerCase()}</td><td class="num">${x}</td><td class="num">${y}</td><td class="num">${delta(y - x, 0, true)}</td></tr>`;
  }).join("");
  const lista = ids => ids.length ? ids.map(id => `<a href="#" data-conta="${id}" class="mono-id">${id}</a>`).join(", ") : "—";
  const nomeRegra = Object.fromEntries((estado.dados.risco?.regras || []).map(x => [x.id, x.nome]));
  const comparaveis = d.contas.filter(c => !c.so_em).sort((x, y) => Math.abs(y.delta_score) - Math.abs(x.delta_score) || x.id.localeCompare(y.id));
  const mudou = comparaveis.filter(c => c.delta_score || c.delta_ranking || c.nivel[0] !== c.nivel[1] || c.mudou_comunidade
                                        || c.comunidades_vizinhas[0] !== c.comunidades_vizinhas[1]);
  el("cmpResultado").innerHTML = `
    <div class="grid g2 mt">
      <div class="card"><div class="card-head"><div><h3>Indicadores</h3><p>${esc(r.a.rotulo)} × ${esc(r.b.rotulo)}</p></div></div>
        <div class="table-wrap"><table><thead><tr><th></th><th class="num">Esquerda</th><th class="num">Direita</th><th class="num">Δ</th></tr></thead>
        <tbody>${linhaInd}</tbody></table></div></div>
      <div class="card"><div class="card-head"><div><h3>Destaques</h3><p>O que mais mudou da esquerda para a direita</p></div></div>
        <div class="card-body"><dl class="kv" style="grid-template-columns:200px 1fr;font-size:12.5px">
          <dt>Passaram a ligar mais comunidades</dt><dd>${lista(d.destaques.mais_pontes)}</dd>
          <dt>Maiores variações de score</dt><dd>${lista(d.destaques.score)}</dd>
          <dt>Mais subiram no ranking</dt><dd>${lista(comparaveis.filter(c => c.delta_ranking > 0).sort((x, y) => y.delta_ranking - x.delta_ranking).slice(0, 5).map(c => c.id))}</dd>
          <dt>Mudaram de prioridade</dt><dd>${lista(d.destaques.mudaram_prioridade)}</dd>
          <dt>Mudaram de comunidade</dt><dd>${lista(d.destaques.mudaram_comunidade)}</dd>
          <dt>Conexões</dt><dd><b>${d.arestas_novas.length}</b> novas · <b>${d.arestas_removidas.length}</b> deixaram de existir</dd>
        </dl></div></div>
    </div>
    <div class="grafos-lado mt">
      <div class="card grafo-lado"><h4>Esquerda: ${esc(r.a.rotulo)}</h4><div class="grafo-cmp" id="cmpGrafoA" role="img" aria-label="Grafo da esquerda"></div></div>
      <div class="card grafo-lado"><h4>Direita: ${esc(r.b.rotulo)}</h4><div class="grafo-cmp" id="cmpGrafoB" role="img" aria-label="Grafo da direita"></div></div>
    </div>
    <div class="legenda-cmp"><span><i style="background:#1E7A5A;height:4px"></i>Conexão nova (só na direita)</span>
      <span><i style="background:#C2263C"></i>Conexão que deixou de existir (só na esquerda)</span>
      <span>Cor do nó: prioridade de risco · borda laranja: mudou de comunidade · clique numa conta para destacá-la nos dois lados</span></div>
    <div class="card mt"><div class="card-head"><div><h3>Mudanças por conta</h3><p>${mudou.length} conta(s) mudaram · ordenadas pela variação do score</p></div></div>
      <div class="table-wrap"><table><thead><tr><th>Conta</th><th class="num">Score</th><th class="num">Δ</th><th class="num">Ranking</th>
        <th>Prioridade</th><th class="num">Comunidades vizinhas</th><th class="num">Betweenness</th><th>Indícios novos</th></tr></thead>
      <tbody id="cmpTabela">${mudou.map(c => `<tr class="clickable" data-cmp-conta="${c.id}">
        <td class="mono-id">${c.id}${c.mudou_comunidade ? ' <span class="chip sim">comunidade</span>' : ""}</td>
        <td class="num">${fmtNum(c.score[0], 1)} → <b>${fmtNum(c.score[1], 1)}</b></td><td class="num">${delta(c.delta_score)}</td>
        <td class="num">#${c.ranking[0]} → #${c.ranking[1]}</td>
        <td>${c.nivel[0] === c.nivel[1] ? pillRisco(c.nivel[1]) : `${pillRisco(c.nivel[0])} → ${pillRisco(c.nivel[1])}`}</td>
        <td class="num">${c.comunidades_vizinhas[0]} → <b>${c.comunidades_vizinhas[1]}</b></td>
        <td class="num">${fmtNum(c.betweenness[0], 3)} → ${fmtNum(c.betweenness[1], 3)}</td>
        <td style="font-size:12px">${c.indicios_novos.map(i => esc(nomeRegra[i] || i)).join(", ") || "—"}</td></tr>`).join("") || `<tr><td colspan="8" class="empty">Nenhuma conta mudou.</td></tr>`}</tbody></table></div></div>`;
  await grafosLadoALado(r);
}

async function grafosLadoALado(r){
  const cytoscape = await carregarCytoscape();
  grafos.forEach(g => g.destroy());
  const d = r.diferencas;
  const ladoA = new Set(r.a.rede.arestas.map(a => `${a.de}>${a.para}`)), ladoB = new Set(r.b.rede.arestas.map(a => `${a.de}>${a.para}`));
  const ids = [...new Set([...r.a.contas, ...r.b.contas].map(c => c.id))].sort();
  const mudaram = new Set(d.destaques.mudaram_comunidade);
  // posições comuns: layout de forças sobre a UNIÃO das conexões dos dois lados
  const uniao = cytoscape({headless: true, styleEnabled: true, elements: [
    ...ids.map((id, i) => ({group: "nodes", data: {id, tam: 30}, position: posicaoInicial(r.b.contas.find(c => c.id === id) || r.a.contas.find(c => c.id === id), i, 10)})),
    ...[...new Set([...ladoA, ...ladoB])].map(k => { const [s, tg] = k.split(">"); return {group: "edges", data: {id: k, source: s, target: tg}}; })]});
  await new Promise(ok => { const l = uniao.layout({...LAYOUT, fit: false, boundingBox: {x1: 0, y1: 0, w: 1000, h: 700}}); l.one("layoutstop", ok); l.run(); });
  const pos = Object.fromEntries(uniao.nodes().map(n => [n.id(), {...n.position()}]));
  uniao.destroy();
  const maxValor = Math.max(1, ...[...r.a.rede.arestas, ...r.b.rede.arestas].map(a => a.valor_total));
  const montar = (lado, alvo, outro, classe) => {
    const contas = Object.fromEntries(lado.contas.map(c => [c.id, c]));
    const cy = cytoscape({container: el(alvo), wheelSensitivity: 0.25, minZoom: 0.1, maxZoom: 4, style: [...estilo("padrao"),
        {selector: "edge.nova", style: {"line-color": "#1E7A5A", "target-arrow-color": "#1E7A5A", width: 4}},
        {selector: "edge.removida", style: {"line-color": "#C2263C", "target-arrow-color": "#C2263C", "line-style": "dashed", width: 3}},
        {selector: "node.mudou", style: {"border-color": "#D99311", "border-width": 4}}],
      layout: {name: "preset", fit: true, padding: 20},
      elements: [
        ...ids.filter(id => contas[id]).map(id => ({group: "nodes", classes: mudaram.has(id) ? "mudou" : "", position: pos[id],
          data: {id, cor: corDe(contas[id], "risco", "padrao"), forma: "ellipse", tam: 20 + Math.min(contas[id].degree, 14) * 2.4}})),
        ...lado.rede.arestas.map(a => ({group: "edges", classes: outro.has(`${a.de}>${a.para}`) ? "" : classe,
          data: {id: `${a.de}>${a.para}`, source: a.de, target: a.para, largura: 1.2 + 4 * Math.sqrt(a.valor_total / maxValor)}}))]});
    cy.on("tap", "node", e => destacar(e.target.id()));
    cy.on("tap", e => { if(e.target === cy) destacar(null); });
    el(alvo).cy = cy;
    return cy;
  };
  grafos = [montar(r.a, "cmpGrafoA", ladoB, "removida"), montar(r.b, "cmpGrafoB", ladoA, "nova")];
}

function destacar(id){
  grafos.forEach(cy => cy.batch(() => {
    cy.elements().removeClass("apagado selecionado vizinha");
    if(!id || !cy.$id(id).length) return;
    const viz = cy.$id(id).closedNeighborhood();
    cy.elements().not(viz).addClass("apagado"); cy.$id(id).addClass("selecionado"); cy.$id(id).connectedEdges().addClass("vizinha");
  }));
  document.querySelectorAll("#cmpTabela tr").forEach(tr => tr.classList.toggle("aberta", tr.dataset.cmpConta === id));
}

/* ---------- ciclo de vida ---------- */
export function iniciar(){
  el("histTabs").addEventListener("click", e => { const b = e.target.closest("button[data-tab]"); if(b) abrirAba(b.dataset.tab); });
  ["cmpA", "cmpB"].forEach(id => el(id).addEventListener("change", () => alternarDatas(id)));
  el("cmpIr").addEventListener("click", () => comparar(fonteDe("cmpA"), fonteDe("cmpB")));
  el("cmpExemplo").addEventListener("click", () => {
    el("cmpA").value = "personalizado"; el("cmpAIni").value = "2026-08-01"; el("cmpAFim").value = "2026-08-15";
    el("cmpB").value = "personalizado"; el("cmpBIni").value = "2026-09-01"; el("cmpBFim").value = "2026-09-15";
    alternarDatas("cmpA"); alternarDatas("cmpB");
    comparar(fonteDe("cmpA"), fonteDe("cmpB"));
  });
  el("page-historico").addEventListener("click", e => {
    const ver = e.target.closest("[data-ver-cenario]");
    if(ver){ const id = ver.dataset.verCenario; preencherFontes(); el("cmpA").value = `cenario:${id}:base`; el("cmpB").value = `cenario:${id}`;
             alternarDatas("cmpA"); alternarDatas("cmpB"); abrirAba("comparar"); comparar(`cenario:${id}:base`, `cenario:${id}`); return; }
    const rest = e.target.closest("[data-restaurar-cenario]"); if(rest){ restaurar(rest.dataset.restaurarCenario); return; }
    const exc = e.target.closest("[data-excluir-cenario]"); if(exc){ excluir(exc.dataset.excluirCenario); return; }
    const linha = e.target.closest("[data-cmp-conta]"); if(linha && !e.target.closest("[data-conta]")) destacar(linha.dataset.cmpConta);
  });
  if(!pode("simular")){   // visualizador e auditor comparam períodos, mas não têm cenários
    el("histTabs").querySelector("[data-tab=cenarios]").hidden = true;
    abrirAba("comparar");
  }
}
export function atualizar(){ preencherFontes(); }
export function mostrar(){ carregarCenarios(); preencherFontes(); }
