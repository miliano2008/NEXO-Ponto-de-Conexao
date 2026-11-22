/* NEXO — tela Importar base (Fase 6, importação simples, só o administrador).

   Etapas: 1) enviar o .xlsx/.csv · 2) conferir as colunas (o servidor sugere; dá para ajustar)
   · 3) prévia com o erro de cada linha · 4) substituir a base (nome, aceite e "SUBSTITUIR").
   A troca vale para todos os usuários; o servidor faz um backup automático antes. */
import {api} from "../nucleo/api.js";
import {carregar} from "../nucleo/dados.js";
import {estado} from "../nucleo/estado.js";
import {baixar} from "../nucleo/exportar.js";
import {FILTROS_VAZIOS, RECORTE_VAZIO} from "../nucleo/filtros.js";
import {atualizarIndicador} from "../nucleo/painel-filtros.js";
import {ui} from "../nucleo/ui.js";
import {el, esc, fmtBRL, fmtData, fmtDataHora} from "../nucleo/utilidades.js";

let envio = null;            // resposta do envio do arquivo: abas, campos, sugestão
let ultimo = null;           // último resultado da prévia
let temporizador = null, pedido = 0;

const ORIGEM = {arquivo: "Arquivo importado", demonstracao: "Base de demonstração"};
const SITUACAO = {ativa: `<span class="pill normal">Em uso</span>`, substituida: `<span class="pill">Substituída</span>`};

/* ---------- base em uso e histórico ---------- */
async function carregarBase(){
  let r;
  try{ r = await api("/api/base"); }
  catch(err){ el("impBase").innerHTML = `<dd>${esc(err.message)}</dd>`; return; }
  const b = r.base;
  el("impBaseSub").textContent = ORIGEM[b.origem] || b.origem;
  el("impBase").innerHTML = `
    <dt>Nome</dt><dd><b>${esc(b.nome)}</b></dd>
    <dt>Tamanho</dt><dd>${b.contas} contas · ${b.transacoes} transações</dd>
    <dt>Período</dt><dd>${b.periodo ? `${fmtData(b.periodo[0])} a ${fmtData(b.periodo[1])}` : "—"}</dd>
    ${b.arquivo ? `<dt>Arquivo</dt><dd>${esc(b.arquivo)}${b.mascarada ? " · códigos mascarados" : ""}</dd>` : ""}
    ${b.importado_por ? `<dt>Trocada por</dt><dd>${esc(b.importado_por)} em ${fmtDataHora(b.importado_em)}</dd>` : ""}`;
  el("impDemo").hidden = b.origem === "demonstracao" && !b.id;
  const a = r.apagados_na_troca || {};
  el("impApagados").innerHTML = `<b>Ao substituir, a base atual (“${esc(b.nome)}”) sai de uso para todos</b> e também são apagados:
    ${a.cenarios} cenário(s) salvo(s), ${a.rascunhos} simulação(ões) em andamento (${a.transacoes_simuladas} transação(ões) simulada(s)),
    ${a.investigacoes} registro(s) de investigação e ${a.analises} análise(s) guardada(s).
    Ficam: usuários, preferências, limites das regras e a auditoria. O backup automático permite recuperar a base atual.`;
  el("impHistorico").innerHTML = (r.historico || []).map(h => `<tr>
      <td>${fmtDataHora(h.importado_em)}</td><td><b>${esc(h.nome)}</b>${h.arquivo ? `<br><span style="font-size:11.5px;color:var(--ink-3)">${esc(h.arquivo)}</span>` : ""}</td>
      <td>${ORIGEM[h.origem] || esc(h.origem)}${h.mascarada ? " · mascarada" : ""}</td><td class="num">${h.contas}</td><td class="num">${h.transacoes}</td>
      <td>${h.periodo_inicio ? `${fmtData(h.periodo_inicio)} a ${fmtData(h.periodo_fim)}` : "—"}</td><td>${esc(h.importado_por)}</td>
      <td style="font-size:11.5px">${esc(h.backup || "—")}</td><td>${SITUACAO[h.situacao] || esc(h.situacao)}</td></tr>`).join("")
    || `<tr><td colspan="9" class="empty">Nenhuma troca ainda: o NEXO está com a base de demonstração original.</td></tr>`;
}

