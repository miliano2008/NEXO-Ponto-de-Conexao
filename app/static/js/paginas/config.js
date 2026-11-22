/* NEXO — tela Configurações: limiares do score, preferências do usuário (Fase 5), limites das
   regras de risco (o administrador ajusta; os outros cargos consultam) e "sobre". */
import {api} from "../nucleo/api.js";
import {carregar, classificar} from "../nucleo/dados.js";
import {emitir, estado, ouvir} from "../nucleo/estado.js";
import {formularioPreferencias, prefs, salvar} from "../nucleo/preferencias.js";
import {pode} from "../nucleo/sessao.js";
import {ui} from "../nucleo/ui.js";
import {el, esc} from "../nucleo/utilidades.js";

const num = v => String(v).replace(".", ",");
let parametros = [];

function render(){
  const d = estado.dados;
  el("pesosInfo").innerHTML = Object.entries(d.simulacao.pesos).map(([k,v])=>`<dt>${k}</dt><dd>${v}</dd>`).join("");
  el("sobre").innerHTML = `
    <dt>Versão</dt><dd>1.0 — Fase 6: importação de bases</dd>
    <dt>Base em uso</dt><dd>${esc(d.base?.nome || "Base de demonstração")} (${d.dashboard.total_contas} contas, ${d.simulacao.total_base_original} transações)</dd>
    <dt>Origem dos dados</dt><dd>${d.simulacao.mysql ? "Tabelas contas/transacoes no MySQL" : d.base?.origem === "arquivo" ? "Base importada (SQLite local)" : "CSVs de demonstração"}</dd>
    <dt>Cálculo</dt><dd>nucleo/analise.py — NetworkX + NumPy</dd>
    <dt>Servidor</dt><dd>Flask (app/servidor.py)</dd>
    <dt>Banco de dados</dt><dd>${esc(d.simulacao.fonte_dados)}${d.simulacao.mysql?" · conexão SSL":" (modo local)"}</dd>
    <dt>Autenticação</dt><dd>E-mail ou CPF/CNPJ + senha (${d.simulacao.mysql ? "tabela usuarios no MySQL" : "SQLite: banco/dados/nexo.db"}), recuperação por e-mail</dd>
    <dt>Usuário atual</dt><dd>${esc(estado.usuario.nome)} · ${esc(estado.usuario.cargo_nome)}</dd>`;
  mostrarLimiares();
}

function mostrarLimiares(){
  el("thrA").value = estado.limiares.analise; el("thrB").value = estado.limiares.alta;
  el("thrAOut").textContent = estado.limiares.analise; el("thrBOut").textContent = estado.limiares.alta;
}

/* ---------- limites das regras de risco ---------- */
function desenharParametros(){
  const admin = pode("administrar_regras");
  el("cfgRiscoSalvar").hidden = el("cfgRiscoPadrao").hidden = !admin;
  el("cfgRiscoSub").textContent = admin
    ? "Usados pelo Painel de risco em todas as análises. A mudança vale para todos e fica na auditoria."
    : "Usados pelo Painel de risco em todas as análises. Só o administrador altera.";
  el("cfgRisco").innerHTML = parametros.map(p => {
    const mudou = p.valor !== p.padrao;
    return `<tr${mudou ? ' class="ajustado"' : ""}><td><b>${esc(p.nome)}</b>${p.ajustado_por ? `<br><span style="font-size:11.5px;color:var(--ink-3)">Ajustado por ${esc(p.ajustado_por)}</span>` : ""}</td>
      <td style="font-size:12.5px">${esc(p.regras_nomes.join(", ") || "Comunidades em destaque")}</td>
      <td class="num">${admin ? `<input class="campo-num" data-param="${p.chave}" inputmode="decimal" value="${num(p.valor)}" aria-label="${esc(p.nome)}">` : `<b>${num(p.valor)}</b>`}</td>
      <td style="font-size:12.5px">${esc(p.unidade)}</td><td class="num">${num(p.padrao)}</td>
      <td style="font-size:12.5px">${num(p.min)} a ${num(p.max)}</td></tr>`;
  }).join("");
}

async function carregarParametros(){
  try{ parametros = (await api("/api/parametros-risco")).parametros; desenharParametros(); }
  catch(err){ el("cfgRisco").innerHTML = `<tr><td colspan="6" class="empty">${esc(err.message)}</td></tr>`; }
}

async function enviarParametros(corpo){
  el("cfgRiscoErro").hidden = true;
  try{
    parametros = (await api("/api/parametros-risco", {method: "POST", body: JSON.stringify(corpo)})).parametros;
    desenharParametros();
    await carregar();   // nova análise com os limites novos (o Painel de risco já mostra o resultado)
    ui.toast("✓ Limites salvos. A análise foi recalculada.");
  } catch(err){ el("cfgRiscoErro").textContent = err.message; el("cfgRiscoErro").hidden = false; }
}

export function iniciar(){
  const aplicar = () => {
    const a = +el("thrA").value, b = Math.max(+el("thrB").value, a + 5);
    estado.limiares.analise = a; estado.limiares.alta = b;
    el("thrAOut").textContent = a; el("thrBOut").textContent = b;
    classificar();
    emitir("reclassificado");
  };
  el("thrA").addEventListener("input", aplicar);
  el("thrB").addEventListener("input", aplicar);
  ["thrA", "thrB"].forEach(id => el(id).addEventListener("change", () =>
    salvar({limiar_analise: estado.limiares.analise, limiar_alta: estado.limiares.alta})));
  formularioPreferencias(el("cfgPreferencias"));
  ouvir("preferencias", () => {
    if(!el("page-config").classList.contains("active")) return;
    if(+el("thrA").value !== prefs.limiar_analise || +el("thrB").value !== prefs.limiar_alta){ mostrarLimiares(); classificar(); emitir("reclassificado"); }
  });
  el("cfgRiscoSalvar").addEventListener("click", () => {
    const valores = {};
    document.querySelectorAll("#cfgRisco input[data-param]").forEach(i => { valores[i.dataset.param] = i.value; });
    enviarParametros({valores});
  });
  el("cfgRiscoPadrao").addEventListener("click", async () => {
    if(!confirm("Voltar todos os limites das regras de risco ao padrão?")) return;
    enviarParametros({padrao: true});
  });
  carregarParametros();
}

export const atualizar = render;
