/* NEXO — tela Usuários e cargos (administrador): cargos, contato, confirmação de e-mail e convites. */
import {api} from "../nucleo/api.js";
import {estado} from "../nucleo/estado.js";
import {pode} from "../nucleo/sessao.js";
import {ui} from "../nucleo/ui.js";
import {digitos, el, esc, fmtDataHora} from "../nucleo/utilidades.js";

let lista = [], convites = [];

function render(){
  const busca = el("usrBusca").value.trim().toLowerCase(), buscaNum = digitos(busca);
  const filtrados = lista.filter(u => !busca || [u.nome,u.documento,u.email,u.telefone].join(" ").toLowerCase().includes(busca)
                                              || (buscaNum && (digitos(u.documento).includes(buscaNum) || digitos(u.telefone).includes(buscaNum))));
  el("usrBody").innerHTML = filtrados.map(u => {
    const eu = u.id === estado.usuario.id;
    const statusEmail = u.email_confirmado
      ? '<span class="pill normal" title="E-mail confirmado">confirmado</span>'
      : `<span class="pill analise" title="Ainda não clicou no link de confirmação">pendente</span>
         <button class="btn ghost sm" data-confirmar="${u.id}" title="Use depois de verificar a pessoa (ex.: pelo telefone)">Confirmar</button>`;
    return `<tr>
      <td><strong>${esc(u.nome)}</strong>${eu?' <span class="chip">você</span>':""}</td>
      <td style="white-space:nowrap">${u.tipo_documento} ${u.documento}</td>
      <td><div>${esc(u.email)} ${statusEmail}</div>
          <div style="font-size:12px;color:var(--ink-3)">📞 ${esc(u.telefone || "sem telefone")}</div></td>
      <td><select class="cargo-select" data-cargo="${u.id}" ${eu?"disabled":""}>
        ${Object.entries(estado.cargos).map(([k,v])=>`<option value="${k}" ${k===u.cargo?"selected":""}>${v}</option>`).join("")}</select></td>
      <td>${u.ativo ? '<span class="pill normal">Ativo</span>' : '<span class="pill alta">Desativado</span>'}</td>
      <td>${fmtDataHora(u.ultimo_login)}</td>
      <td><div style="display:flex;flex-direction:column;gap:5px;align-items:stretch">
        <button class="btn ghost sm" data-contato="${u.id}">Editar contato</button>
        ${eu?"":`<button class="btn ghost sm" data-ativo="${u.id}" data-valor="${!u.ativo}">${u.ativo?"Desativar":"Reativar"}</button>`}</div></td></tr>`;
  }).join("") || `<tr><td colspan="7" class="empty">Nenhum usuário encontrado.</td></tr>`;
}

function matriz(){
  const cargos = Object.keys(estado.cargos);
  const nomes = {consultar:"Consultar dashboard, transações, rede e contas", relatorios:"Relatórios",
    exportar:"Exportar JSON", simular:"Simulador de transações", configurar:"Configurações",
    ver_auditoria:"Auditoria de acessos", gerenciar_usuarios:"Gerenciar usuários, cargos e convites"};
  el("matrizPerm").innerHTML = `<table><thead><tr><th>Permissão</th>${cargos.map(c=>`<th style="text-align:center">${estado.cargos[c]}</th>`).join("")}</tr></thead><tbody>
    ${Object.entries(estado.permissoes).map(([p,cs])=>`<tr><td>${nomes[p]||p}</td>${cargos.map(c=>`<td style="text-align:center">${cs.includes(c)?'<b style="color:var(--green)">✓</b>':'<span style="color:var(--ink-3)">—</span>'}</td>`).join("")}</tr>`).join("")}
    </tbody></table>`;
}

function renderConvites(){
  const cor = {Ativo:"normal", Esgotado:"revisar", Expirado:"revisar", Revogado:"alta"};
  el("convBody").innerHTML = convites.map(c => `<tr>
      <td class="mono-id">${esc(c.codigo)}</td><td>${esc(c.cargo_nome)}</td>
      <td class="num">${c.usos} / ${c.max_usos}</td><td>${fmtDataHora(c.expira_em)}</td>
      <td>${esc(c.criado_por || "—")}</td><td><span class="pill ${cor[c.situacao]}">${c.situacao}</span></td>
      <td class="num">${c.situacao==="Ativo"?`<button class="btn ghost sm" data-revogar="${c.id}">Revogar</button>`:""}</td></tr>`).join("")
    || `<tr><td colspan="7" class="empty">Nenhum código gerado ainda.</td></tr>`;
}

async function carregar(){
  if(!pode("gerenciar_usuarios")) return;
  el("usrEmailAviso").hidden = estado.emailConfigurado;
  try{
    const [u, c] = await Promise.all([api("/api/usuarios"), api("/api/convites")]);
    lista = u.usuarios; convites = c.convites;
    render(); matriz(); renderConvites();
  } catch(err){ ui.toast(esc(err.message), true); }
}

