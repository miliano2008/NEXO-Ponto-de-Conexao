/* NEXO — tela Contas em análise: ranking pelo Score NEXO com filtros. */
import {estado} from "../nucleo/estado.js";
import {el, fmtBRL, fmtNum, pill} from "../nucleo/utilidades.js";

let ligado = false;
function render(){
  const minScore = +el("fScore").value, minDeg = +el("fDeg").value;
  const com = el("fCom").value, st = el("fStat").value;
  el("scoreOut").textContent = minScore; el("degOut").textContent = minDeg;

  const lista = [...estado.dados.contas]
    .filter(c => c.score>=minScore && c.degree>=minDeg && (!com||String(c.com)===com) && (!st||c.status===st))
    .sort((a,b)=>b.score-a.score);

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
      <td>${pill(c.status)}</td></tr>`).join("")
    : `<tr><td colspan="11" class="empty">Nenhuma conta atende a esses critérios. Reduza o score ou o degree mínimo.</td></tr>`;
}
function init(){
  const sel = el("fCom").value;
  el("fCom").innerHTML = `<option value="">Todas</option>` + estado.dados.comunidades.map(c=>`<option value="${c.id}">Comunidade ${c.id}</option>`).join("");
  el("fCom").value = estado.dados.comunidades.some(c=>String(c.id)===sel) ? sel : "";
  el("fDeg").max = Math.max(...estado.dados.contas.map(c=>c.degree), 1);
  if(!ligado){ ligado = true; ["fScore","fDeg","fCom","fStat"].forEach(id=>el(id).addEventListener("input", render)); }
  render();
}

export const atualizar = init;
export const reclassificar = render;
