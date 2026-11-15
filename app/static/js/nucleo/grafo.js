/* NEXO — grafos com Cytoscape.js (Fase 3): carregamento sob demanda, esquemas de cores
   com legenda (inclusive paleta segura para daltonismo), estilo e minimapa.

   O Cytoscape (~136 KB compactado) fica em static/vendor e só é baixado quando uma tela
   com grafo é aberta. As cores vêm das variáveis do tema (claro/escuro). */

let modulo = null;
export function carregarCytoscape(){
  modulo ||= import("../../vendor/cytoscape/cytoscape.esm.min.js").then(m => m.default)
    .catch(erro => { modulo = null; throw new Error("Não foi possível carregar o desenho do grafo: " + erro.message); });
  return modulo;
}

/* ---------- cores ---------- */
// Okabe–Ito (Color Universal Design). O amarelo original (#F0E442) tem pouco contraste no fundo
// claro e foi trocado pelo preto, que também faz parte da paleta.
const OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#000000", "#7F7F7F"];
const CORES_COM = ["#1B5FA8", "#D99311", "#1E7A5A", "#C2263C", "#7B4FC4", "#0E8A9A", "#B5578A", "#6B7D1E", "#8A5A2B", "#4A5A6E", "#2F9E44", "#E8590C"];
// na paleta para daltonismo, a comunidade também muda a FORMA do nó (cor não é a única pista)
export const FORMAS = ["ellipse", "round-rectangle", "triangle", "diamond", "round-hexagon", "star", "vee", "round-tag"];

const PALETAS = {
  padrao: {
    status: {"Alta relevância": "#C2263C", "Em análise": "#D99311", "Revisar": "#7FA4CE", "Normal": "#1B5FA8"},
    risco: {"Alta": "#C2263C", "Moderada": "#D99311", "Baixa": "#1B5FA8", "Sem indícios": "#A9B6C6"},
    papel: {"Intermediária e repasse": "#C2263C", "Intermediária": "#7B4FC4", "Repasse": "#D99311", "Outro papel": "#A9B6C6"},
    com: CORES_COM, simulada: "#1E7A5A", destaque: "#1E7A5A",
  },
  daltonismo: {
    status: {"Alta relevância": "#D55E00", "Em análise": "#E69F00", "Revisar": "#56B4E9", "Normal": "#0072B2"},
    risco: {"Alta": "#D55E00", "Moderada": "#E69F00", "Baixa": "#0072B2", "Sem indícios": "#999999"},
    papel: {"Intermediária e repasse": "#D55E00", "Intermediária": "#0072B2", "Repasse": "#E69F00", "Outro papel": "#999999"},
    com: OKABE_ITO, simulada: "#009E73", destaque: "#009E73",
  },
};

export const ESQUEMAS = {
  status: "Status de relevância", risco: "Prioridade de risco", com: "Comunidade (Louvain)", papel: "Papel na rede",
};

/* papel: intermediária (intermediação ou ponte entre comunidades) e/ou repasse (repasse rápido ou cadeia) */
export function papel(conta){
  const i = conta.indicios || [];
  const inter = i.includes("intermediacao") || i.includes("ponte"), rep = i.includes("repasse") || i.includes("cadeia");
  return inter && rep ? "Intermediária e repasse" : inter ? "Intermediária" : rep ? "Repasse" : "Outro papel";
}

export function corDe(conta, esquema, paleta){
  const p = PALETAS[paleta] || PALETAS.padrao;
  if(esquema === "com") return p.com[(conta.com - 1) % p.com.length];
  if(esquema === "risco") return p.risco[conta.nivel_risco] || p.risco["Sem indícios"];
  if(esquema === "papel") return p.papel[papel(conta)];
  return p.status[conta.status] || p.status.Normal;
}
export const formaDe = (conta, esquema, paleta) =>
  paleta === "daltonismo" && esquema === "com" ? FORMAS[(conta.com - 1) % FORMAS.length] : "ellipse";

