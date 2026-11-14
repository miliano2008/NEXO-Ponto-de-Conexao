/* NEXO — página institucional: acesso rápido no banner, cabeçalho e menu do celular. */
import {digitos, el} from "./nucleo/utilidades.js";

// cabeçalho ganha sombra ao rolar a página
const topo = el("topo");
const marcarRolagem = () => topo.classList.toggle("rolou", window.scrollY > 8);
window.addEventListener("scroll", marcarRolagem, {passive: true});
marcarRolagem();

// menu do celular
const menu = el("menu"), botaoMenu = el("menuBotao");
botaoMenu.addEventListener("click", () => {
  const aberto = menu.classList.toggle("aberto");
  botaoMenu.setAttribute("aria-expanded", aberto);
});
menu.addEventListener("click", e => { if(e.target.closest("a")){ menu.classList.remove("aberto"); botaoMenu.setAttribute("aria-expanded", false); } });

// "Entrar" no cabeçalho leva ao cartão de acesso desta página (sem trocar de página)
el("topoEntrar")?.addEventListener("click", e => {
  if(!el("formAcesso")) return;
  e.preventDefault();
  el("acesso").scrollIntoView({behavior: "smooth", block: "center"});
  setTimeout(() => el("hLogin").focus(), 350);
});

// FAQ: uma resposta aberta por vez
document.querySelectorAll("#faq details").forEach(d => d.addEventListener("toggle", () => {
  if(d.open) document.querySelectorAll("#faq details[open]").forEach(o => { if(o !== d) o.open = false; });
}));

// acesso rápido: mesma API e mesmas regras da tela de login
const form = el("formAcesso");
if(form){
  const erro = msg => { el("hErro").textContent = msg || ""; el("hErro").hidden = !msg; };
  form.addEventListener("submit", async e => {
    e.preventDefault(); erro("");
    const login = el("hLogin").value.trim(), senha = el("hSenha").value;
    if(!login || !senha) return erro("Informe o e-mail (ou CPF/CNPJ) e a senha.");
    if(!/[A-Za-z@]/.test(login) && digitos(login).length < 11) return erro("CPF/CNPJ incompleto. Ou informe o e-mail.");
    el("hEntrar").disabled = true;
    try{
      const r = await fetch("/auth/entrar", {method: "POST", body: JSON.stringify({login, senha}),
        headers: {"Content-Type": "application/json", "X-Requested-With": "NEXO"}});
      const corpo = await r.json().catch(() => ({}));
      if(r.ok){
        try{ if(window.PasswordCredential) await navigator.credentials.store(new PasswordCredential({id: login, password: senha})); }
        catch(_){ /* o usuário pode recusar salvar a senha */ }
        location.href = "/app";
        return;
      }
      // e-mail pendente: a tela de login tem o botão "Reenviar e-mail de confirmação"
      erro(corpo.codigo === "email_nao_confirmado" ? `${corpo.erro} Para receber outro link, use a tela de login.`
                                                    : corpo.erro || "Erro de comunicação com o servidor.");
    } catch(_){ erro("Não foi possível falar com o servidor. Verifique se o NEXO está em execução."); }
    finally{ el("hEntrar").disabled = false; }
  });
}
