/* NEXO — tela Rede de transações (Fase 3): grafo com Cytoscape.js e navegação estilo mapa
   (roda do mouse = zoom, arrastar o fundo = mover, localizar conta, vizinhança, ajustar à tela,
   minimapa), esquemas de cores com legenda (inclusive paleta segura para daltonismo), grafo de
   cada comunidade, animação dos padrões com as transações reais, matrizes e análise espectral. */
import {charts} from "../nucleo/graficos.js";
import {obterMatrizes} from "../nucleo/dados.js";
import {estado, ouvir} from "../nucleo/estado.js";
import {contasVisiveis, filtrosDeVisualizacaoAtivos} from "../nucleo/filtros.js";
import {ESQUEMAS, LAYOUT, carregarCytoscape, corDe, criarMinimapa, elementos, estilo, formaDe, legenda,
        papel, posicaoInicial} from "../nucleo/grafo.js";
import {prefs, salvar, semAnimacao} from "../nucleo/preferencias.js";
import {ui} from "../nucleo/ui.js";
import {corCom, el, esc, fmtBRL, fmtNum, pill, pillRisco} from "../nucleo/utilidades.js";
import {TIPOS, animar, ocorrencias} from "./rede-animacao.js";

/* ---------- preferências (Fase 5: no cadastro do usuário, em qualquer computador) ---------- */
let esquema = ESQUEMAS[prefs.grafo_esquema] ? prefs.grafo_esquema : "status";
let paleta = prefs.grafo_paleta || "padrao";
const salvarPref = () => salvar({grafo_esquema: esquema, grafo_paleta: paleta});
const dur = ms => semAnimacao() ? 0 : ms;   // "menos animação": o grafo pula direto para a posição

let cy = null, cytoscape = null, minimapa = null, mostrarRotulos = prefs.grafo_rotulos !== false;
let focoCom = "", selecionado = null, ajustarAoMostrar = false, versaoDesenhada = -1;
const posicoes = {};          // posições guardadas entre análises: a rede não "pula" após uma simulação

const grafoVisivel = () => el("page-rede").classList.contains("active") && el("tab-grafo").style.display !== "none";

/* ---------- grafo principal ---------- */
async function garantirGrafo(){
  if(cy) return cy;
  cytoscape = await carregarCytoscape();
  el("grafoCarregando").hidden = true;
  cy = cytoscape({container: el("graph"), wheelSensitivity: 0.25, minZoom: 0.12, maxZoom: 4, boxSelectionEnabled: false,
                  style: estilo(paleta, {rotulos: mostrarRotulos})});
  el("graph").cy = cy;   // usado pelos testes
  eventos();
  minimapa = criarMinimapa(cytoscape, cy, el("minimapa"));
  return cy;
}

async function desenhar(){
  if(!estado.dados) return;
  try{ await garantirGrafo(); }
  catch(err){ el("grafoCarregando").hidden = false; el("grafoCarregando").textContent = err.message; return; }
  const d = estado.dados;
  const simuladas = new Set(d.transacoes.filter(t => t.simulada).map(t => `${t.de}>${t.para}`));
  const novos = d.contas.filter(c => !posicoes[c.id]);
  cy.batch(() => {
    cy.elements().remove();
    cy.add(elementos(d.contas, d.rede.arestas, {esquema, paleta, simuladas}));
    d.contas.forEach((c, i) => cy.$id(c.id).position(posicoes[c.id] || posicaoInicial(c, i, d.comunidades.length)));
  });
  if(novos.length) organizar(novos.length === d.contas.length);
  else if(versaoDesenhada === -1) cy.fit(undefined, 30);
  versaoDesenhada = estado.versaoDados;
  if(selecionado && !cy.$id(selecionado).length) selecionado = null;
  realcar();
  minimapa.atualizar();
  if(!grafoVisivel()) ajustarAoMostrar = true;
}

function organizar(ajustar = true){
  const layout = cy.layout({...LAYOUT, fit: ajustar});
  layout.one("layoutstop", () => {
    cy.nodes().forEach(n => { posicoes[n.id()] = {...n.position()}; });
    minimapa.atualizar();
  });
  layout.run();
}