export function legenda(esquema, paleta, comunidades){
  const p = PALETAS[paleta] || PALETAS.padrao;
  const item = (cor, texto, forma = "ellipse") =>
    `<span><i class="forma-${forma}" style="background:${cor}"></i>${texto}</span>`;
  const itens = esquema === "com"
    ? comunidades.map(c => item(p.com[(c.id - 1) % p.com.length], `Comunidade ${c.id}`, paleta === "daltonismo" ? FORMAS[(c.id - 1) % FORMAS.length] : "ellipse"))
    : Object.entries(p[esquema]).map(([nome, cor]) => item(cor, nome));
  return itens.join("") + `<span><i style="background:${p.simulada};border-radius:2px;height:3px;width:16px"></i>Conexão simulada</span>`;
}

/* variáveis do tema atual (o Cytoscape desenha em canvas e precisa da cor final) */
export function tema(){
  const s = getComputedStyle(document.documentElement), v = n => s.getPropertyValue(n).trim();
  return {texto: v("--ink-2") || "#4A5A6E", linha: v("--line") || "#E1E7EF", fundo: v("--surface") || "#fff",
          azul: v("--blue") || "#1B5FA8", tinta: v("--ink") || "#16202E", suave: v("--ink-3") || "#7C8B9E"};
}

/* ---------- estilo ---------- */
export function estilo(paleta = "padrao", opcoes = {}){
  const t = tema(), p = PALETAS[paleta] || PALETAS.padrao;
  return [
    {selector: "node", style: {
      "background-color": "data(cor)", shape: "data(forma)", width: "data(tam)", height: "data(tam)",
      label: opcoes.rotulos === false ? "" : "data(id)", "font-size": 11, "font-weight": 600, color: t.texto,
      "text-valign": "bottom", "text-margin-y": 4, "border-width": 2, "border-color": t.fundo,
      "text-background-color": t.fundo, "text-background-opacity": 0.75, "text-background-padding": 1,
      "transition-property": "opacity", "transition-duration": "180ms"}},
    {selector: "edge", style: {
      width: "data(largura)", "line-color": t.linha, "target-arrow-color": t.linha, "target-arrow-shape": "triangle",
      "arrow-scale": 0.9, "curve-style": "bezier", opacity: 0.9,
      "transition-property": "opacity, line-color, width", "transition-duration": "180ms"}},
    {selector: "edge.simulada", style: {"line-color": p.simulada, "target-arrow-color": p.simulada, "line-style": "dashed", width: 3}},
    {selector: "node.destaque", style: {"border-color": p.destaque, "border-width": 4}},
    {selector: "node.selecionado", style: {"border-color": t.tinta, "border-width": 4}},
    {selector: ".apagado", style: {opacity: 0.12}},
    {selector: "edge.vizinha", style: {"line-color": t.azul, "target-arrow-color": t.azul, opacity: 1}},
    {selector: "edge.ativa", style: {
      "line-color": p.destaque, "target-arrow-color": p.destaque, width: 5, opacity: 1, label: "data(rotulo)",
      "font-size": 11, "font-weight": 700, color: t.tinta, "text-background-color": t.fundo, "text-background-opacity": 0.95,
      "text-background-padding": 3, "text-rotation": "autorotate", "text-margin-y": -14, "z-index": 20}},
    {selector: "edge.percorrida", style: {"line-color": p.destaque, "target-arrow-color": p.destaque, opacity: 0.55, width: 3}},
    {selector: "node.pulso", style: {width: 12, height: 12, "background-color": p.destaque, "border-width": 0, label: "", "z-index": 30}},
  ];
}

/* ---------- elementos ---------- */
export function elementos(contas, arestas, {esquema = "status", paleta = "padrao", simuladas = new Set()} = {}){
  const maxValor = Math.max(1, ...arestas.map(a => a.valor_total));
  return [
    ...contas.map(c => ({group: "nodes", data: {
      id: c.id, cor: corDe(c, esquema, paleta), forma: formaDe(c, esquema, paleta),
      tam: 22 + Math.min(c.degree, 14) * 2.8}})),
    ...arestas.map(a => ({group: "edges", classes: simuladas.has(`${a.de}>${a.para}`) ? "simulada" : "",
      data: {id: `${a.de}>${a.para}`, source: a.de, target: a.para, quantidade: a.quantidade, valor: a.valor_total,
             largura: 1.2 + 4 * Math.sqrt(a.valor_total / maxValor)}})),
  ];
}

