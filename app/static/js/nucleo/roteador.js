/* NEXO — navegação entre telas (#endereço) e carregamento sob demanda dos módulos.

   Cada tela é um módulo em js/paginas/ que pode exportar:
     iniciar()        → uma vez, quando o módulo é carregado (liga botões e campos)
     atualizar()      → a cada análise nova (evento "dados")
     reclassificar()  → quando os limiares mudam (evento "reclassificado")
     mostrar(param)   → toda vez que a tela é aberta
   O código de uma tela só é baixado na primeira vez em que ela é aberta.
*/
import {estado, ouvir} from "./estado.js";
import {PERMISSAO_PAGINA, pode} from "./sessao.js";
import {ui} from "./ui.js";
import {el} from "./utilidades.js";

const TITULOS = {
  dashboard:"Visão geral", transacoes:"Transações", rede:"Rede de transações",
  contas:"Contas em análise", conta:"Detalhes da conta", simulador:"Simulador de transações",
  relatorios:"Relatórios", arquitetura:"Arquitetura do sistema", config:"Configurações",
  usuarios:"Usuários e cargos", auditoria:"Auditoria de acessos"
};

const MODULOS = {
  dashboard:   () => import("../paginas/dashboard.js"),
  transacoes:  () => import("../paginas/transacoes.js"),
  rede:        () => import("../paginas/rede.js"),
  contas:      () => import("../paginas/contas.js"),
  conta:       () => import("../paginas/conta.js"),
  simulador:   () => import("../paginas/simulador.js"),
  relatorios:  () => import("../paginas/relatorios.js"),
  arquitetura: () => import("../paginas/arquitetura.js"),
  config:      () => import("../paginas/config.js"),
  usuarios:    () => import("../paginas/usuarios.js"),
  auditoria:   () => import("../paginas/auditoria.js"),
};

const carregados = {};   // nome → módulo já iniciado
const pedidos = {};      // nome → Promise do carregamento (evita carregar duas vezes)

function modulo(nome){
  return pedidos[nome] ||= MODULOS[nome]().then(m => {
    m.iniciar?.();
    if(estado.dados) m.atualizar?.();
    carregados[nome] = m;
    return m;
  });
}

ouvir("dados", () => Object.values(carregados).forEach(m => m.atualizar?.()));
ouvir("reclassificado", () => Object.values(carregados).forEach(m => m.reclassificar?.()));

export async function irPara(pagina, param){
  if(!TITULOS[pagina]) pagina = "dashboard";
  const perm = PERMISSAO_PAGINA[pagina];
  if(perm && !pode(perm)){
    ui.toast(`O cargo ${estado.usuario.cargo_nome} não tem acesso a esta tela.`, true);
    pagina = "dashboard";
  }
  document.querySelectorAll(".page").forEach(p=>p.classList.remove("active"));
  el("page-"+pagina).classList.add("active");
  el("pageTitle").textContent = TITULOS[pagina];
  document.querySelectorAll("#nav button").forEach(b=>b.classList.toggle("active", b.dataset.page===pagina));
  el("sidebar").classList.remove("open");
  const hash = pagina==="conta" ? `#conta/${param}` : `#${pagina}`;
  if(location.hash !== hash) history.pushState(null, "", hash);
  window.scrollTo({top:0, behavior:"instant"});
  const m = await modulo(pagina);
  m.mostrar?.(param);
}

export function rotaAtual(){
  const [pagina, param] = location.hash.slice(1).split("/");
  return irPara(pagina || "dashboard", param);
}
