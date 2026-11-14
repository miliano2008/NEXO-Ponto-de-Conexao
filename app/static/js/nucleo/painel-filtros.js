/* NEXO — painel "Período e filtros": calendário, tipo e faixa de valor (recalculam a
   análise) e filtros de visualização (não recalculam). */
import {carregar} from "./dados.js";
import {emitir, estado} from "./estado.js";
import {FILTROS_VAZIOS, RECORTE_VAZIO, descreverRecorte, filtrosDeVisualizacaoAtivos, quantidadeAtivos} from "./filtros.js";
import {ui} from "./ui.js";
import {el, esc, fmtData, lerBRL, mascararCampoBRL, valorParaCampo} from "./utilidades.js";

const MESES = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"];
const NIVEIS = ["Alta", "Moderada", "Baixa", "Sem indícios"];

const painel = () => el("painelFiltros");
const aberto = () => !painel().hidden;

function meses(primeira, ultima){
  const lista = [];
  for(let [a, m] = primeira.split("-").map(Number); `${a}-${String(m).padStart(2,"0")}` <= ultima.slice(0,7); m === 12 ? (a++, m = 1) : m++){
    const ini = `${a}-${String(m).padStart(2,"0")}-01`, ult = new Date(a, m, 0).getDate();
    const mes = MESES[m-1][0].toUpperCase() + MESES[m-1].slice(1);
    lista.push({rotulo: `${mes}/${a}`, ini, fim: `${a}-${String(m).padStart(2,"0")}-${ult}`});
  }
  return lista;
}

function montar(){
  const d = estado.dados, r = estado.recorte, f = estado.filtros, base = d.simulacao.datas_base;
  const rec = d.simulacao.recorte;
  const contas = d.contas.map(c => c.id).sort();
  const opcoes = (lista, sel) => `<option value="">Todas</option>` + lista.map(v => `<option ${String(v)===String(sel)?"selected":""}>${esc(v)}</option>`).join("");
  const dia = r.inicio && r.inicio === r.fim;
  painel().innerHTML = `
  <form id="formFiltros" novalidate>
    <section>
      <h4>Período <span>recalcula a rede</span></h4>
      <div class="atalhos">
        <button type="button" data-atalho="0" class="${!r.dias && !r.inicio && !r.fim ? "on" : ""}">Base completa</button>
        ${[7, 15, 30].map(n => `<button type="button" data-atalho="${n}" class="${r.dias===n && !r.inicio && !r.fim ? "on" : ""}">Últimos ${n} dias</button>`).join("")}
        ${meses(base.primeira, base.ultima).map(m => `<button type="button" data-ini="${m.ini}" data-fim="${m.fim}" class="${r.inicio===m.ini && r.fim===m.fim ? "on" : ""}">${m.rotulo}</button>`).join("")}
      </div>
      <div class="linha-datas">
        <label>${dia ? "Dia" : "Data inicial"}<input type="date" id="fIni" min="${base.primeira}" max="${base.ultima}" value="${r.inicio || rec.inicio_efetivo}"></label>
        <label id="rotFim" ${dia ? "hidden" : ""}>Data final<input type="date" id="fFim" min="${base.primeira}" max="${base.ultima}" value="${r.fim || rec.fim_efetivo}"></label>
      </div>
      <label class="check"><input type="checkbox" id="fDia" ${dia ? "checked" : ""}> Um dia específico</label>
      <p class="dica">Dados de ${fmtData(base.primeira)} a ${fmtData(base.ultima)}.</p>
    </section>
    <section>
      <h4>Tipo e valor das transações <span>recalcula a rede</span></h4>
      <div class="checks">${d.simulacao.tipos_transacao.map(t => `<label class="check"><input type="checkbox" name="tipo" value="${esc(t)}" ${!r.tipos.length || r.tipos.includes(t) ? "checked" : ""}> ${esc(t)}</label>`).join("")}</div>
      <div class="linha-datas">
        <label>Valor mínimo (R$)<input id="fVmin" inputmode="numeric" placeholder="0,00" value="${valorParaCampo(r.valor_min)}"></label>
        <label>Valor máximo (R$)<input id="fVmax" inputmode="numeric" placeholder="sem limite" value="${valorParaCampo(r.valor_max)}"></label>
      </div>
    </section>
    <section>
      <h4>Mostrar somente <span>não recalcula</span></h4>
      <div class="grade">
        <label>Conta de origem<select id="fOrigem">${opcoes(contas, f.origem)}</select></label>
        <label>Conta de destino<select id="fDestino">${opcoes(contas, f.destino)}</select></label>
        <label>Comunidade<select id="fComunidade">${opcoes(d.comunidades.map(c => c.id), f.comunidade)}</select></label>
        <label>Status de relevância<select id="fStatus"><option value="">Todos</option>${["Alta relevância","Em análise","Revisar","Normal"].map(s => `<option ${f.status===s?"selected":""}>${s}</option>`).join("")}</select></label>
        <label>Investigação<select id="fInvest"><option value="">Todas</option>${Object.entries(estado.situacoes || {}).map(([k, v]) => `<option value="${k}" ${f.investigacao===k?"selected":""}>${esc(v)}</option>`).join("")}</select></label>
        <label>Mínimo de transações da conta<input type="number" id="fMinTx" min="0" step="1" value="${f.minTx || ""}" placeholder="0"></label>
      </div>
      <div class="checks"><span class="rot">Prioridade de verificação:</span>${NIVEIS.map(n => `<label class="check"><input type="checkbox" name="risco" value="${n}" ${f.risco.includes(n) ? "checked" : ""}> ${n}</label>`).join("")}</div>
    </section>
    <div class="msg-erro-mini" id="fErro" hidden></div>
    <footer>
      <button type="button" class="btn ghost" id="fLimpar">Limpar tudo</button>
      <span style="flex:1"></span>
      <button type="button" class="btn ghost" id="fCancelar">Cancelar</button>
      <button type="submit" class="btn" id="fAplicar">Aplicar</button>
    </footer>
  </form>`;

  mascararCampoBRL(el("fVmin")); mascararCampoBRL(el("fVmax"));
  el("fDia").addEventListener("change", e => {
    el("rotFim").hidden = e.target.checked;
    el("fIni").parentElement.firstChild.textContent = e.target.checked ? "Dia" : "Data inicial";
  });
  painel().querySelectorAll("[data-atalho],[data-ini]").forEach(b => b.addEventListener("click", () => {
    painel().querySelectorAll(".atalhos button").forEach(x => x.classList.toggle("on", x === b));
    if(b.dataset.ini){ el("fIni").value = b.dataset.ini; el("fFim").value = b.dataset.fim; }
    else { el("fIni").value = base.primeira; el("fFim").value = base.ultima; }
    el("fDia").checked = false; el("rotFim").hidden = false;
    painel().dataset.atalho = b.dataset.atalho ?? "";
  }));
  ["fIni", "fFim"].forEach(id => el(id).addEventListener("input", () => {
    painel().dataset.atalho = "";
    painel().querySelectorAll(".atalhos button").forEach(x => x.classList.remove("on"));
  }));
  painel().dataset.atalho = r.inicio || r.fim ? "" : String(r.dias || 0);
  el("fCancelar").addEventListener("click", fechar);
  el("fLimpar").addEventListener("click", () => aplicar({...RECORTE_VAZIO}, {...FILTROS_VAZIOS, risco: []}));
  el("formFiltros").addEventListener("submit", e => { e.preventDefault(); aplicar(...lerFormulario()); });
}

