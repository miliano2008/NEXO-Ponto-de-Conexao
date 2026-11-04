/* NEXO — tela Rede de transações: grafo (layout de forças animado em SVG), padrões,
   comunidades, matrizes e análise espectral. */
import {charts} from "../nucleo/graficos.js";
import {obterMatrizes} from "../nucleo/dados.js";
import {estado, ouvir} from "../nucleo/estado.js";
import {ui} from "../nucleo/ui.js";
import {corCom, corStatus, el, esc, fmtBRL, fmtNum, pill} from "../nucleo/utilidades.js";

const W=1000, H=620;
let nos = [], arestas = [], zoom = 1, mostrarRotulos = true, corPor = "status", focoCom = "";
let arrastando = null, animacao = null;
const posicoes = {};   // mantém posições entre recálculos: a rede "se move" após uma simulação

function preparar(reiniciar=false){
  const d = estado.dados, nCom = d.comunidades.length || 1;
  nos = d.contas.map((c,i)=>{
    const p = !reiniciar && posicoes[c.id];
    if(p) return {...c, x:p.x, y:p.y};
    // posição inicial agrupada por comunidade para o layout convergir mais rápido
    const a = ((c.com-1)/nCom)*Math.PI*2, j = (i*2.399)%(Math.PI*2);
    return {...c, x: W/2 + Math.cos(a)*260 + Math.cos(j)*45, y: H/2 + Math.sin(a)*200 + Math.sin(j)*45};
  });
  const porId = Object.fromEntries(nos.map(n=>[n.id,n]));
  const simuladas = new Set(d.transacoes.filter(t=>t.simulada).map(t=>t.de+">"+t.para));
  arestas = d.rede.arestas.map(a=>({de:porId[a.de], para:porId[a.para], qtd:a.quantidade, valor:a.valor_total,
    sim: simuladas.has(a.de+">"+a.para)}));
}

// Fruchterman–Reingold, executado em pequenos passos por quadro (animação)
function passo(temp){
  const k = Math.sqrt((W*H)/nos.length)*0.50;
  nos.forEach(v=>{v.dx=0; v.dy=0;});
  for(let i=0;i<nos.length;i++) for(let j=i+1;j<nos.length;j++){
    const a=nos[i], b=nos[j];
    let dx=a.x-b.x, dy=a.y-b.y, d=Math.hypot(dx,dy)||0.01;
    // repulsão extra quando os círculos (e rótulos) se sobrepõem
    const f = (k*k)/d * (d < raio(a)+raio(b)+22 ? 4 : 1); dx/=d; dy/=d;
    a.dx+=dx*f; a.dy+=dy*f; b.dx-=dx*f; b.dy-=dy*f;
  }
  arestas.forEach(e=>{
    let dx=e.de.x-e.para.x, dy=e.de.y-e.para.y, d=Math.hypot(dx,dy)||0.01;
    const f=(d*d)/k; dx/=d; dy/=d;
    e.de.dx-=dx*f; e.de.dy-=dy*f; e.para.dx+=dx*f; e.para.dy+=dy*f;
  });
  nos.forEach(v=>{
    // leve gravidade ao centro: componentes desconexas não fogem da tela
    v.dx += (W/2-v.x)*0.25; v.dy += (H/2-v.y)*0.45;
    if(arrastando && arrastando.no===v) return;
    const d = Math.hypot(v.dx,v.dy)||0.01;
    v.x = Math.max(55, Math.min(W-90, v.x + (v.dx/d)*Math.min(d,temp)));
    v.y = Math.max(45, Math.min(H-45, v.y + (v.dy/d)*Math.min(d,temp)));
    posicoes[v.id] = {x:v.x, y:v.y};
  });
}

function animar(iteracoes=300, temp0=W/10){
  cancelAnimationFrame(animacao);
  let it = 0, temp = temp0;
  const quadro = () => {
    for(let s=0; s<6 && it<iteracoes; s++, it++){ passo(temp); temp *= 0.985; }
    desenhar();
    if(it<iteracoes) animacao = requestAnimationFrame(quadro);
  };
  quadro();
}

