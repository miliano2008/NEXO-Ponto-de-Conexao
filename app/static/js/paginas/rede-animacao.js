/* NEXO — animação dos padrões (Fase 3): reproduz as transações REAIS de um padrão, em ordem
   cronológica, com o valor e a data na seta e um ponto percorrendo cada ligação.
   Controles: reproduzir/pausar, anterior, próximo, reiniciar e velocidade.
   Não é um GIF: o desenho usa os dados da análise atual (recorte e simulações incluídos). */
import {estado} from "../nucleo/estado.js";
import {carregarCytoscape, corDe, estilo} from "../nucleo/grafo.js";
import {ui} from "../nucleo/ui.js";
import {el, esc, fmtBRL, fmtData} from "../nucleo/utilidades.js";

export const TIPOS = {
  fan_in: {nome: "Recebimentos concentrados (fan-in)", desc: "Várias contas enviam para a mesma conta."},
  fan_out: {nome: "Envios dispersos (fan-out)", desc: "Uma conta distribui valores para várias contas."},
  cadeia: {nome: "Cadeia de repasse", desc: "Cada transferência sai da conta que acabou de receber, em ordem cronológica."},
  ciclo: {nome: "Circuito recorrente", desc: "As transferências formam um circuito que volta à conta de origem, e as ligações se repetem."},
  repasse: {nome: "Repasse rápido", desc: "A conta recebe um valor e reenvia a maior parte logo em seguida."},
};

const quando = t => `${t.data}T${t.hora}`;

/* ocorrências de cada tipo a partir dos indícios do backend, sem repetir a mesma cadeia/circuito */
export function ocorrencias(tipo){
  const d = estado.dados, vistos = new Set(), lista = [];
  const porTx = Object.fromEntries(d.transacoes.map(t => [t.id, t]));
  for(const [conta, info] of Object.entries(d.risco.contas)){
    const ind = info.indicios.find(i => i.regra === tipo);
    if(!ind) continue;
    let transacoes;
    if(tipo === "fan_in") transacoes = d.transacoes.filter(t => t.para === conta && ind.contas.includes(t.de));
    else if(tipo === "fan_out") transacoes = d.transacoes.filter(t => t.de === conta && ind.contas.includes(t.para));
    else transacoes = (ind.transacoes || []).map(id => porTx[id]).filter(Boolean);
    const contas = tipo === "cadeia" || tipo === "ciclo" ? ind.contas : [conta];
    const chave = tipo === "cadeia" || tipo === "ciclo" ? [...new Set(contas)].sort().join(",") + "|" + tipo : conta;
    if(vistos.has(chave) || !transacoes.length) continue;
    vistos.add(chave);
    lista.push({tipo, conta, contas, evidencia: ind.evidencia,
                transacoes: [...transacoes].sort((a, b) => quando(a).localeCompare(quando(b)))});
  }
  return lista.sort((a, b) => b.transacoes.length - a.transacoes.length || a.conta.localeCompare(b.conta));
}

/* posições fixas por tipo de padrão: o desenho explica o padrão sozinho */
function posicoes(oc){
  const envolvidas = [...new Set(oc.transacoes.flatMap(t => [t.de, t.para]))];
  const pos = {};
  if(oc.tipo === "cadeia"){
    const ordem = oc.contas.filter((c, i, a) => a.indexOf(c) === i);
    envolvidas.filter(c => !ordem.includes(c)).forEach(c => ordem.push(c));
    ordem.forEach((c, i) => { pos[c] = {x: i * 150, y: (i % 2) * 40}; });
  } else if(oc.tipo === "ciclo"){
    const ordem = oc.contas.slice(0, -1);
    ordem.forEach((c, i) => { const a = -Math.PI / 2 + i * 2 * Math.PI / ordem.length; pos[c] = {x: Math.cos(a) * 170, y: Math.sin(a) * 140}; });
  } else {
    const centro = oc.conta, outras = envolvidas.filter(c => c !== centro);
    pos[centro] = {x: 0, y: 0};
    if(oc.tipo === "repasse"){
      const entram = outras.filter(c => oc.transacoes.some(t => t.de === c && t.para === centro));
      const saem = outras.filter(c => !entram.includes(c));
      entram.forEach((c, i) => { pos[c] = {x: -220, y: (i - (entram.length - 1) / 2) * 110}; });
      saem.forEach((c, i) => { pos[c] = {x: 220, y: (i - (saem.length - 1) / 2) * 110}; });
    } else {
      const lado = oc.tipo === "fan_in" ? -1 : 1;
      outras.forEach((c, i) => {
        const a = (i - (outras.length - 1) / 2) * (Math.PI / 1.6) / Math.max(outras.length - 1, 1);
        pos[c] = {x: lado * Math.cos(a) * 240, y: Math.sin(a) * 240};
      });
    }
  }
  return pos;
}

let reprodutor = null;