/* ---------- 1. enviar arquivo ---------- */
async function enviarArquivo(arquivo){
  if(!arquivo) return;
  if(arquivo.size > 2 * 1024 * 1024){ ui.toast("Arquivo grande demais: o limite é 2 MB.", true); return; }
  const dados = new FormData(); dados.append("arquivo", arquivo);
  el("loading").classList.add("on");
  el("impArquivoInfo").hidden = false; el("impArquivoInfo").innerHTML = `Lendo <b>${esc(arquivo.name)}</b>…`;
  try{
    const r = await fetch("/api/importacao/arquivo", {method: "POST", body: dados, headers: {"X-Requested-With": "NEXO"}});
    if(r.status === 401){ location.href = "/login"; return; }
    const corpo = await r.json().catch(() => ({}));
    if(!r.ok) throw new Error(corpo.erro || `Erro ${r.status} no servidor`);
    envio = corpo;
    el("impArquivoInfo").innerHTML = `✓ <b>${esc(corpo.arquivo.nome)}</b> · ${corpo.abas.length} aba(s)
      ${corpo.mapeamento_salvo ? " · usei o mapeamento salvo da última importação com estas colunas" : ""}
      ${corpo.mesmo_arquivo_da_base ? `<br><span style="color:var(--amber)">Este é o mesmo arquivo da base em uso.</span>` : ""}`;
    el("impEtapas").hidden = false;
    desenharMapa(corpo.sugestao);
    mostrarResultado(corpo.resultado);
    el("impEtapas").scrollIntoView({behavior: "smooth", block: "start"});
  } catch(err){
    envio = null; el("impEtapas").hidden = true;
    el("impArquivoInfo").innerHTML = `<span style="color:var(--red)">${esc(err.message)}</span>`;
  } finally { el("loading").classList.remove("on"); el("impArquivo").value = ""; }
}

/* ---------- 2. conferir as colunas ---------- */
function seletorColuna(grupo, [campo, rotulo, obrigatorio], cabecalho, atual){
  return `<label><span>${esc(rotulo)}${obrigatorio ? ` <span class="obrig" title="obrigatório">*</span>` : ""}</span>
    <select data-grupo="${grupo}" data-campo="${campo}">
      <option value="">${obrigatorio ? "— escolha a coluna —" : "— não tem —"}</option>
      ${cabecalho.map((c, i) => `<option value="${i}" ${atual === i ? "selected" : ""}>${esc(c || `(coluna ${i + 1} sem nome)`)}</option>`).join("")}
    </select></label>`;
}

function desenharMapa(s){
  const abas = envio.abas;
  const opcoesAba = (atual, comNenhuma) => (comNenhuma ? `<option value="">Não usar (tirar as contas das transações)</option>` : "")
    + abas.map((a, i) => `<option value="${i}" ${atual === i ? "selected" : ""}>${esc(a.nome)} (${a.linhas} linha(s))</option>`).join("");
  const tx = abas[s.aba_transacoes], ct = s.aba_contas != null ? abas[s.aba_contas] : null;
  el("impMapa").innerHTML = `
    <div class="imp-grupo"><h4>Transações</h4>
      <label>Aba<select id="impAbaTx">${opcoesAba(s.aba_transacoes, false)}</select></label>
      <div class="pref-grade">${envio.campos.transacoes.map(c =>
        seletorColuna("tx", c, tx.cabecalho, s.mapa_transacoes[c[0]])).join("")}</div></div>
    <div class="imp-grupo"><h4>Contas <small>(opcional)</small></h4>
      <label>Aba<select id="impAbaCt">${opcoesAba(s.aba_contas, true)}</select></label>
      ${ct ? `<div class="pref-grade">${envio.campos.contas.map(c =>
        seletorColuna("ct", c, ct.cabecalho, s.mapa_contas[c[0]])).join("")}</div>` : ""}</div>
    <label class="check"><input type="checkbox" id="impMascarar" ${s.mascarar ? "checked" : ""}>
      <span><b>Mascarar códigos (LGPD)</b>: as contas viram C001, C002… e as transações T0001… A correspondência com os códigos originais não é guardada.</span></label>`;
}