const raio = n => 8 + Math.min(n.degree,14)*1.25;
const corNo = n => corPor==="com" ? corCom(n.com) : corStatus(estado.porId[n.id].status);

function desenhar(){
  const svg = el("graph");
  if(!nos.length) return;
  const maior = nos.reduce((a,b)=>a.score>b.score?a:b);
  const cores = ["var(--ink-3)","var(--amber)","var(--red)","var(--green)"];
  const defs = `<defs>${cores.map((c,i)=>
      `<marker id="seta${i}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
         <path d="M0,0 L10,5 L0,10 Z" fill="${c}"/></marker>`).join("")}</defs>`;
  const apagado = n => focoCom && String(n.com)!==focoCom;

  const linhas = arestas.map(e=>{
    const r2 = raio(e.para)+6, dx=e.para.x-e.de.x, dy=e.para.y-e.de.y, d=Math.hypot(dx,dy)||1;
    const x2 = e.para.x - (dx/d)*r2, y2 = e.para.y - (dy/d)*r2;
    const x1 = e.de.x + (dx/d)*(raio(e.de)+2), y1 = e.de.y + (dy/d)*(raio(e.de)+2);
    const st = [estado.porId[e.de.id].status, estado.porId[e.para.id].status];
    let alerta = st.includes("Alta relevância") ? 2 : st.includes("Em análise") ? 1 : 0;
    if(e.sim) alerta = 3;
    const cor = ["var(--line)","var(--amber)","var(--red)","var(--green)"][alerta];
    const op = (apagado(e.de)||apagado(e.para)) ? .12 : .85;
    return `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}"
      stroke="${cor}" stroke-width="${e.sim?3:1 + Math.min(e.valor/15000,2.2)}" ${e.sim?'stroke-dasharray="6 4"':""} marker-end="url(#seta${alerta})" opacity="${op}"><title>${e.de.id} → ${e.para.id}: ${e.qtd} transação(ões) · ${fmtBRL(e.valor)}</title></line>`;
  }).join("");

  const circulos = nos.map(n=>{
    const r = raio(n), destaque = n.id===maior.id || estado.destaque.has(n.id);
    const cor = corNo(n);
    return `<g class="node" data-id="${n.id}" transform="translate(${n.x.toFixed(1)},${n.y.toFixed(1)})" opacity="${apagado(n)?.18:1}">
      ${destaque?`<circle r="${r+7}" fill="none" stroke="${estado.destaque.has(n.id)?"var(--green)":cor}" stroke-width="2" opacity=".6"/>`:""}
      <circle r="${r}" fill="${cor}" stroke="var(--surface)" stroke-width="2.5"/>
      <text y="3.5" text-anchor="middle" style="fill:#fff" font-size="9">${n.degree}</text>
      ${mostrarRotulos?`<text y="${r+12}" text-anchor="middle">${n.id}</text>`:""}
    </g>`;
  }).join("");

  const cx=W/2, cy=H/2, s=zoom;
  svg.setAttribute("viewBox", `${cx-(W/2)/s} ${cy-(H/2)/s} ${W/s} ${H/s}`);
  svg.innerHTML = defs + `<g>${linhas}</g><g>${circulos}</g>`;
}

function legenda(){
  el("legenda").innerHTML = corPor==="com"
    ? estado.dados.comunidades.map(c=>`<span><i style="background:${corCom(c.id)}"></i>Comunidade ${c.id}</span>`).join("")
    : `<span><i style="background:var(--blue)"></i>Normal / Revisar</span>
       <span><i style="background:var(--amber)"></i>Em análise</span>
       <span><i style="background:var(--red)"></i>Alta relevância estrutural</span>
       <span><i style="background:var(--green)"></i>Conexão simulada</span>`;
}