function colorir(){
  if(!cy) return;
  cy.batch(() => cy.nodes().not(".pulso").forEach(n => {
    const c = estado.porId[n.id()]; if(!c) return;
    n.data({cor: corDe(c, esquema, paleta), forma: formaDe(c, esquema, paleta)});
  }));
  el("legenda").innerHTML = legenda(esquema, paleta, estado.dados.comunidades);
  minimapa?.atualizar();
}

/* realce: filtros globais e "destacar comunidade" apagam o resto; a conta selecionada mostra a vizinhança */
function realcar(){
  if(!cy) return;
  const visiveis = new Set(contasVisiveis().map(c => c.id));
  cy.batch(() => {
    cy.elements().removeClass("apagado vizinha selecionado destaque");
    cy.nodes().forEach(n => {
      const c = estado.porId[n.id()];
      const fora = !visiveis.has(n.id()) || (focoCom && String(c.com) !== focoCom);
      if(fora) n.addClass("apagado");
      if(estado.destaque.has(n.id())) n.addClass("destaque");
    });
    cy.edges().forEach(e => { if(e.source().hasClass("apagado") || e.target().hasClass("apagado")) e.addClass("apagado"); });
    if(selecionado){
      const no = cy.$id(selecionado), viz = no.closedNeighborhood();
      cy.elements().not(viz).addClass("apagado");
      viz.removeClass("apagado"); no.addClass("selecionado"); no.connectedEdges().addClass("vizinha");
    }
  });
  const n = cy.nodes().not(".apagado").length;
  el("grafoInfo").textContent = selecionado
    ? `${selecionado}: ${cy.$id(selecionado).neighborhood("node").length} conta(s) conectada(s). Clique no fundo para ver toda a rede.`
    : (focoCom || filtrosDeVisualizacaoAtivos()) ? `${n} de ${cy.nodes().length} contas em destaque.` : `${cy.nodes().length} contas · ${cy.edges().length} conexões dirigidas.`;
}

function selecionar(id, aproximar = false){
  selecionado = id;
  realcar();
  if(id && aproximar) cy.animate({fit: {eles: cy.$id(id).closedNeighborhood(), padding: 80}}, {duration: dur(450)});
}

function eventos(){
  const tip = el("tip");
  cy.on("tap", "node", e => { if(e.target.hasClass("pulso")) return; selecionar(e.target.id()); painel(e.target.id()); });
  cy.on("dbltap", "node", e => cy.animate({center: {eles: e.target}, zoom: Math.max(cy.zoom() * 1.8, 1.6)}, {duration: dur(400)}));
  cy.on("tap", e => { if(e.target === cy && selecionado){ selecionar(null); } });
  cy.on("mouseover", "node", e => {
    const c = estado.porId[e.target.id()]; if(!c) return;
    const r = el("graph").getBoundingClientRect(), p = e.target.renderedPosition();
    tip.innerHTML = `<b>Conta ${c.id}</b>
      <div>Score<span>${fmtNum(c.score,1)}</span></div>
      <div>Prioridade de risco<span>${esc(c.nivel_risco)} (${c.risco})</span></div>
      <div>Papel<span>${esc(papel(c))}</span></div>
      <div>Degree<span>${c.degree} (${c.inDeg} in / ${c.outDeg} out)</span></div>
      <div>Betweenness<span>${fmtNum(c.betw,3)}</span></div>
      <div>Flow<span>${fmtBRL(c.flow)}</span></div>
      <div>Comunidade<span>${c.com}</span></div>`;
    tip.style.left = (r.left + p.x + 16) + "px"; tip.style.top = (r.top + p.y + 16) + "px"; tip.style.opacity = 1;
  });
  cy.on("mouseout", "node", () => { tip.style.opacity = 0; });
  cy.on("viewport", () => { tip.style.opacity = 0; });
  cy.on("dragfree", "node", e => { posicoes[e.target.id()] = {...e.target.position()}; });
}