/* posição inicial agrupada por comunidade: o layout converge mais rápido e fica parecido entre execuções */
export function posicaoInicial(conta, i, nComunidades){
  const a = ((conta.com - 1) / Math.max(nComunidades, 1)) * Math.PI * 2, j = (i * 2.399) % (Math.PI * 2);
  return {x: Math.cos(a) * 420 + Math.cos(j) * 70, y: Math.sin(a) * 300 + Math.sin(j) * 70};
}

export const LAYOUT = {name: "cose", animate: false, randomize: false, fit: true, padding: 30, nodeRepulsion: () => 12000,
  idealEdgeLength: () => 90, edgeElasticity: () => 80, gravity: 0.35, numIter: 1500, componentSpacing: 90,
  nodeDimensionsIncludeLabels: true, nestingFactor: 1.2};

/* ---------- minimapa ---------- */
// segunda instância, sem interação própria, com um retângulo mostrando a área visível do grafo principal
export function criarMinimapa(cytoscape, cy, alvo){
  alvo.innerHTML = `<div class="minimapa-grafo"></div><div class="minimapa-janela"></div>`;
  const mini = cytoscape({container: alvo.firstElementChild, elements: [], autoungrabify: true, autounselectify: true,
    userZoomingEnabled: false, userPanningEnabled: false, boxSelectionEnabled: false,
    style: [{selector: "node", style: {"background-color": "data(cor)", width: "data(tam)", height: "data(tam)", label: ""}},
            {selector: "edge", style: {width: 1, "line-color": tema().linha, "curve-style": "haystack"}}]});
  const janela = alvo.lastElementChild;
  let quadro = 0, quadroCopia = 0;

  function copiar(){
    mini.elements().remove();
    mini.add(cy.elements().not(".pulso").map(e => ({group: e.group(), data: {...e.data()},
      position: e.isNode() ? {...e.position()} : undefined})));
    mini.fit(undefined, 6);
    desenharJanela();
  }
  function desenharJanela(){
    cancelAnimationFrame(quadro);
    quadro = requestAnimationFrame(() => {
      const ext = cy.extent(), z = mini.zoom(), p = mini.pan();
      const x1 = Math.max(0, ext.x1 * z + p.x), y1 = Math.max(0, ext.y1 * z + p.y);
      const x2 = Math.min(alvo.clientWidth, ext.x2 * z + p.x), y2 = Math.min(alvo.clientHeight, ext.y2 * z + p.y);
      Object.assign(janela.style, {left: x1 + "px", top: y1 + "px", width: Math.max(4, x2 - x1) + "px", height: Math.max(4, y2 - y1) + "px"});
    });
  }
  // clicar ou arrastar no minimapa leva a visão do grafo principal para aquele ponto
  let arrastando = false;
  const irPara = e => {
    const r = alvo.getBoundingClientRect(), z = mini.zoom(), p = mini.pan();
    const modelo = {x: (e.clientX - r.left - p.x) / z, y: (e.clientY - r.top - p.y) / z};
    const ext = cy.extent();
    cy.panBy({x: ((ext.x1 + ext.x2) / 2 - modelo.x) * cy.zoom(), y: ((ext.y1 + ext.y2) / 2 - modelo.y) * cy.zoom()});
  };
  alvo.addEventListener("pointerdown", e => { arrastando = true; alvo.setPointerCapture(e.pointerId); irPara(e); });
  alvo.addEventListener("pointermove", e => { if(arrastando) irPara(e); });
  alvo.addEventListener("pointerup", () => { arrastando = false; });

  cy.on("viewport resize", desenharJanela);
  cy.on("position", "node", () => { cancelAnimationFrame(quadroCopia); quadroCopia = requestAnimationFrame(copiar); });
  return {atualizar: copiar, mini};
}