export async function animar(oc){
  reprodutor?.parar();
  const titulo = `${TIPOS[oc.tipo].nome} · ${oc.tipo === "cadeia" || oc.tipo === "ciclo" ? oc.contas.join(" → ") : oc.conta}`;
  ui.modal(titulo, `
    <p style="margin:0 0 10px;font-size:13px;color:var(--ink-2)">${esc(TIPOS[oc.tipo].desc)} <b>${oc.transacoes.length}</b> transação(ões) reais, em ordem cronológica.</p>
    <div class="anim-palco"><div id="animGrafo" class="anim-grafo" role="img" aria-label="Animação do padrão"></div></div>
    <div class="anim-controles">
      <button class="btn ghost sm" id="animInicio" title="Reiniciar">⏮</button>
      <button class="btn ghost sm" id="animAnterior" title="Transação anterior">◀</button>
      <button class="btn sm" id="animPlay">▶ Reproduzir</button>
      <button class="btn ghost sm" id="animProximo" title="Próxima transação">▶|</button>
      <label class="anim-vel">Velocidade <select id="animVel"><option value="0.5">0,5×</option><option value="1" selected>1×</option><option value="2">2×</option></select></label>
      <span id="animPasso" class="anim-passo"></span>
    </div>
    <ol class="anim-lista" id="animLista">${oc.transacoes.map((t, i) => `
      <li data-passo="${i}"><span class="quando">${fmtData(t.data)} ${t.hora}</span> <b>${t.de} → ${t.para}</b> ${fmtBRL(t.valor)} · ${esc(t.tipo)}</li>`).join("")}</ol>
    <p style="margin:10px 0 0;font-size:12px;color:var(--ink-3)">${esc(oc.evidencia || "")}</p>`);

  const cytoscape = await carregarCytoscape();
  const alvo = el("animGrafo");
  if(!alvo) return;
  const pos = posicoes(oc), contas = Object.keys(pos);
  const pares = [...new Set(oc.transacoes.map(t => `${t.de}>${t.para}`))];
  const cy = cytoscape({container: alvo, autoungrabify: false, userZoomingEnabled: true, wheelSensitivity: 0.25,
    style: estilo(document.documentElement.dataset.paleta || "padrao"), layout: {name: "preset", padding: 40},
    elements: [
      ...contas.map(c => ({group: "nodes", data: {id: c, cor: corDe(estado.porId[c], "risco", "padrao"), forma: "ellipse",
                                                    tam: c === oc.conta && oc.tipo !== "cadeia" && oc.tipo !== "ciclo" ? 44 : 32}, position: pos[c]})),
      ...pares.map(p => { const [de, para] = p.split(">"); return {group: "edges", data: {id: p, source: de, target: para, largura: 2, rotulo: ""}}; }),
    ]});
  cy.fit(undefined, 40);
  alvo.cy = cy;

  let passo = -1, tocando = false, temporizador = null;
  const vel = () => +el("animVel").value || 1;

  function marcar(i){
    cy.edges().removeClass("ativa percorrida").data("rotulo", "");
    oc.transacoes.slice(0, Math.max(i, 0)).forEach(t => cy.$id(`${t.de}>${t.para}`).addClass("percorrida"));
    document.querySelectorAll("#animLista li").forEach(li => li.classList.toggle("on", +li.dataset.passo === i));
    el("animLista").querySelector("li.on")?.scrollIntoView({block: "nearest"});
    el("animPasso").textContent = i < 0 ? `0 de ${oc.transacoes.length}` : `Transação ${i + 1} de ${oc.transacoes.length}`;
    if(i < 0) return;
    const t = oc.transacoes[i], aresta = cy.$id(`${t.de}>${t.para}`);
    aresta.removeClass("percorrida").addClass("ativa").data("rotulo", `${fmtBRL(t.valor)} · ${fmtData(t.data).slice(0, 5)} ${t.hora}`);
    // ponto percorrendo a ligação
    const origem = cy.$id(t.de).position(), destino = cy.$id(t.para).position();
    cy.remove(".pulso");
    const pulso = cy.add({group: "nodes", classes: "pulso", data: {id: `pulso${i}`}, position: {...origem}});
    pulso.ungrabify();
    pulso.animate({position: {...destino}}, {duration: 900 / vel(), easing: "ease-in-out-sine", complete: () => pulso.remove()});
  }
  function ir(i){ passo = Math.max(-1, Math.min(oc.transacoes.length - 1, i)); marcar(passo); }
  function tocar(){
    if(!document.contains(alvo)){ parar(); return; }   // a janela foi fechada
    if(passo >= oc.transacoes.length - 1){ pausar(); return; }
    ir(passo + 1);
    temporizador = setTimeout(tocar, 1600 / vel());
  }
  function pausar(){ tocando = false; clearTimeout(temporizador); if(el("animPlay")) el("animPlay").textContent = passo >= oc.transacoes.length - 1 ? "↻ Repetir" : "▶ Reproduzir"; }
  function parar(){ pausar(); cy.destroy(); reprodutor = null; }
  reprodutor = {parar};

  el("animPlay").addEventListener("click", () => {
    if(tocando){ pausar(); return; }
    if(passo >= oc.transacoes.length - 1) ir(-1);
    tocando = true; el("animPlay").textContent = "⏸ Pausar"; tocar();
  });
  el("animProximo").addEventListener("click", () => { pausar(); ir(passo + 1); });
  el("animAnterior").addEventListener("click", () => { pausar(); ir(passo - 1); });
  el("animInicio").addEventListener("click", () => { pausar(); ir(-1); });
  el("animLista").addEventListener("click", e => { const li = e.target.closest("li[data-passo]"); if(li){ pausar(); ir(+li.dataset.passo); } });
  ir(-1);
  // começa sozinho: quem clica em "Animar" quer ver acontecer
  el("animPlay").click();
}

/* fecha a animação junto com a janela */
document.addEventListener("click", e => {
  if(reprodutor && (e.target.closest("[data-close=modal]") || e.target.id === "overlay")) reprodutor.parar();
});
document.addEventListener("keydown", e => { if(e.key === "Escape" && reprodutor) reprodutor.parar(); });