/* ---------- painel lateral da conta ---------- */
function painel(id){
  const c = estado.porId[id];
  const envia = estado.dados.transacoes.filter(t=>t.de===id), recebe = estado.dados.transacoes.filter(t=>t.para===id);
  const unicos = l => [...new Set(l)].map(x => `<a href="#" data-localizar="${x}" class="mono-id">${x}</a>`).join(", ") || "—";
  ui.drawer(`Conta ${c.id}`, `
    <div style="margin-bottom:14px">${pill(c.status)} ${pillRisco(c.nivel_risco)} <span style="font-size:12px;color:var(--ink-3)">${esc(c.titular)} · ${esc(papel(c))}</span></div>
    <div class="grid g2" style="gap:10px">
      ${[["Score",fmtNum(c.score,1)],["Risco",c.risco],["Degree",c.degree],["Comunidade",c.com],["Betweenness",fmtNum(c.betw,3)],["Closeness",fmtNum(c.close,3)]]
        .map(([k,v])=>`<div class="kpi" style="padding:12px 14px;box-shadow:none"><h4>${k}</h4><div class="val" style="font-size:22px">${v}</div></div>`).join("")}
    </div>
    <p style="font-size:12.5px;color:var(--ink-2);margin:16px 0 4px"><strong>${c.inDeg}</strong> contas enviaram valores e <strong>${c.outDeg}</strong> contas receberam valores desta conta.</p>
    <p style="font-size:12.5px;color:var(--ink-2)">Entrada: <strong>${fmtBRL(c.entrada)}</strong> · Saída: <strong>${fmtBRL(c.saida)}</strong> · Imbalance ${fmtNum(c.imbalance,3)}</p>
    <p style="font-size:12.5px;color:var(--ink-2)">Recebe de: ${unicos(recebe.map(t=>t.de))}<br>Envia para: ${unicos(envia.map(t=>t.para))}</p>
    <button class="btn" style="width:100%;margin-top:12px" data-conta="${c.id}">Abrir detalhes da conta</button>
    <button class="btn ghost" style="width:100%;margin-top:8px" data-simular="${c.id}">Simular transação a partir desta conta</button>`);
}

function estatisticas(){
  const d = estado.dados, n = d.contas.length, m = d.rede.arestas.length;
  const top = [...d.contas].sort((a,b)=>b.betw-a.betw)[0];
  el("netStats").innerHTML = `
    <h3 style="margin:0 0 12px;font-size:14.5px">Resumo da rede</h3>
    <dl class="kv" style="grid-template-columns:190px 1fr;font-size:12.5px">
      <dt>Nós (contas)</dt><dd>${n}</dd>
      <dt>Conexões dirigidas distintas</dt><dd>${m}</dd>
      <dt>Transações</dt><dd>${d.transacoes.length}</dd>
      <dt>Densidade do grafo</dt><dd>${fmtNum(m/(n*(n-1)),3)}</dd>
      <dt>Maior intermediação</dt><dd><a href="#" data-localizar="${top.id}" class="mono-id">${top.id}</a> · betweenness ${fmtNum(top.betw,3)}</dd>
      <dt>Comunidades (Louvain)</dt><dd>${d.dashboard.total_comunidades} · modularidade ${fmtNum(d.dashboard.modularidade_louvain,3)}</dd>
      <dt>Componentes conexas</dt><dd>${d.espectral.componentes_conexas}</dd>
    </dl>`;
}

