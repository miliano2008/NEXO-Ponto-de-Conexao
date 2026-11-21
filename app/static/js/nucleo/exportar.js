/* NEXO — botões de exportação de relatórios (Fase 5): PDF, Excel, Word, PowerPoint e CSV.

   O arquivo é pedido com fetch (e não por um link comum) para que um erro do servidor apareça
   como aviso na tela, em vez de abrir uma página com o erro. O formato preferido do usuário
   (Preferências) vem primeiro e em destaque. */
import {prefs} from "./preferencias.js";
import {ui} from "./ui.js";
import {el, esc} from "./utilidades.js";

export const FORMATOS = [["pdf", "PDF", "📄"], ["xlsx", "Excel", "📊"], ["docx", "Word", "📝"], ["pptx", "PowerPoint", "📽️"], ["csv", "CSV", "🗂️"]];

export function botoes(atributos){
  const preferido = prefs.relatorio_formato || "pdf";
  const ordem = [...FORMATOS].sort((a, b) => (b[0] === preferido) - (a[0] === preferido));
  return `<div class="botoes-export" ${atributos}>${ordem.map(([f, nome, icone]) =>
    `<button class="btn ${f === preferido ? "" : "ghost"} sm" data-formato="${f}" title="Baixar em ${nome}">${icone} ${nome}</button>`).join("")}</div>`;
}

export async function baixar(url, botao){
  if(botao) botao.disabled = true;
  el("loading").classList.add("on");
  try{
    const r = await fetch(url, {headers: {"X-Requested-With": "NEXO"}});
    if(r.status === 401){ location.href = "/login"; return; }
    if(!r.ok){ const corpo = await r.json().catch(() => ({})); throw new Error(corpo.erro || `Erro ${r.status} no servidor`); }
    const nome = (r.headers.get("Content-Disposition") || "").match(/filename="?([^";]+)"?/)?.[1] || "relatorio_nexo";
    const link = document.createElement("a");
    link.href = URL.createObjectURL(await r.blob());
    link.download = nome;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 4000);
    ui.toast(`✓ ${esc(nome)} baixado.`);
  } catch(err){ ui.toast(esc(err.message), true); }
  finally{ el("loading").classList.remove("on"); if(botao) botao.disabled = false; }
}
