/* NEXO — tela Contas em análise: ranking com filtros e ordenação por qualquer métrica
   (clique no cabeçalho alterna crescente/decrescente). Respeita os filtros globais. */
import {estado} from "../nucleo/estado.js";
import {contasVisiveis, situacao} from "../nucleo/filtros.js";
import {chipInvestigacao, el, fmtBRL, fmtNum, pill, pillRisco} from "../nucleo/utilidades.js";

const ORDEM_INVEST = ["encaminhada", "em_analise", "investigada", "nao_iniciada", "sem_indicio"];
let ligado = false, ordem = {campo: "score", desc: true};

const valor = (c, campo) => campo === "investigacao" ? ORDEM_INVEST.length - ORDEM_INVEST.indexOf(situacao(c.id)) : c[campo];

function render(){
  const minScore = +el("fScore").value, minDeg = +el("fDeg").value;
  const com = el("fCom").value, st = el("fStat").value, risco = el("fRisco").value;
  el("scoreOut").textContent = minScore; el("degOut").textContent = minDeg;

  const sentido = ordem.desc ? -1 : 1;
  const lista = contasVisiveis()
    .filter(c => c.score>=minScore && c.degree>=minDeg && (!com||String(c.com)===com) && (!st||c.status===st)
                 && (!risco || c.nivel_risco===risco))
    .sort((a,b) => {
      const va = valor(a, ordem.campo), vb = valor(b, ordem.campo);
      return (typeof va === "string" ? va.localeCompare(vb) : va - vb) * sentido || b.score - a.score;
    });

  el("contasHead").querySelectorAll("th[data-ordem]").forEach(th => {
    const ativo = th.dataset.ordem === ordem.campo && !(th.textContent.startsWith("Status") && ordem.campo === "score");
    th.querySelector(".seta")?.remove();
    th.setAttribute("aria-sort", ativo ? (ordem.desc ? "descending" : "ascending") : "none");
    if(ativo) th.insertAdjacentHTML("beforeend", `<span class="seta">${ordem.desc ? "▼" : "▲"}</span>`);
  });

  el("contasBody").innerHTML = lista.length ? lista.map(c=>`
    <tr class="clickable" data-conta="${c.id}">
      <td style="color:var(--ink-3)">${c.ranking}</td>
      <td class="mono-id">${c.id}</td>
      <td class="num"><strong>${fmtNum(c.score,1)}</strong></td>
      <td class="num">${c.degree}</td>
      <td class="num">${c.inDeg} / ${c.outDeg}</td>
      <td class="num">${fmtNum(c.betw,3)}</td>
      <td class="num">${fmtNum(c.close,3)}</td>
      <td class="num">${fmtBRL(c.flow)}</td>
      <td class="num">${fmtNum(c.imbalance,3)}</td>
      <td class="num">${c.com}</td>
      <td>${pill(c.status)}</td>
      <td class="num">${c.risco ? `${pillRisco(c.nivel_risco)} <b>${c.risco}</b>` : pillRisco(c.nivel_risco)}</td>
      <td>${chipInvestigacao(situacao(c.id), estado.casos[c.id]?.situacao_nome)}</td></tr>`).join("")
    : `<tr><td colspan="13" class="empty">Nenhuma conta atende a esses critérios. Reduza o score ou o degree mínimo, ou limpe os filtros.</td></tr>`;
}
function init(){
  const sel = el("fCom").value;
  el("fCom").innerHTML = `<option value="">Todas</option>` + estado.dados.comunidades.map(c=>`<option value="${c.id}">Comunidade ${c.id}</option>`).join("");
  el("fCom").value = estado.dados.comunidades.some(c=>String(c.id)===sel) ? sel : "";
  el("fDeg").max = Math.max(...estado.dados.contas.map(c=>c.degree), 1);
  if(!ligado){
    ligado = true;
    ["fScore","fDeg","fCom","fStat","fRisco"].forEach(id=>el(id).addEventListener("input", render));
    el("contasHead").addEventListener("click", e => {
      const th = e.target.closest("th[data-ordem]"); if(!th) return;
      const campo = th.dataset.ordem;
      ordem = ordem.campo === campo ? {campo, desc: !ordem.desc} : {campo, desc: !["id", "ranking", "com"].includes(campo)};
      render();
    });
  }
  render();
}

export const atualizar = init;
export const reclassificar = render;
export const filtrar = render;
export const casos = render;