function painel(id){
  const c = estado.porId[id];
  const envia = estado.dados.transacoes.filter(t=>t.de===id), recebe = estado.dados.transacoes.filter(t=>t.para===id);
  const unicos = l => [...new Set(l)].join(", ") || "—";
  ui.drawer(`Conta ${c.id}`, `
    <div style="margin-bottom:14px">${pill(c.status)} <span style="font-size:12px;color:var(--ink-3)">${esc(c.titular)}</span></div>
    <div class="grid g2" style="gap:10px">
      ${[["Score",fmtNum(c.score,1)],["Ranking","#"+c.ranking],["Degree",c.degree],["Comunidade",c.com],["Betweenness",fmtNum(c.betw,3)],["Closeness",fmtNum(c.close,3)]]
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
      <dt>Maior intermediação</dt><dd><a href="#" data-conta="${top.id}" class="mono-id">${top.id}</a> · betweenness ${fmtNum(top.betw,3)}</dd>
      <dt>Comunidades (Louvain)</dt><dd>${d.dashboard.total_comunidades} · modularidade ${fmtNum(d.dashboard.modularidade_louvain,3)}</dd>
      <dt>Componentes conexas</dt><dd>${d.espectral.componentes_conexas}</dd>
    </dl>`;
}

function interacoes(){
  const svg = el("graph"), tip = el("tip");
  svg.addEventListener("mousemove", e=>{
    const g = e.target.closest(".node");
    if(!g || arrastando){ tip.style.opacity=0; return; }
    const c = estado.porId[g.dataset.id];
    tip.innerHTML = `<b>Conta ${c.id}</b>
      <div>Score<span>${fmtNum(c.score,1)}</span></div>
      <div>Degree<span>${c.degree} (${c.inDeg} in / ${c.outDeg} out)</span></div>
      <div>Betweenness<span>${fmtNum(c.betw,3)}</span></div>
      <div>Closeness<span>${fmtNum(c.close,3)}</span></div>
      <div>Flow<span>${fmtBRL(c.flow)}</span></div>
      <div>Comunidade<span>${c.com}</span></div>
      <div>Status<span>${c.status}</span></div>`;
    tip.style.left = (e.clientX+14)+"px"; tip.style.top = (e.clientY+14)+"px"; tip.style.opacity=1;
  });
  svg.addEventListener("mouseleave", ()=> tip.style.opacity=0);

  const pos = e => {
    const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
    return {x: vb.x + (e.clientX-r.left)/r.width*vb.width, y: vb.y + (e.clientY-r.top)/r.height*vb.height};
  };
  svg.addEventListener("pointerdown", e=>{
    const g = e.target.closest(".node"); if(!g) return;
    arrastando = {no: nos.find(n=>n.id===g.dataset.id), movido:false};
    svg.setPointerCapture(e.pointerId);
  });
  svg.addEventListener("pointermove", e=>{
    if(!arrastando) return;
    const p = pos(e); arrastando.no.x = p.x; arrastando.no.y = p.y; arrastando.movido = true;
    posicoes[arrastando.no.id] = {x:p.x, y:p.y};
    desenhar();
  });
  svg.addEventListener("pointerup", ()=>{
    if(arrastando && !arrastando.movido) painel(arrastando.no.id);
    arrastando = null;
  });

  el("zIn").onclick = ()=>{ zoom = Math.min(zoom*1.2, 2.6); desenhar(); };
  el("zOut").onclick = ()=>{ zoom = Math.max(zoom/1.2, 0.6); desenhar(); };
  el("zReset").onclick = ()=>{ zoom = 1; preparar(true); animar(); };
  el("corPor").onchange = e=>{ corPor = e.target.value; legenda(); desenhar(); };
  el("focoCom").onchange = e=>{ focoCom = e.target.value; desenhar(); };
}

/* ---- padrões, comunidades e matrizes ---- */
function mini(tipo){
  const s = (pts, ligs) => `<svg viewBox="0 0 170 74" style="width:100%;max-width:200px;height:auto">
    ${ligs.map(([a,b])=>`<line x1="${pts[a][0]}" y1="${pts[a][1]}" x2="${pts[b][0]}" y2="${pts[b][1]}" stroke="var(--ink-3)" stroke-width="1.4" marker-end="url(#setaMini)"/>`).join("")}
    ${pts.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="${p[2]||7}" fill="${p[3]||"var(--blue)"}"/>`).join("")}</svg>`;
  return {
    "Fan-in": s([[20,12],[20,37],[20,62],[130,37,11,"var(--amber)"]], [[0,3],[1,3],[2,3]]),
    "Fan-out": s([[30,37,11,"var(--amber)"],[140,12],[140,37],[140,62]], [[0,1],[0,2],[0,3]]),
    "Cadeia de repasse": s([[16,37],[62,37],[108,37],[152,37]], [[0,1],[1,2],[2,3]]),
    "Hub": s([[85,37,13,"var(--red)"],[18,12],[18,62],[152,12],[152,62],[85,6,6],[85,68,6]], [[1,0],[2,0],[0,3],[0,4],[5,0],[0,6]]),
    "Ponte": s([[18,20],[18,54],[85,37,11,"var(--amber)"],[152,20],[152,54]], [[0,2],[1,2],[2,3],[2,4]])
  }[tipo];
}

function padroes(){
  const desc = {
    "Fan-in":"Muitas contas distintas enviando para uma única conta.",
    "Fan-out":"Uma conta distribuindo valores para várias contas distintas.",
    "Cadeia de repasse":"O valor passa por contas em sequência: conta → conta → conta → conta.",
    "Hub":"Conta com grande número de conexões de entrada e saída.",
    "Ponte":"Conta com alta intermediação entre partes distintas da rede."
  };
  const link = id => `<a href="#" data-conta="${id}" class="mono-id">${id}</a>`;
  const texto = p => p.tipo==="Fan-in" ? `${p.exemplo.join(", ")} → ${link(p.conta)}`
    : p.tipo==="Fan-out" ? `${link(p.conta)} → ${p.exemplo.join(", ")}`
    : p.tipo==="Cadeia de repasse" ? p.exemplo.map(link).join(" → ")
    : p.tipo==="Hub" ? `${link(p.conta)} · degree ${p.exemplo}`
    : `${link(p.conta)} · betweenness ${fmtNum(p.exemplo,3)}`;
  el("padroesGrid").innerHTML = `<svg width="0" height="0" style="position:absolute"><defs><marker id="setaMini" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="var(--ink-3)"/></marker></defs></svg>` +
    Object.keys(desc).map(tipo=>{
      const casos = estado.dados.padroes.filter(p=>p.tipo===tipo);
      return `<div class="pattern"><h4>${tipo} <span class="chip" style="margin-left:6px">${casos.length} ocorrência(s)</span></h4><p>${desc[tipo]}</p>
        ${mini(tipo)}
        <div style="font-size:12px;color:var(--ink-2);margin-top:10px;line-height:1.9">${casos.slice(0,4).map(texto).join("<br>") || "Nenhum caso no período."}
        ${casos.length>4?`<br><span style="color:var(--ink-3)">+ ${casos.length-4} outros</span>`:""}</div>
        <div class="chip-row" style="margin-top:10px"><span class="chip">Critério: ${esc(casos[0]?.criterio || "—")}</span></div></div>`;
    }).join("");
}

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
      </dl></div></div>`).join("");
  const atual = el("focoCom").value;
  el("focoCom").innerHTML = `<option value="">Nenhuma</option>` + d.comunidades.map(c=>`<option value="${c.id}">Comunidade ${c.id}</option>`).join("");
  el("focoCom").value = d.comunidades.some(c=>String(c.id)===atual) ? atual : "";
  focoCom = el("focoCom").value;
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

export function iniciar(){
  interacoes();
  el("redeTabs").addEventListener("click", e=>{
    const b = e.target.closest("button[data-tab]"); if(!b) return;
    [...el("redeTabs").children].forEach(x=>x.classList.toggle("active", x===b));
    ["grafo","padroes","comunidades","matriz"].forEach(t =>
      el("tab-"+t).style.display = t===b.dataset.tab ? "" : "none");
    if(b.dataset.tab === "matriz") matrizes();
  });
  el("matSel").addEventListener("change", matrizes);
  ouvir("tema", () => desenhar());
  ouvir("rotulos", rotulos);
}
export function atualizar(){
  const primeira = !Object.keys(posicoes).length;
  preparar(); legenda(); estatisticas(); padroes(); comunidades(); matrizes();
  primeira ? animar(320) : animar(90, 18);
}
function rotulos(v){ mostrarRotulos = v; desenhar(); }

export const reclassificar = () => desenhar();
export const mostrar = () => desenhar();
