/* NEXO — preferências do usuário (Fase 5): aparência, acessibilidade, grafo, gráficos e relatórios.

   Ficam no banco (PUT /api/preferencias) e acompanham o usuário em qualquer computador.
   aplicar() traduz cada preferência em atributos do <html> (o CSS faz o resto) e avisa as telas:
     "tema"          → cores mudaram (grafo e minimapa redesenham)
     "rotulos"       → nomes das contas no grafo
     "preferencias"  → qualquer outra mudança (gráficos, cores do grafo, limiares)
*/
import {api} from "./api.js";
import {emitir, estado} from "./estado.js";
import {ui} from "./ui.js";
import {el, esc} from "./utilidades.js";

export const prefs = {};
let padrao = {};

const ATRIBUTOS = {texto: "data-texto", fonte: "data-fonte"};

export function aplicar(novas){
  const antes = {...prefs};
  Object.assign(prefs, novas);
  const raiz = document.documentElement;
  if(prefs.tema === "claro") raiz.setAttribute("data-theme", "light");
  else if(prefs.tema === "escuro") raiz.setAttribute("data-theme", "dark");
  else raiz.removeAttribute("data-theme");
  Object.entries(ATRIBUTOS).forEach(([k, atr]) => raiz.setAttribute(atr, prefs[k]));
  raiz.toggleAttribute("data-contraste", !!prefs.contraste);
  raiz.toggleAttribute("data-menos-animacao", !!prefs.menos_animacao);
  raiz.toggleAttribute("data-foco", !!prefs.foco_reforcado);
  estado.limiares.analise = prefs.limiar_analise;
  estado.limiares.alta = prefs.limiar_alta;
  if(antes.tema !== undefined && (antes.tema !== prefs.tema || antes.contraste !== prefs.contraste)) emitir("tema");
  if(antes.grafo_rotulos !== undefined && antes.grafo_rotulos !== prefs.grafo_rotulos) emitir("rotulos", prefs.grafo_rotulos);
  emitir("preferencias", prefs);
}

/* Menos animação: pedido do usuário ou do sistema operacional. */
export const semAnimacao = () => !!prefs.menos_animacao || matchMedia("(prefers-reduced-motion: reduce)").matches;

export async function carregarPreferencias(){
  try{
    const r = await api("/api/preferencias");
    padrao = r.padrao;
    aplicar(r.preferencias);
  } catch(_){ /* sem as preferências, a tela segue com o padrão */ }
}

/* Salva no banco (várias mudanças seguidas viram um pedido só). */
let pendente = {}, temporizador = null;
export function salvar(parcial, {imediato = false} = {}){
  aplicar(parcial);
  Object.assign(pendente, parcial);
  clearTimeout(temporizador);
  const enviar = async () => {
    const corpo = pendente; pendente = {};
    try{ aplicar((await api("/api/preferencias", {method: "PUT", body: JSON.stringify({preferencias: corpo})})).preferencias); }
    catch(err){ ui.toast(esc(err.message), true); }
  };
  if(imediato) return enviar();
  temporizador = setTimeout(enviar, 400);
}

export async function restaurarPadrao(){
  aplicar((await api("/api/preferencias", {method: "PUT", body: JSON.stringify({padrao: true})})).preferencias);
}

/* ---------- formulário (Configurações e o botão "Preferências" da barra lateral) ---------- */
const OPCOES = {
  tema: [["sistema", "Igual ao sistema"], ["claro", "Claro"], ["escuro", "Escuro"]],
  texto: [["normal", "Normal"], ["grande", "Grande"], ["maior", "Maior"]],
  fonte: [["inter", "Inter (padrão)"], ["sistema", "Fonte do sistema"], ["legivel", "Alta legibilidade"]],
  grafo_esquema: [["status", "Status de relevância"], ["risco", "Prioridade de risco"], ["com", "Comunidade (Louvain)"], ["papel", "Papel na rede"]],
  grafo_paleta: [["padrao", "Padrão"], ["daltonismo", "Segura para daltonismo"]],
  relatorio_formato: [["pdf", "PDF"], ["xlsx", "Excel"], ["docx", "Word"], ["pptx", "PowerPoint"], ["csv", "CSV"]],
};
const CHAVES = [
  ["contraste", "Contraste alto", "Textos e bordas mais fortes"],
  ["menos_animacao", "Menos animação", "Desliga transições e o movimento automático do grafo"],
  ["foco_reforcado", "Foco bem visível", "Contorno grosso no item selecionado pelo teclado (Tab)"],
  ["grafo_rotulos", "Rótulos das contas no grafo", "Mostra o código da conta sob cada nó"],
  ["graficos_valores", "Valores nos gráficos", "Escreve o valor em cima de cada barra"],
];

const seletor = (chave, rotulo) => `<label>${rotulo}<select data-pref="${chave}">${OPCOES[chave]
  .map(([v, n]) => `<option value="${v}" ${prefs[chave] === v ? "selected" : ""}>${n}</option>`).join("")}</select></label>`;

export function formularioPreferencias(alvo){
  alvo.innerHTML = `
    <div class="form-pref">
      <h4>Aparência</h4>
      <div class="pref-grade">${seletor("tema", "Tema")}${seletor("texto", "Tamanho do texto")}${seletor("fonte", "Fonte")}</div>
      <h4>Grafo e relatórios</h4>
      <div class="pref-grade">${seletor("grafo_esquema", "Cores do grafo")}${seletor("grafo_paleta", "Paleta do grafo")}${seletor("relatorio_formato", "Formato preferido do relatório")}</div>
      <h4>Acessibilidade e exibição</h4>
      ${CHAVES.map(([k, nome, desc]) => `<div class="switch"><div><p>${nome}</p><span>${desc}</span></div>
        <button class="toggle ${prefs[k] ? "on" : ""}" data-pref-bool="${k}" role="switch" aria-checked="${!!prefs[k]}" aria-label="${nome}"></button></div>`).join("")}
      <div style="display:flex;gap:10px;align-items:center;margin-top:14px;flex-wrap:wrap">
        <button class="btn ghost sm" type="button" data-pref-padrao>Voltar ao padrão</button>
        <span style="font-size:12px;color:var(--ink-3)">Salvas no seu cadastro: valem em qualquer computador.</span>
      </div>
    </div>`;
  if(alvo.dataset.ligado) return;
  alvo.dataset.ligado = "1";
  alvo.addEventListener("change", e => {
    const s = e.target.closest("select[data-pref]");
    if(s) salvar({[s.dataset.pref]: s.value});
  });
  alvo.addEventListener("click", async e => {
    const b = e.target.closest("[data-pref-bool]");
    if(b){
      const valor = !b.classList.contains("on");
      b.classList.toggle("on", valor); b.setAttribute("aria-checked", valor);
      salvar({[b.dataset.prefBool]: valor});
      return;
    }
    if(e.target.closest("[data-pref-padrao]")){
      await restaurarPadrao(); formularioPreferencias(alvo); ui.toast("✓ Preferências no padrão.");
    }
  });
}

export function abrirPreferencias(){
  ui.modal("Preferências", `<div id="prefModal"></div>`);
  formularioPreferencias(el("prefModal"));
}

export const valoresPadrao = () => ({...padrao});