/* ---------- padrões: animáveis (com sequência no tempo) e estruturais ---------- */
function mini(tipo){
  const s = (pts, ligs) => `<svg viewBox="0 0 170 74" style="width:100%;max-width:200px;height:auto" aria-hidden="true">
    ${ligs.map(([a,b])=>`<line x1="${pts[a][0]}" y1="${pts[a][1]}" x2="${pts[b][0]}" y2="${pts[b][1]}" stroke="var(--ink-3)" stroke-width="1.4" marker-end="url(#setaMini)"/>`).join("")}
    ${pts.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="${p[2]||7}" fill="${p[3]||"var(--blue)"}"/>`).join("")}</svg>`;
  return {
    fan_in: s([[20,12],[20,37],[20,62],[130,37,11,"var(--amber)"]], [[0,3],[1,3],[2,3]]),
    fan_out: s([[30,37,11,"var(--amber)"],[140,12],[140,37],[140,62]], [[0,1],[0,2],[0,3]]),
    cadeia: s([[16,37],[62,37],[108,37],[152,37]], [[0,1],[1,2],[2,3]]),
    ciclo: s([[85,10],[140,37],[85,64],[30,37]], [[0,1],[1,2],[2,3],[3,0]]),
    repasse: s([[20,37],[85,37,11,"var(--amber)"],[150,20],[150,54]], [[0,1],[1,2],[1,3]]),
    Hub: s([[85,37,13,"var(--red)"],[18,12],[18,62],[152,12],[152,62],[85,6,6],[85,68,6]], [[1,0],[2,0],[0,3],[0,4],[5,0],[0,6]]),
    Ponte: s([[18,20],[18,54],[85,37,11,"var(--amber)"],[152,20],[152,54]], [[0,2],[1,2],[2,3],[2,4]])
  }[tipo];
}

let ocorrenciasAtuais = {};
function padroes(){
  const link = id => `<a href="#" data-localizar="${id}" class="mono-id">${id}</a>`;
  ocorrenciasAtuais = Object.fromEntries(Object.keys(TIPOS).map(t => [t, ocorrencias(t)]));
  const animaveis = Object.entries(TIPOS).map(([tipo, info]) => {
    const casos = ocorrenciasAtuais[tipo];
    const rotulo = oc => tipo === "cadeia" || tipo === "ciclo" ? oc.contas.map(link).join(" → ") : link(oc.conta);
    return `<div class="pattern"><h4>${esc(info.nome)} <span class="chip" style="margin-left:6px">${casos.length} ocorrência(s)</span></h4>
      <p>${esc(info.desc)}</p>${mini(tipo)}
      <ul class="lista-padroes">${casos.slice(0, 5).map((oc, i) => `
        <li><span>${rotulo(oc)} <small>${oc.transacoes.length} transação(ões)</small></span>
          <button class="btn ghost sm" data-animar="${tipo}:${i}" aria-label="Animar ${esc(info.nome)} ${oc.conta}">▶ Animar</button></li>`).join("")
        || `<li class="vazio">Nenhum caso no recorte atual.</li>`}
        ${casos.length > 5 ? `<li class="vazio">+ ${casos.length - 5} outros (veja no Painel de risco)</li>` : ""}</ul></div>`;
  }).join("");
  const estruturais = ["Hub", "Ponte"].map(tipo => {
    const casos = estado.dados.padroes.filter(p => p.tipo === tipo);
    const desc = tipo === "Hub" ? "Conta com grande número de conexões de entrada e saída." : "Conta com alta intermediação entre partes distintas da rede.";
    return `<div class="pattern"><h4>${tipo} <span class="chip" style="margin-left:6px">${casos.length} ocorrência(s)</span></h4><p>${desc} Padrão estrutural (sem sequência no tempo): clique para localizar no grafo.</p>
      ${mini(tipo)}<div style="font-size:12px;color:var(--ink-2);margin-top:10px;line-height:1.9">
      ${casos.map(p => tipo === "Hub" ? `${link(p.conta)} · degree ${p.exemplo}` : `${link(p.conta)} · betweenness ${fmtNum(p.exemplo,3)}`).join("<br>") || "Nenhum caso no período."}</div></div>`;
  }).join("");
  el("padroesGrid").innerHTML = `<svg width="0" height="0" style="position:absolute"><defs><marker id="setaMini" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="var(--ink-3)"/></marker></defs></svg>`
    + animaveis + estruturais;
}

/* ---------- comunidades: cartões e grafo individual ---------- */
function comunidades(){
  const d = estado.dados;
  el("comNota").innerHTML = `Comunidades obtidas pelo <strong>algoritmo de Louvain</strong> (NetworkX, grafo não direcionado, peso = número de transferências, semente 42). Modularidade: <strong>${fmtNum(d.dashboard.modularidade_louvain,3)}</strong>. O resultado pode diferir das comunidades planejadas na planilha.`;
  el("comunidadesGrid").innerHTML = d.comunidades.map(g=>`
    <div class="card" style="border-top:3px solid ${corCom(g.id)}"><div class="card-head"><div><h3>Comunidade ${g.id}</h3><p>${g.contas.join(" · ")}</p></div></div>
      <div class="card-body"><dl class="kv" style="grid-template-columns:160px 1fr;font-size:12.5px">
        <dt>Contas</dt><dd>${g.quantidade_contas}</dd>
        <dt>Transações incidentes</dt><dd>${g.quantidade_transacoes_incidentes} (${g.quantidade_transacoes_internas} internas)</dd>
        <dt>Volume incidente</dt><dd>${fmtBRL(g.volume_incidente)}</dd>
        <dt>Volume interno</dt><dd>${fmtBRL(g.volume_interno)}</dd>
        <dt>Conta mais conectada</dt><dd><a href="#" data-conta="${g.conta_mais_conectada}" class="mono-id">${g.conta_mais_conectada}</a> (degree ${estado.porId[g.conta_mais_conectada].degree})</dd>
      </dl>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
        <button class="btn sm" data-grafo-com="${g.id}">Ver grafo da comunidade</button>
        <button class="btn ghost sm" data-focar-com="${g.id}">Destacar na rede</button></div></div></div>`).join("");
  const atual = el("focoCom").value;
  el("focoCom").innerHTML = `<option value="">Nenhuma</option>` + d.comunidades.map(c=>`<option value="${c.id}">Comunidade ${c.id}</option>`).join("");
  el("focoCom").value = d.comunidades.some(c=>String(c.id)===atual) ? atual : "";
  focoCom = el("focoCom").value;
}

let cyComunidade = null;
async function grafoComunidade(id){
  const d = estado.dados, g = d.comunidades.find(c => c.id === +id);
  const membros = new Set(g.contas);
  const internas = d.rede.arestas.filter(a => membros.has(a.de) && membros.has(a.para));
  const externas = d.rede.arestas.filter(a => membros.has(a.de) !== membros.has(a.para));
  const linhas = g.contas.map(cid => estado.porId[cid]).sort((a, b) => b.degree - a.degree).map(c => {
    const ent = internas.filter(a => a.para === c.id).reduce((s, a) => s + a.valor_total, 0);
    const sai = internas.filter(a => a.de === c.id).reduce((s, a) => s + a.valor_total, 0);
    return `<tr class="clickable" data-conta="${c.id}"><td class="mono-id">${c.id}</td><td class="num">${c.degree}</td>
      <td class="num">${fmtBRL(ent)}</td><td class="num">${fmtBRL(sai)}</td><td>${pillRisco(c.nivel_risco)}</td></tr>`;
  }).join("");
  ui.modal(`Comunidade ${g.id}`, `
    <p style="margin:0 0 10px;font-size:13px;color:var(--ink-2)">${g.quantidade_contas} contas · ${internas.length} conexões internas
      (${fmtBRL(g.volume_interno)}) · ${externas.length} conexão(ões) com outras comunidades (fora do desenho).</p>
    <div class="anim-palco"><div id="grafoCom" class="anim-grafo" role="img" aria-label="Grafo da comunidade ${g.id}"></div></div>
    <div class="table-wrap" style="margin-top:12px"><table><thead><tr><th>Conta</th><th class="num">Degree</th>
      <th class="num">Recebido na comunidade</th><th class="num">Enviado na comunidade</th><th>Prioridade</th></tr></thead><tbody>${linhas}</tbody></table></div>`);
  const cyt = await carregarCytoscape();
  if(!el("grafoCom")) return;
  cyComunidade?.destroy();
  cyComunidade = cyt({container: el("grafoCom"), wheelSensitivity: 0.25, style: estilo(paleta, {rotulos: true}),
    // dentro da comunidade, a cor mostra a prioridade de risco (todas já são da mesma comunidade)
    elements: elementos(g.contas.map(cid => estado.porId[cid]), internas, {esquema: esquema === "com" ? "risco" : esquema, paleta})});
  el("grafoCom").cy = cyComunidade;
  cyComunidade.layout({...LAYOUT, fit: true, padding: 40, numIter: 800}).run();
}

const descMatriz = {
  A:"Adjacência dirigida: 1 em (i, j) indica que a conta da linha transferiu para a da coluna.",
  W:"Pesos: soma em R$ transferida da linha para a coluna (valores em milhares).",
  D:"Grau de saída de cada conta na diagonal.",
  L:"Laplaciana dirigida L = D − A (não simétrica).",
  A_simetrica:"Adjacência sem direção: base da análise espectral.",
  L_simetrica:"Laplaciana simétrica Ls = Ds − As, usada em L v = λ v."
};

async function matrizes(){
  if(el("tab-matriz").style.display === "none") return;   // só monta a tabela quando a aba está aberta
  const versao = estado.versaoDados;
  let m;
  try{ m = await obterMatrizes(); } catch(err){ ui.toast(esc(err.message), true); return; }
  if(versao !== estado.versaoDados) return;               // chegou uma análise mais nova no meio do caminho
  const nome = el("matSel").value, ids = m.ordem_contas, M = m[nome];
  el("matTitulo").textContent = `Matriz ${nome.replace("_simetrica"," simétrica")} — ${ids.length} × ${ids.length}`;
  el("matDesc").textContent = descMatriz[nome];
  const maxW = Math.max(...M.flat().map(Math.abs), 1);
  const celula = (v,i,j) => {
    if(!v) return `<td style="color:var(--ink-3);opacity:.35">0</td>`;
    if(i===j) return `<td class="diagd" title="${ids[i]}">${v}</td>`;
    if(nome==="W"){
      const a = (0.15 + 0.85*v/maxW).toFixed(2);
      return `<td style="background:rgba(27,95,168,${a});color:${a>0.55?"#fff":"var(--ink)"}" title="${ids[i]} → ${ids[j]}: ${fmtBRL(v)}">${(v/1000).toFixed(1)}</td>`;
    }
    return `<td class="one" title="${ids[i]} → ${ids[j]}">${v}</td>`;
  };
  el("matFull").innerHTML = `<table class="matrix heat"><thead><tr><th></th>${ids.map(i=>`<th>${i.slice(1)}</th>`).join("")}</tr></thead><tbody>
    ${M.map((linha,i)=>`<tr><th>${ids[i]}</th>${linha.map((v,j)=>celula(v,i,j)).join("")}</tr>`).join("")}</tbody></table>`;

  const e = estado.dados.espectral, av = e.autovalores;
  charts.barras(el("chartEig"), av.map((v,i)=>({rotulo:`λ${i+1}`, valor:v, cor: v<1e-8?"var(--amber)":"var(--blue)"})),
    v=>fmtNum(v,4), v=>fmtNum(v,1));
  const zeros = av.filter(v=>v<1e-8).length;
  el("espectralInfo").innerHTML = `<dl class="kv" style="grid-template-columns:200px 1fr;font-size:12.5px">
      <dt>Matriz utilizada</dt><dd>${esc(e.matriz_utilizada)}</dd>
      <dt>Equação</dt><dd>${esc(e.equacao)}</dd>
      <dt>Autovalores iguais a zero</dt><dd>${zeros}</dd>
      <dt>Componentes conexas</dt><dd>${e.componentes_conexas} ${zeros===e.componentes_conexas?"✔ confere":"✖ diverge"}</dd>
      <dt>λ₂ (conectividade algébrica)</dt><dd>${fmtNum(e.segundo_menor_autovalor,6)}</dd>
      <dt>Maior autovalor</dt><dd>${fmtNum(av[av.length-1],4)}</dd>
    </dl>
    <p style="font-size:12.5px;color:var(--ink-2);margin:14px 0 0">O número de autovalores nulos da Laplaciana é igual ao número de componentes conexas. λ₂ = 0 indica rede desconexa; isso descreve a estrutura, não risco.</p>
    <p style="font-size:12px;color:var(--ink-3)">${esc(e.observacao)}</p>`;
}