function lerMapa(){
  const mapa = grupo => Object.fromEntries([...document.querySelectorAll(`#impMapa select[data-grupo=${grupo}]`)]
    .filter(s => s.value !== "").map(s => [s.dataset.campo, +s.value]));
  const abaCt = el("impAbaCt").value;
  return {aba_transacoes: +el("impAbaTx").value, mapa_transacoes: mapa("tx"),
          aba_contas: abaCt === "" ? null : +abaCt, mapa_contas: abaCt === "" ? {} : mapa("ct"),
          mascarar: el("impMascarar").checked};
}

function agendarPrevia(){
  clearTimeout(temporizador);
  temporizador = setTimeout(async () => {
    const meu = ++pedido;
    try{
      const r = await api("/api/importacao/previa", {method: "POST", body: JSON.stringify(lerMapa())});
      if(meu === pedido) mostrarResultado(r.resultado);
    } catch(err){ if(meu === pedido) ui.toast(esc(err.message), true); }
  }, 250);
}

/* ---------- 3. prévia ---------- */
function mostrarResultado(r){
  ultimo = r;
  const z = r.resumo;
  el("impPreviaSub").textContent = z ? `${z.transacoes} de ${z.linhas} linha(s) prontas · primeiras ${r.previa.length} mostradas abaixo` : "";
  const erros = r.erros || [], avisos = r.avisos || [];
  el("impResumo").innerHTML = `
    ${z ? `<div class="imp-resumo">
      <div><b>${z.transacoes}</b><span>transações</span></div><div><b>${z.contas}</b><span>contas</span></div>
      <div><b>${fmtBRL(z.volume)}</b><span>volume</span></div>
      <div><b>${fmtData(z.periodo[0])} a ${fmtData(z.periodo[1])}</b><span>período</span></div>
      <div><b>${Object.entries(z.por_tipo).map(([k, v]) => `${esc(k)} ${v}`).join(" · ")}</b><span>modalidades</span></div></div>` : ""}
    ${erros.length ? `<div class="note warn imp-lista"><b>${erros.length >= 200 ? "200+" : erros.length} problema(s) para corrigir antes de importar:</b><ul>
      ${erros.slice(0, 15).map(e => `<li>${e.linha ? `<b>Linha ${e.linha}:</b> ` : ""}${esc(e.mensagem)}</li>`).join("")}
      ${erros.length > 15 ? `<li>… e mais ${erros.length - 15}. Corrija no arquivo e envie de novo.</li>` : ""}</ul></div>`
      : `<div class="note imp-ok">✓ Nenhum erro: a base pode ser importada.</div>`}
    ${avisos.length ? `<div class="note imp-lista"><b>Avisos</b><ul>${avisos.map(a => `<li>${esc(a)}</li>`).join("")}</ul></div>` : ""}`;
  el("impPrevia").innerHTML = (r.previa || []).map(p => p.erro
    ? `<tr class="linha-erro"><td class="num">${p.linha}</td><td colspan="7">—</td><td><span class="pill alta">${esc(p.erro)}</span></td></tr>`
    : `<tr><td class="num">${p.linha}</td><td class="mono-id">${esc(p.id)}</td><td class="mono-id">${esc(p.de)}</td><td class="mono-id">${esc(p.para)}</td>
        <td class="num">${fmtBRL(p.valor)}</td><td>${fmtData(p.data)}</td><td>${esc(p.hora)}</td><td>${esc(p.tipo)}</td>
        <td><span class="pill normal">OK</span></td></tr>`).join("")
    || `<tr><td colspan="9" class="empty">Escolha as colunas obrigatórias para ver a prévia.</td></tr>`;
  validarFormulario();
}

/* ---------- 4. substituir ---------- */
async function recarregarBaseNova(){
  // período, filtros e destaques da base antiga podem não existir na nova
  estado.recorte = {...RECORTE_VAZIO};
  estado.filtros = {...FILTROS_VAZIOS, risco: []};
  estado.destaque = new Set(); estado.ultimoImpacto = null;
  await carregar();
  atualizarIndicador();
  await carregarBase();
}

function validarFormulario(){
  const ok = !!ultimo?.pode_importar && el("impAceite").checked && el("impNome").value.trim().length >= 3
    && el("impConfirmacao").value.trim().toUpperCase() === "SUBSTITUIR";
  el("impEnviar").disabled = !ok;
}