function lerFormulario(){
  const base = estado.dados.simulacao.datas_base, atalho = painel().dataset.atalho;
  const tipos = [...painel().querySelectorAll("input[name=tipo]:checked")].map(i => i.value);
  const todos = estado.dados.simulacao.tipos_transacao;
  let ini = el("fIni").value, fim = el("fDia").checked ? ini : el("fFim").value;
  const recorte = {dias: 0, inicio: "", fim: "", tipos: tipos.length === todos.length ? [] : tipos,
                   valor_min: lerBRL(el("fVmin").value) ?? "", valor_max: lerBRL(el("fVmax").value) ?? ""};
  if(atalho !== "" && atalho !== undefined){ recorte.dias = +atalho; }          // atalho: "últimos N dias" ou base completa
  else if(!(ini === base.primeira && fim === base.ultima)){ recorte.inicio = ini; recorte.fim = fim; }
  const filtros = {origem: el("fOrigem").value, destino: el("fDestino").value, comunidade: el("fComunidade").value,
                   status: el("fStatus").value, investigacao: el("fInvest").value, minTx: +el("fMinTx").value || 0,
                   risco: [...painel().querySelectorAll("input[name=risco]:checked")].map(i => i.value)};
  return [recorte, filtros];
}

async function aplicar(recorte, filtros){
  const erro = el("fErro");
  if(!tiposEscolhidos(recorte)){ erro.textContent = "Escolha pelo menos um tipo de transação."; erro.hidden = false; return; }
  const mudouRecorte = JSON.stringify(recorte) !== JSON.stringify(estado.recorte);
  const anterior = estado.recorte;
  estado.filtros = filtros;
  if(mudouRecorte){
    estado.recorte = recorte;
    el("fAplicar") && (el("fAplicar").disabled = true);
    try{ await carregar(); }
    catch(err){
      estado.recorte = anterior;
      if(erro){ erro.textContent = err.message; erro.hidden = false; }
      el("fAplicar") && (el("fAplicar").disabled = false);
      return;
    }
  } else {
    emitir("filtros");
  }
  atualizarIndicador();
  fechar();
  ui.toast(mudouRecorte ? "✓ Análise recalculada para o novo recorte." : "✓ Filtros aplicados.");
}

const tiposEscolhidos = r => !painel().querySelector("input[name=tipo]") || r.tipos.length || painel().querySelectorAll("input[name=tipo]:checked").length;

export function atualizarIndicador(){
  const n = quantidadeAtivos();
  el("filtrosQtd").textContent = n; el("filtrosQtd").hidden = !n;
  el("periodLabel").textContent = descreverRecorte();
  el("filtrosAviso").innerHTML = filtrosDeVisualizacaoAtivos()
    ? ` · <b class="aviso-filtro">filtros de visualização ativos</b> <button class="link-limpar" id="limparVisual" type="button">limpar</button>` : "";
  el("limparVisual")?.addEventListener("click", () => {
    estado.filtros = {...FILTROS_VAZIOS, risco: []}; emitir("filtros"); atualizarIndicador();
  });
}

export function abrir(){
  if(!estado.dados) return;
  montar();
  painel().hidden = false;
  el("btnFiltros").setAttribute("aria-expanded", "true");
  setTimeout(() => el("fIni")?.focus(), 30);
}
export function fechar(){
  painel().hidden = true;
  el("btnFiltros").setAttribute("aria-expanded", "false");
}
export function alternar(){ aberto() ? fechar() : abrir(); }

document.addEventListener("keydown", e => { if(e.key === "Escape" && aberto()) fechar(); });
document.addEventListener("click", e => {
  if(aberto() && !e.target.closest("#painelFiltros") && !e.target.closest("#btnFiltros")) fechar();
});
