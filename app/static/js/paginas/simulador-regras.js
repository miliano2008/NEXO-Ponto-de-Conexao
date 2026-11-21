/* NEXO — simulador (Fase 4): prévia das regras por modalidade, quadro das regras (o
   administrador ajusta ação e limites) e "Salvar como cenário". */
import {api} from "../nucleo/api.js";
import {estado} from "../nucleo/estado.js";
import {pode} from "../nucleo/sessao.js";
import {ui} from "../nucleo/ui.js";
import {el, esc, fmtBRL, fmtData, lerBRL, mascararCampoBRL, valorParaCampo} from "../nucleo/utilidades.js";

const CLASSE_ORIGEM = {"Regulamentação": "reg", "Prática de mercado (configurável)": "mercado", "Parâmetro do administrador": "admin"};
const ICONE = {ok: "✓", alerta: "⚠", bloqueio: "⛔"};
const NOME_ACAO = {bloquear: "Bloqueia", alertar: "Alerta", desligada: "Desligada"};
export const chipOrigem = o => `<span class="chip origem ${CLASSE_ORIGEM[o] || ""}">${esc(o)}</span>`;
const pillAcao = a => `<span class="pill ${a === "bloquear" ? "alta" : a === "alertar" ? "analise" : "normal"}">${NOME_ACAO[a] || esc(a)}</span>`;

let regras = [];

/* ---------- prévia enquanto a pessoa preenche ---------- */
let temporizador = null, pedido = 0;
export function agendarPrevia(lerFormulario){
  clearTimeout(temporizador);
  temporizador = setTimeout(() => previa(lerFormulario()), 250);
}

async function previa(corpo){
  const alvo = el("simPrevia"), meu = ++pedido;
  if(!corpo.valor || corpo.de === corpo.para){ alvo.innerHTML = ""; el("simEnviar").disabled = false; return; }
  let r;
  try{ r = await api("/api/transacoes/validar", {method: "POST", body: JSON.stringify(corpo)}); }
  catch(err){ if(meu === pedido){ alvo.innerHTML = `<div class="msg-erro-mini">${esc(err.message)}</div>`; } return; }
  if(meu !== pedido) return;   // chegou uma prévia mais nova
  const banco = (id, b) => b ? `<b>${id}</b> · ${esc(b.instituicao)} · ${esc(b.tipo_conta)} · chave PIX ${esc(b.chave_pix.toLowerCase())}` : id;
  const datas = r.transacoes.map(t => fmtData(t.data).slice(0, 5));
  // uma linha por regra: o pior resultado entre as repetições
  const porRegra = {};
  r.transacoes.forEach(t => t.verificacoes.forEach(v => {
    const ordem = {ok: 0, alerta: 1, bloqueio: 2};
    const atual = porRegra[v.regra];
    if(!atual || ordem[v.resultado] > ordem[atual.resultado]) porRegra[v.regra] = {...v, quando: `${fmtData(t.data)} ${t.hora}`};
  }));
  const linhas = Object.values(porRegra);
  alvo.innerHTML = `
    <div class="previa-bancos">${banco(corpo.de, r.origem)} → ${banco(corpo.para, r.destino)}
      <span class="chip ${r.mesma_instituicao ? "" : "sim"}">${r.mesma_instituicao ? "Mesma instituição" : "Entre instituições"}</span></div>
    ${r.transacoes.length > 1 ? `<div class="previa-datas">${r.transacoes.length} transações: ${datas.join(", ")}</div>` : ""}
    <ul class="previa-regras">${linhas.map(v => `<li class="${v.resultado}"><span class="ic">${ICONE[v.resultado]}</span>
      <span><b>${esc(v.nome)}</b> ${chipOrigem(v.origem)}<br>${esc(v.mensagem)}${r.transacoes.length > 1 && v.resultado !== "ok" ? ` <small>(${esc(v.quando)})</small>` : ""}</span></li>`).join("")
      || `<li class="ok"><span class="ic">✓</span><span>Nenhuma regra ativa para esta modalidade.</span></li>`}</ul>
    ${r.bloqueios ? `<div class="msg-erro-mini" style="margin:8px 0 0">A simulação está bloqueada pelas regras acima. Ajuste a data, a hora, a modalidade ou as contas.</div>` : ""}`;
  el("simEnviar").disabled = r.bloqueios > 0;
}

/* ---------- quadro das regras ---------- */
function limites(r){
  const p = r.parametros;
  if("limite" in p) return `${fmtBRL(p.limite)} das ${p.inicio} às ${p.fim}`;
  if("inicio" in p) return `${p.inicio} às ${p.fim}`;
  return "—";
}

export async function carregarRegras(){
  try{ regras = (await api("/api/modalidades")).regras; }
  catch(err){ el("simRegras").innerHTML = `<tr><td colspan="7" class="empty">${esc(err.message)}</td></tr>`; return; }
  const admin = pode("administrar_regras");
  el("simRegras").innerHTML = regras.map(r => `
    <tr><td>${esc(r.modalidade)}</td>
      <td><b>${esc(r.nome)}</b><br><span style="font-size:12px;color:var(--ink-3)">${esc(r.descricao)}</span>
        ${r.ajustado_por ? `<br><span style="font-size:11.5px;color:var(--ink-3)">Ajustada por ${esc(r.ajustado_por)}</span>` : ""}</td>
      <td>${chipOrigem(r.origem)}</td><td>${pillAcao(r.acao)}</td><td style="font-size:12.5px">${limites(r)}</td>
      <td class="num" title="Transações da base que ficariam fora desta regra">${r.base_fora}</td>
      <td>${admin ? `<button class="btn ghost sm" data-editar-regra="${r.id}">Ajustar</button>` : ""}</td></tr>`).join("");
}