async function alterar(id, dados){
  try{
    const r = await api(`/api/usuarios/${id}`, {method:"PATCH", body:JSON.stringify(dados)});
    let msg = `${esc(r.usuario.nome)}: ${r.usuario.cargo_nome} · ${r.usuario.ativo?"ativo":"desativado"}`;
    if(r.confirmacao_enviada === true) msg = `${esc(r.usuario.nome)}: e-mail alterado. Link de confirmação enviado para o novo endereço.`;
    if(r.confirmacao_enviada === false) msg = `${esc(r.usuario.nome)}: e-mail alterado, mas o link não pôde ser enviado. Use “Confirmar” após verificar a pessoa.`;
    if(dados.confirmar_email) msg = `${esc(r.usuario.nome)}: e-mail confirmado manualmente.`;
    ui.toast(msg);
    ui.closeModal();
  } catch(err){ ui.toast(esc(err.message), true); }
  carregar();
}

function editarContato(id){
  const u = lista.find(x => x.id === +id);
  ui.modal(`Contato de ${u.nome}`, `
    <div class="note" style="margin:0 0 14px">Use para atender um pedido de troca de e-mail: confirme a identidade da pessoa pelo telefone cadastrado antes de alterar.
      Um e-mail novo fica <b>pendente</b> até a pessoa clicar no link enviado a ele.</div>
    <div class="field" style="margin-bottom:12px"><label for="ctEmail">E-mail</label><input type="text" id="ctEmail" value="${esc(u.email)}" style="width:100%"></div>
    <div class="field" style="margin-bottom:16px"><label for="ctTel">Telefone com DDD</label><input type="text" id="ctTel" value="${esc(u.telefone||"")}" placeholder="(11) 91234-5678" style="width:100%"></div>
    <button class="btn" data-salvar-contato="${u.id}">Salvar</button> <button class="btn ghost" data-close="modal">Cancelar</button>`);
}

async function gerarConvite(){
  const cargo = el("convCargo").value;
  if(cargo === "administrador" && !confirm("Este código dá acesso de ADMINISTRADOR a quem usar. Gerar mesmo assim?")) return;
  try{
    const r = await api("/api/convites", {method:"POST", body:JSON.stringify(
      {cargo, dias:+el("convDias").value, max_usos:+el("convUsos").value})});
    el("convNovo").innerHTML = `Código gerado: <b class="mono-id" style="font-size:16px">${esc(r.codigo)}</b>
      <button class="btn ghost sm" id="convCopiar">Copiar</button><br>
      <span style="font-size:12px">Copie agora: por segurança ele <b>não será mostrado de novo</b>. Envie só para quem deve ter este cargo.</span>`;
    el("convNovo").hidden = false;
    el("convCopiar").onclick = () => navigator.clipboard?.writeText(r.codigo).then(()=>ui.toast("Código copiado."));
    carregar();
  } catch(err){ ui.toast(esc(err.message), true); }
}

export function iniciar(){
  el("convCargo").innerHTML = ["analista","auditor","visualizador","administrador"]
    .map(c=>`<option value="${c}">${{analista:"Analista",auditor:"Auditor",visualizador:"Visualizador",administrador:"Administrador"}[c]}</option>`).join("");
  el("convGerar").addEventListener("click", gerarConvite);
  el("convBody").addEventListener("click", async e=>{
    const b = e.target.closest("[data-revogar]"); if(!b) return;
    try{ await api(`/api/convites/${b.dataset.revogar}`, {method:"DELETE"}); ui.toast("Convite revogado."); carregar(); }
    catch(err){ ui.toast(esc(err.message), true); }
  });
  el("usrBusca").addEventListener("input", render);
  el("usrBody").addEventListener("change", e=>{
    const s = e.target.closest("[data-cargo]"); if(s) alterar(s.dataset.cargo, {cargo:s.value});
  });
  el("usrBody").addEventListener("click", e=>{
    const a = e.target.closest("[data-ativo]"); if(a) alterar(a.dataset.ativo, {ativo: a.dataset.valor==="true"});
    const c = e.target.closest("[data-confirmar]");
    if(c && confirm("Confirmar este e-mail manualmente? Faça isso só depois de verificar a pessoa.")) alterar(c.dataset.confirmar, {confirmar_email:true});
    const k = e.target.closest("[data-contato]"); if(k) editarContato(k.dataset.contato);
  });
  el("modalBody").addEventListener("click", e=>{
    const b = e.target.closest("[data-salvar-contato]");
    if(b) alterar(b.dataset.salvarContato, {email: el("ctEmail").value.trim(), telefone: el("ctTel").value.trim()});
  });
}

export const mostrar = carregar;