/* ---------- ciclo de vida da tela ---------- */
function abrirAba(nome){
  [...el("redeTabs").children].forEach(x => x.classList.toggle("active", x.dataset.tab === nome));
  ["grafo","padroes","comunidades","matriz"].forEach(t => el("tab-"+t).style.display = t === nome ? "" : "none");
  if(nome === "matriz") matrizes();
  if(nome === "grafo") mostrar();
}

function localizar(id){
  id = String(id || "").trim().toUpperCase();
  if(!estado.porId[id]){ ui.toast(`Conta ${esc(id)} não encontrada nesta análise.`, true); return; }
  ui.closeDrawer(); ui.closeModal();
  abrirAba("grafo");
  selecionar(id, true);
}

export function iniciar(){
  el("redeTabs").addEventListener("click", e=>{
    const b = e.target.closest("button[data-tab]"); if(b) abrirAba(b.dataset.tab);
  });
  el("matSel").addEventListener("change", matrizes);
  el("corPor").innerHTML = Object.entries(ESQUEMAS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  el("corPor").value = esquema; el("paleta").value = paleta;
  el("corPor").addEventListener("change", e => { esquema = e.target.value; salvarPref(); colorir(); });
  el("paleta").addEventListener("change", e => { paleta = e.target.value; salvarPref(); cy?.style(estilo(paleta, {rotulos: mostrarRotulos})); colorir(); });
  el("focoCom").addEventListener("change", e => { focoCom = e.target.value; selecionado = null; realcar();
    if(cy && focoCom) cy.animate({fit: {eles: cy.nodes().not(".apagado"), padding: 60}}, {duration: dur(400)}); });
  el("buscaConta").addEventListener("change", e => { if(e.target.value) localizar(e.target.value); });
  el("buscaConta").addEventListener("keydown", e => { if(e.key === "Enter"){ e.preventDefault(); localizar(e.target.value); } });
  // stop(): um clique durante a animação de "ajustar" não pode ser sobrescrito por ela
  const zoomPor = f => { if(!cy) return; cy.stop(true, true);
    cy.zoom({level: cy.zoom() * f, renderedPosition: {x: cy.width() / 2, y: cy.height() / 2}}); };
  el("zIn").onclick = () => zoomPor(1.3);
  el("zOut").onclick = () => zoomPor(1 / 1.3);
  el("zFit").onclick = () => cy?.animate({fit: {padding: 30}}, {duration: dur(350)});
  el("zCentro").onclick = () => { if(!cy) return;
    selecionado ? cy.animate({fit: {eles: cy.$id(selecionado).closedNeighborhood(), padding: 80}}, {duration: dur(350)})
                : ui.toast("Clique numa conta (ou use “Localizar conta”) para centralizar nela."); };
  el("zReset").onclick = () => { if(!cy) return; Object.keys(posicoes).forEach(k => delete posicoes[k]);
    estado.dados.contas.forEach((c, i) => cy.$id(c.id).position(posicaoInicial(c, i, estado.dados.comunidades.length))); organizar(true); };
  el("page-rede").addEventListener("click", e => {
    const anim = e.target.closest("[data-animar]");
    if(anim){ const [tipo, i] = anim.dataset.animar.split(":"); animar(ocorrenciasAtuais[tipo][+i]); return; }
    const gc = e.target.closest("[data-grafo-com]"); if(gc){ grafoComunidade(gc.dataset.grafoCom); return; }
    const fc = e.target.closest("[data-focar-com]");
    if(fc){ el("focoCom").value = fc.dataset.focarCom; abrirAba("grafo"); el("focoCom").dispatchEvent(new Event("change")); }
  });
  // "localizar" também funciona a partir do painel lateral e das janelas
  document.addEventListener("click", e => {
    const loc = e.target.closest("[data-localizar]");
    if(loc){ e.preventDefault(); e.stopPropagation(); localizar(loc.dataset.localizar); }
  }, true);
  ouvir("tema", () => { if(cy){ cy.style(estilo(paleta, {rotulos: mostrarRotulos})); minimapa = criarMinimapa(cytoscape, cy, el("minimapa")); minimapa.atualizar(); } });
  ouvir("rotulos", v => { mostrarRotulos = v; cy?.style(estilo(paleta, {rotulos: v})); });
  ouvir("preferencias", p => {   // mudou em Configurações ou em outro lugar
    if(p.grafo_esquema === esquema && p.grafo_paleta === paleta) return;
    const novaPaleta = p.grafo_paleta !== paleta;
    esquema = ESQUEMAS[p.grafo_esquema] ? p.grafo_esquema : "status"; paleta = p.grafo_paleta;
    el("corPor").value = esquema; el("paleta").value = paleta;
    if(novaPaleta) cy?.style(estilo(paleta, {rotulos: mostrarRotulos}));
    colorir();
  });
}

export async function atualizar(){
  legendaEDados();
  await desenhar();
}
function legendaEDados(){
  el("legenda").innerHTML = legenda(esquema, paleta, estado.dados.comunidades);
  el("listaContas").innerHTML = estado.dados.contas.map(c => `<option value="${c.id}">`).join("");
  estatisticas(); padroes(); comunidades(); matrizes();
}

/* a tela (ou a aba Grafo) ficou visível: o canvas precisa saber o tamanho real */
export function mostrar(){
  if(!cy || !grafoVisivel()) return;
  requestAnimationFrame(() => {
    cy.resize();
    if(ajustarAoMostrar){ cy.fit(undefined, 30); ajustarAoMostrar = false; }
    minimapa.atualizar();
  });
}
export const reclassificar = () => colorir();
export const filtrar = () => realcar();
export const casos = () => {};