export function editarRegra(id){
  const r = regras.find(x => x.id === id); if(!r) return;
  const p = r.parametros;
  ui.modal(`Ajustar: ${r.nome}`, `
    <form id="formRegra" class="form-senha" novalidate>
      <p style="margin:0 0 12px;font-size:13px">${chipOrigem(r.origem)} ${esc(r.descricao)}<br>
        <span style="font-size:12px;color:var(--ink-3)">Fonte: ${esc(r.fonte)}</span></p>
      <label>Ação<select id="rgAcao">${["bloquear", "alertar", "desligada"].filter(a => !(r.id === "pix_24h" && a === "bloquear"))
        .map(a => `<option value="${a}" ${a === r.acao ? "selected" : ""}>${NOME_ACAO[a]}</option>`).join("")}</select></label>
      ${"limite" in p ? `<label>Limite por transação (R$)<input id="rgLimite" inputmode="numeric" value="${valorParaCampo(p.limite)}"></label>` : ""}
      ${"inicio" in p ? `<label>Início<input type="time" id="rgInicio" value="${p.inicio}"></label><label>Fim<input type="time" id="rgFim" value="${p.fim}"></label>` : ""}
      <p style="font-size:12px;color:var(--ink-3);margin:0 0 12px">Padrão: ${NOME_ACAO[r.padrao.acao]}${Object.keys(r.padrao.parametros).length ? " · " + esc(Object.entries(r.padrao.parametros).map(([k, v]) => `${k} ${k === "limite" ? fmtBRL(v) : v}`).join(", ")) : ""}.
        A mudança vale para todas as simulações e fica na auditoria.</p>
      <div class="msg-erro-mini" id="rgErro" hidden></div>
      <div style="display:flex;gap:8px"><button class="btn" type="submit">Salvar</button>
        <button class="btn ghost" type="button" id="rgPadrao">Voltar ao padrão</button></div>
    </form>`);
  if(el("rgLimite")) mascararCampoBRL(el("rgLimite"));
  const enviar = async corpo => {
    try{ await api(`/api/modalidades/${id}`, {method: "POST", body: JSON.stringify(corpo)});
         ui.closeModal(); ui.toast("✓ Regra atualizada."); await carregarRegras(); el("simDe").dispatchEvent(new Event("change")); }
    catch(err){ el("rgErro").textContent = err.message; el("rgErro").hidden = false; }
  };
  el("formRegra").addEventListener("submit", e => {
    e.preventDefault();
    const parametros = {};
    if(el("rgLimite")) parametros.limite = lerBRL(el("rgLimite").value);
    if(el("rgInicio")){ parametros.inicio = el("rgInicio").value; parametros.fim = el("rgFim").value; }
    enviar({acao: el("rgAcao").value, parametros});
  });
  el("rgPadrao").addEventListener("click", () => enviar({padrao: true}));
}

/* ---------- salvar como cenário ---------- */
export function salvarCenario(irParaHistorico){
  const qtd = estado.dados.simulacao.transacoes_simuladas;
  if(!qtd){ ui.toast("Simule ao menos uma transação antes de salvar o cenário.", true); return; }
  ui.modal("Salvar como cenário", `
    <form id="formCenario" class="form-senha" novalidate>
      <p style="margin:0 0 12px;font-size:13px">Guarda as <b>${qtd}</b> transação(ões) simulada(s) e o resultado desta execução
        (com e sem a simulação, no recorte atual). O cenário não muda depois, mesmo que a base mude.</p>
      <label>Nome<input id="cnNome" maxlength="80" placeholder="Ex.: PIX noturno recorrente para C030" required></label>
      <label>Descrição (opcional)<textarea id="cnDescricao" maxlength="500" rows="3" style="font:inherit;font-size:14px;border:1px solid var(--line);border-radius:8px;padding:9px 11px"></textarea></label>
      <div class="msg-erro-mini" id="cnErro" hidden></div>
      <button class="btn" type="submit" id="cnSalvar">Salvar cenário</button>
    </form>`);
  setTimeout(() => el("cnNome").focus(), 30);
  el("formCenario").addEventListener("submit", async e => {
    e.preventDefault(); el("cnSalvar").disabled = true;
    try{
      await api("/api/cenarios", {method: "POST", body: JSON.stringify({nome: el("cnNome").value,
        descricao: el("cnDescricao").value, recorte: estado.recorte})});
      ui.closeModal();
      ui.toast(`✓ Cenário salvo. <a href="#" data-goto="historico" style="color:inherit;font-weight:700">Abrir o histórico</a>`);
      irParaHistorico?.();
    } catch(err){ el("cnErro").textContent = err.message; el("cnErro").hidden = false; el("cnSalvar").disabled = false; }
  });
}
