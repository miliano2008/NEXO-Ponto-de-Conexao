/* NEXO — tela Configurações: limiares do score, tema, rótulos do grafo, alertas e "sobre". */
import {classificar} from "../nucleo/dados.js";
import {emitir, estado} from "../nucleo/estado.js";
import {el, esc} from "../nucleo/utilidades.js";

function render(){
  const d = estado.dados;
  el("pesosInfo").innerHTML = Object.entries(d.simulacao.pesos).map(([k,v])=>`<dt>${k}</dt><dd>${v}</dd>`).join("");
  el("sobre").innerHTML = `
    <dt>Versão</dt><dd>0.4 — Fase 0: estrutura modular, migrações e cache</dd>
    <dt>Origem dos dados</dt><dd>${d.simulacao.mysql ? "Tabelas contas/transacoes no MySQL" : "CSVs exportados do Excel"} (${d.dashboard.total_contas} contas, ${d.simulacao.total_base_original} transações)</dd>
    <dt>Cálculo</dt><dd>nucleo/analise.py — NetworkX + NumPy</dd>
    <dt>Servidor</dt><dd>Flask (app/servidor.py)</dd>
    <dt>Banco de dados</dt><dd>${esc(d.simulacao.fonte_dados)}${d.simulacao.mysql?" · conexão SSL":" (modo local)"}</dd>
    <dt>Autenticação</dt><dd>CPF/CNPJ + senha (${d.simulacao.mysql ? "tabela usuarios no MySQL" : "SQLite: banco/dados/nexo.db"}), recuperação por e-mail</dd>
    <dt>Usuário atual</dt><dd>${esc(estado.usuario.nome)} · ${esc(estado.usuario.cargo_nome)}</dd>`;
}
export function iniciar(){
  const aplicar = () => {
    estado.limiares.analise = +el("thrA").value;
    estado.limiares.alta = Math.max(+el("thrB").value, +el("thrA").value+5);
    el("thrAOut").textContent = estado.limiares.analise;
    el("thrBOut").textContent = estado.limiares.alta;
    classificar();
    emitir("reclassificado");
  };
  el("thrA").addEventListener("input", aplicar);
  el("thrB").addEventListener("input", aplicar);
  el("swTheme").addEventListener("click", e=>{
    const on = e.currentTarget.classList.toggle("on");
    document.documentElement.setAttribute("data-theme", on?"dark":"light");
    emitir("tema");
  });
  el("swLabels").addEventListener("click", e=> emitir("rotulos", e.currentTarget.classList.toggle("on")));
  el("swAlerts").addEventListener("click", e=> e.currentTarget.classList.toggle("on"));
}

export const atualizar = render;
