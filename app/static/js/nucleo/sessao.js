/* NEXO — usuário logado e permissões por cargo.

   A interface só esconde o que o cargo não pode usar; quem realmente bloqueia é a
   API, que confere a permissão em cada pedido.
*/
import {api} from "./api.js";
import {estado} from "./estado.js";
import {el, iniciais} from "./utilidades.js";

export const pode = permissao => !!estado.usuario?.permissoes.includes(permissao);

export const PERMISSAO_PAGINA = {simulador:"simular", relatorios:"relatorios", config:"configurar",
                                 usuarios:"gerenciar_usuarios", auditoria:"ver_auditoria"};

export async function carregarUsuario(){
  const r = await api("/auth/eu");
  Object.assign(estado, {usuario:r.usuario, cargos:r.cargos, permissoes:r.permissoes, emailConfigurado:r.email_configurado});
  const u = r.usuario;
  el("userNome").textContent = u.nome;
  el("userCargo").textContent = `${u.cargo_nome} · ${u.documento}`;
  el("userAvatar").textContent = el("chipAvatar").textContent = iniciais(u.nome);
  el("chipCargo").textContent = u.cargo_nome;
  document.querySelectorAll("#nav button[data-page]").forEach(b => {
    const perm = PERMISSAO_PAGINA[b.dataset.page];
    b.hidden = perm ? !pode(perm) : false;
  });
  el("navAdmin").hidden = !pode("gerenciar_usuarios") && !pode("ver_auditoria");
  ["simular","exportar"].forEach(p => document.body.classList.toggle("sem-"+p, !pode(p)));
}
