/* NEXO — "Minha senha": o próprio usuário troca a senha ou desconecta os outros computadores.
   Trocar a senha encerra as outras sessões; esta continua aberta. */
import {api} from "./api.js";
import {ui} from "./ui.js";
import {el, esc} from "./utilidades.js";

export function abrirMinhaSenha(){
  ui.modal("Minha senha", `
    <form id="formSenha" class="form-senha" autocomplete="on" novalidate>
      <input type="text" autocomplete="username" hidden>
      <label>Senha atual<input id="msAtual" type="password" autocomplete="current-password" required></label>
      <label>Nova senha<input id="msNova" type="password" autocomplete="new-password" required></label>
      <ul class="regras-mini" id="msRegras"><li data-r="tam">8 ou mais caracteres</li><li data-r="letra">Letras</li><li data-r="num">Números</li></ul>
      <label>Confirmar nova senha<input id="msConf" type="password" autocomplete="new-password" required></label>
      <div class="note" style="margin:4px 0 12px;font-size:12px">Ao trocar a senha, o NEXO é encerrado nos <b>outros</b> computadores em que você estava conectado. Neste, você continua.</div>
      <div class="msg-erro-mini" id="msErro" hidden></div>
      <button class="btn" type="submit" id="msSalvar">Salvar nova senha</button>
    </form>
    <hr style="border:0;border-top:1px solid var(--line);margin:18px 0">
    <p style="margin:0 0 8px;font-size:13px"><b>Esqueceu a senha ou entrou com o Google?</b> Saia e use “Esqueci minha senha” na tela de login.</p>
    <p style="margin:0 0 10px;font-size:13px">Suspeita de que alguém usou seu acesso? Desconecte todos os outros computadores:</p>
    <button class="btn ghost" type="button" id="msEncerrar">Desconectar outros computadores</button>`);

  el("msNova").addEventListener("input", e=>{
    const v = e.target.value, ok = {tam: v.length >= 8, letra: /[A-Za-z]/.test(v), num: /\d/.test(v)};
    el("msRegras").querySelectorAll("li").forEach(li => li.classList.toggle("ok", ok[li.dataset.r]));
  });
  el("formSenha").addEventListener("submit", async e=>{
    e.preventDefault();
    const erro = el("msErro"); erro.hidden = true;
    el("msSalvar").disabled = true;
    try{
      await api("/auth/alterar-senha", {method:"POST", body: JSON.stringify({
        atual: el("msAtual").value, nova: el("msNova").value, confirmacao: el("msConf").value})});
      ui.closeModal();
      ui.toast("✓ Senha alterada. Os outros computadores foram desconectados.");
    } catch(err){ erro.textContent = err.message; erro.hidden = false; }
    finally{ el("msSalvar").disabled = false; }
  });
  el("msEncerrar").addEventListener("click", async e=>{
    e.target.disabled = true;
    try{
      await api("/auth/encerrar-sessoes", {method:"POST"});
      ui.closeModal();
      ui.toast("✓ Os outros computadores foram desconectados. Este continua conectado.");
    } catch(err){ ui.toast(esc(err.message), true); }
    finally{ e.target.disabled = false; }
  });
  setTimeout(() => el("msAtual").focus(), 30);
}
