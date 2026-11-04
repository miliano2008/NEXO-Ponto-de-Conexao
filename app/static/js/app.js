/* =========================================================
   NEXO — ponto de entrada da aplicação (após o login)

   Organização (ES modules, sem etapa de compilação):
     nucleo/   → utilidades, estado, API, sessão, dados, gráficos, janelas e roteador
     paginas/  → uma tela por arquivo, carregada sob demanda pelo roteador
   Todas as métricas vêm do backend Python (app/servidor.py → nucleo/analise.py).
   ========================================================= */
import {api} from "./nucleo/api.js";
import {carregar} from "./nucleo/dados.js";
import {estado} from "./nucleo/estado.js";
import {irPara, rotaAtual} from "./nucleo/roteador.js";
import {carregarUsuario} from "./nucleo/sessao.js";
import {ui} from "./nucleo/ui.js";
import {el, esc, fmtNum} from "./nucleo/utilidades.js";

async function init(){
  el("overlay").addEventListener("click", e => { if(e.target.id==="overlay") ui.closeModal(); });
  document.addEventListener("keydown", e => { if(e.key==="Escape"){ ui.closeModal(); ui.closeDrawer(); } });

  el("nav").addEventListener("click", e=>{
    const b = e.target.closest("button[data-page]"); if(b) irPara(b.dataset.page);
  });
  // data-conta abre o detalhe; data-goto navega; data-simular abre o simulador com a conta de origem
  document.addEventListener("click", e=>{
    const fechar = e.target.closest("[data-close]");
    if(fechar){ fechar.dataset.close==="modal" ? ui.closeModal() : ui.closeDrawer(); return; }
    const sim = e.target.closest("[data-simular]");
    if(sim){ e.preventDefault(); ui.closeDrawer(); irPara("simulador", sim.dataset.simular); return; }
    const conta = e.target.closest("[data-conta]");
    if(conta){ e.preventDefault(); ui.closeModal(); ui.closeDrawer(); irPara("conta", conta.dataset.conta); return; }
    const goto = e.target.closest("[data-goto]");
    if(goto){ e.preventDefault(); irPara(goto.dataset.goto); }
  });
  window.addEventListener("popstate", rotaAtual);

  el("periodSelect").addEventListener("change", async e=>{
    estado.periodo = +e.target.value;
    el("periodLabel").textContent = estado.periodo ? `últimos ${estado.periodo} dias` : "base completa";
    try{ await carregar(); } catch(err){ ui.toast(esc(err.message), true); }
  });

  el("btnNotif").addEventListener("click", ()=>{
    const alerta = estado.dados.contas.filter(c=>c.status==="Alta relevância"||c.status==="Em análise").slice(0,5);
    ui.modal("Notificações", `<p style="margin-top:0;font-size:13px">Contas acima dos limiares atuais:</p>
      ${alerta.map(c=>`<div class="note" style="margin-bottom:10px">Conta <a href="#" data-conta="${c.id}" class="mono-id">${c.id}</a> — ${c.status} (score ${fmtNum(c.score,1)}). Necessita investigação.</div>`).join("") || "<p>Nenhuma conta acima do limiar.</p>"}
      <p style="font-size:12px;color:var(--ink-3);margin-bottom:0">Alertas gerados a partir do score provisório do backend.</p>`);
  });
  el("btnSair").addEventListener("click", async ()=>{
    await api("/auth/sair", {method:"POST"}).catch(()=>{});
    location.href = "/login";
  });
  el("menuToggle").addEventListener("click", ()=> el("sidebar").classList.toggle("open"));

  try{
    await carregarUsuario();
    await carregar();
    await rotaAtual();
  } catch(err){
    el("sysStatus").textContent = "Backend indisponível";
    document.querySelector(".content").insertAdjacentHTML("afterbegin",
      `<div class="note warn" style="margin-bottom:16px">Não foi possível carregar os dados do backend: ${esc(err.message)}. Verifique se o NEXO está em execução (iniciar.bat).</div>`);
  }
}

init();
