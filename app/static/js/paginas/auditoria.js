/* NEXO — tela Auditoria de acessos: últimos eventos registrados no banco. */
import {api} from "../nucleo/api.js";
import {pode} from "../nucleo/sessao.js";
import {ui} from "../nucleo/ui.js";
import {el, esc, fmtDataHora} from "../nucleo/utilidades.js";

const nomes = {login:"Login", logout:"Logout", login_falhou:"Login inválido", login_negado_inativo:"Login de usuário desativado",
  login_bloqueado:"Login com conta bloqueada", login_email_pendente:"Login com e-mail pendente",
  cadastro:"Novo cadastro", recuperacao_solicitada:"Recuperação solicitada", senha_redefinida:"Senha redefinida",
  email_confirmado:"E-mail confirmado", email_confirmado_manual:"E-mail confirmado pelo admin",
  confirmacao_reenviada:"Confirmação reenviada", contato_alterado:"Contato alterado",
  convite_criado:"Convite criado", convite_revogado:"Convite revogado", limite_ip:"Limite de tentativas (IP)",
  email_falhou:"Falha no envio de e-mail", usuario_alterado:"Usuário alterado", acesso_negado:"Acesso negado", admin_criado:"Administrador criado"};
const alerta = new Set(["login_falhou","login_negado_inativo","login_bloqueado","email_falhou","acesso_negado","limite_ip"]);
async function carregar(){
  if(!pode("ver_auditoria")) return;
  try{
    const {eventos} = await api("/api/auditoria");
    el("audBody").innerHTML = eventos.map(e=>`<tr>
      <td>${fmtDataHora(e.data)}</td>
      <td>${alerta.has(e.evento)?`<span class="pill analise">${nomes[e.evento]}</span>`:`<span class="pill normal">${nomes[e.evento]||esc(e.evento)}</span>`}</td>
      <td>${e.documento||"—"}</td><td>${esc(e.detalhe||"—")}</td><td>${esc(e.ip||"—")}</td></tr>`).join("")
      || `<tr><td colspan="5" class="empty">Nenhum evento registrado.</td></tr>`;
  } catch(err){ ui.toast(esc(err.message), true); }
}
export function iniciar(){ el("audAtualizar").addEventListener("click", carregar); }

export const mostrar = carregar;