async function substituir(e){
  e.preventDefault();
  el("impErro").hidden = true; el("impEnviar").disabled = true;
  try{
    const r = await api("/api/importacao/confirmar", {method: "POST", body: JSON.stringify({...lerMapa(),
      nome: el("impNome").value, aceite: el("impAceite").checked, confirmacao: el("impConfirmacao").value})});
    envio = ultimo = null;
    el("impEtapas").hidden = true; el("impArquivoInfo").hidden = true; el("impForm").reset();
    await recarregarBaseNova();
    ui.toast(`✓ Base “${esc(r.base.nome)}” em uso. Backup da anterior: ${esc(r.backup)}`);
  } catch(err){ el("impErro").textContent = err.message; el("impErro").hidden = false; validarFormulario(); }
}

function voltarDemonstracao(){
  ui.modal("Voltar à base de demonstração", `
    <form id="formDemo" class="form-senha" novalidate>
      <p style="margin:0 0 12px;font-size:13px">A base atual sai de uso e volta a base de demonstração do projeto (40 contas e 160 transações).
        Simulações, cenários e investigações da base atual são apagados; antes, o NEXO faz um backup automático.</p>
      <label>Para confirmar, digite <b>SUBSTITUIR</b><input id="demoConfirmacao" autocomplete="off"></label>
      <div class="msg-erro-mini" id="demoErro" hidden></div>
      <button class="btn" type="submit">Voltar à base de demonstração</button>
    </form>`);
  setTimeout(() => el("demoConfirmacao").focus(), 30);
  el("formDemo").addEventListener("submit", async ev => {
    ev.preventDefault();
    try{
      const r = await api("/api/base/demonstracao", {method: "POST", body: JSON.stringify({confirmacao: el("demoConfirmacao").value})});
      ui.closeModal();
      await recarregarBaseNova();
      ui.toast(`✓ Base de demonstração em uso. Backup da anterior: ${esc(r.backup)}`);
    } catch(err){ el("demoErro").textContent = err.message; el("demoErro").hidden = false; }
  });
}

export function iniciar(){
  el("impArquivo").addEventListener("change", e => enviarArquivo(e.target.files[0]));
  const area = el("impArea");
  ["dragenter", "dragover"].forEach(t => area.addEventListener(t, e => { e.preventDefault(); area.classList.add("sobre"); }));
  ["dragleave", "drop"].forEach(t => area.addEventListener(t, () => area.classList.remove("sobre")));
  area.addEventListener("drop", e => { e.preventDefault(); enviarArquivo(e.dataTransfer.files[0]); });
  el("impMapa").addEventListener("change", e => {
    if(e.target.id === "impAbaTx" || e.target.id === "impAbaCt"){
      // outra aba: o servidor não sabe sugerir de novo, então limpa as escolhas daquela parte
      const m = lerMapa();
      const s = {aba_transacoes: m.aba_transacoes, mapa_transacoes: e.target.id === "impAbaTx" ? {} : m.mapa_transacoes,
                 aba_contas: m.aba_contas, mapa_contas: e.target.id === "impAbaCt" ? sugerirContas(m.aba_contas) : m.mapa_contas,
                 mascarar: m.mascarar};
      desenharMapa(s);
    }
    agendarPrevia();
  });
  ["impNome", "impConfirmacao"].forEach(id => el(id).addEventListener("input", validarFormulario));
  el("impAceite").addEventListener("change", validarFormulario);
  el("impForm").addEventListener("submit", substituir);
  el("impModelo").addEventListener("click", e => baixar("/api/importacao/modelo", e.currentTarget));
  el("impDemo").addEventListener("click", voltarDemonstracao);
}

/* sugestão simples para a aba de contas escolhida à mão: colunas com o nome do campo */
function sugerirContas(aba){
  if(aba == null) return {};
  const nome = t => (t || "").normalize("NFD").replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
  const cab = envio.abas[aba].cabecalho.map(nome), mapa = {};
  [["id_conta", ["idconta", "conta", "codigo", "id"]], ["tipo_titular", ["tipotitular", "titular", "tipo"]],
   ["data_abertura", ["dataabertura", "abertura"]]].forEach(([campo, nomes]) => {
    const i = cab.findIndex(c => nomes.includes(c)); if(i >= 0) mapa[campo] = i;
  });
  return mapa;
}

export function mostrar(){ carregarBase(); }
