/* NEXO — acesso: login (CPF/CNPJ + senha), cadastro com confirmação de e-mail,
   recuperação de senha e redefinição/confirmação pelos links enviados por e-mail. */
import {digitos, el, esc} from "./nucleo/utilidades.js";

(() => {
const ROTAS = {login: "/login", cadastro: "/cadastro"};

/* ---------- máscaras ---------- */
// até 11 dígitos = CPF, acima = CNPJ
function mascararDoc(valor){
  const d = digitos(valor).slice(0, 14);
  if(d.length <= 11)
    return d.replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2");
  return d.replace(/(\d{2})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2")
          .replace(/(\d{3})(\d)/, "$1/$2").replace(/(\d{4})(\d{1,2})$/, "$1-$2");
}
function mascararTel(valor){
  const d = digitos(valor).slice(0, 11);
  if(d.length <= 2) return d.length ? `(${d}` : "";
  const meio = d.length === 11 ? 5 : 4;
  return `(${d.slice(0,2)}) ${d.slice(2, 2+meio)}${d.length > 2+meio ? "-" + d.slice(2+meio) : ""}`;
}
function mascararConvite(valor){
  const c = valor.toUpperCase().replace(/[^A-Z0-9]/g, "").replace(/^NEXO/, "").slice(0, 8);
  return c ? "NEXO-" + c.slice(0,4) + (c.length > 4 ? "-" + c.slice(4) : "") : "";
}

function erro(msg){ const e = el("erro"); e.textContent = msg || ""; e.hidden = !msg; }

function ir(etapa, atualizarUrl = true){
  document.querySelectorAll(".etapa").forEach(f => f.hidden = f.id !== "etapa-" + etapa);
  erro("");
  if(atualizarUrl && ROTAS[etapa] && location.pathname !== ROTAS[etapa]) history.pushState(null, "", ROTAS[etapa]);
  const foco = {login:"docInput", cadastro:"cadDoc", esqueci:"esqDoc", redefinir:"redSenha"}[etapa];
  setTimeout(() => el(foco)?.focus(), 30);
}

async function post(url, dados){
  const r = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json", "X-Requested-With":"NEXO"},
                              body: JSON.stringify(dados)});
  const corpo = await r.json().catch(() => ({}));
  if(!r.ok){ const e = new Error(corpo.erro || "Erro de comunicação com o servidor."); e.codigo = corpo.codigo; throw e; }
  return corpo;
}

// bloqueia o botão enquanto o pedido está em andamento
function enviando(form, fn){
  form.addEventListener("submit", async e => {
    e.preventDefault(); erro("");
    const botao = form.querySelector("button[type=submit]");
    botao.disabled = true;
    try{ await fn(); } catch(err){ if(err.codigo !== "tratado") erro(err.message); } finally{ botao.disabled = false; }
  });
}

function regrasSenha(input, lista){
  input.addEventListener("input", () => {
    const v = input.value;
    const ok = {tam: v.length >= 8, letra: /[A-Za-z]/.test(v), num: /\d/.test(v)};
    lista.querySelectorAll("li").forEach(li => li.classList.toggle("ok", ok[li.dataset.r]));
  });
}

/* ---------- campos ---------- */
[["docInput","docTipo"], ["cadDoc","cadDocTipo"], ["esqDoc", null]].forEach(([id, dica]) =>
  el(id).addEventListener("input", e => {
    e.target.value = mascararDoc(e.target.value);
    if(dica){
      const n = digitos(e.target.value).length;
      el(dica).textContent = n === 0 ? " " : n <= 11 ? `CPF · ${n}/11 dígitos` : `CNPJ · ${n}/14 dígitos`;
      if(id === "cadDoc") el("cadNomeLabel").textContent = n > 11 ? "Razão social" : "Nome completo";
    }
  }));
el("cadTel").addEventListener("input", e => { e.target.value = mascararTel(e.target.value); });
el("cadConvite").addEventListener("input", e => { e.target.value = mascararConvite(e.target.value); });

document.addEventListener("click", e => {
  const b = e.target.closest("[data-ir]");
  if(b){
    e.preventDefault();
    if(b.dataset.ir === "esqueci") el("esqDoc").value = el("docInput").value;
    if(b.dataset.ir === "cadastro" && !el("cadDoc").value) el("cadDoc").value = el("docInput").value;
    if(["/redefinir", "/confirmar"].includes(location.pathname)){ location.href = ROTAS[b.dataset.ir] || "/login"; return; }
    ir(b.dataset.ir);
  }
  const olho = e.target.closest("[data-olho]");
  if(olho){ const i = el(olho.dataset.olho); i.type = i.type === "password" ? "text" : "password"; }
});
window.addEventListener("popstate", () => ir(location.pathname === "/cadastro" ? "cadastro" : "login", false));

/* ---------- 1. login ---------- */
async function salvarNoNavegador(){
  // Chrome/Edge: oferece salvar a senha. Outros navegadores usam o próprio formulário.
  try{
    if(window.PasswordCredential)
      await navigator.credentials.store(new PasswordCredential({id: el("docInput").value, password: el("senhaInput").value}));
  } catch(_){ /* o usuário pode recusar; não impede o login */ }
}

enviando(el("etapa-login"), async () => {
  el("pendente").hidden = true;
  if(digitos(el("docInput").value).length < 11 || !el("senhaInput").value)
    throw new Error("Informe o CPF/CNPJ e a senha.");
  try{
    await post("/auth/entrar", {documento: el("docInput").value, senha: el("senhaInput").value});
  } catch(err){
    if(err.codigo === "email_nao_confirmado"){
      el("pendenteMsg").textContent = err.message;
      el("pendente").hidden = false;
      err.codigo = "tratado";
    }
    throw err;
  }
  await salvarNoNavegador();
  location.href = "/";
});

el("btnReenviar").addEventListener("click", async e => {
  e.target.disabled = true; erro("");
  try{
    const r = await post("/auth/reenviar-confirmacao", {documento: el("docInput").value, senha: el("senhaInput").value});
    el("pendenteMsg").textContent = `Enviamos um novo link para ${r.email}. Verifique também a caixa de spam.`;
  } catch(err){ erro(err.message); }
  finally{ e.target.disabled = false; }
});

/* ---------- 2. cadastro ---------- */
regrasSenha(el("cadSenha"), el("cadRegras"));
enviando(el("etapa-cadastro"), async () => {
  const r = await post("/auth/cadastrar", {
    documento: el("cadDoc").value, nome: el("cadNome").value, email: el("cadEmail").value,
    telefone: el("cadTel").value, senha: el("cadSenha").value, confirmacao: el("cadConf").value,
    convite: el("cadConvite").value});
  el("docInput").value = el("cadDoc").value;
  el("cadOk").innerHTML = r.enviado
    ? `✉ Cadastro criado como <b>${esc(r.cargo_nome)}</b>. Enviamos um link para <b>${esc(r.email)}</b>.<br>
       Abra o e-mail e clique em <b>Confirmar meu e-mail</b> para liberar o acesso. O link vale por ${r.validade_horas} horas. Verifique também a caixa de spam.`
    : `Cadastro criado como <b>${esc(r.cargo_nome)}</b>, mas <b>não foi possível enviar o e-mail de confirmação</b> agora.<br>
       Tente entrar mais tarde e use “Reenviar e-mail de confirmação”, ou peça ao administrador para confirmar seu e-mail.`;
  ir("cadastrado", false);
});

/* ---------- 3. esqueci minha senha ---------- */
enviando(el("etapa-esqueci"), async () => {
  el("esqOk").hidden = true;
  if(digitos(el("esqDoc").value).length < 11) throw new Error("Informe um CPF ou CNPJ completo.");
  const r = await post("/auth/esqueci", {documento: el("esqDoc").value});
  el("esqOk").textContent = "✉ " + r.mensagem;
  el("esqOk").hidden = false;
});

/* ---------- 4/5. links recebidos por e-mail ---------- */
const token = new URLSearchParams(location.search).get("token") || "";
regrasSenha(el("redSenha"), el("redRegras"));
enviando(el("etapa-redefinir"), async () => {
  await post("/auth/redefinir", {token, senha: el("redSenha").value, confirmacao: el("redConf").value});
  el("etapa-redefinir").querySelectorAll(".campo, #redBtn").forEach(x => x.hidden = true);
  el("redefQuem").innerHTML = "✓ Senha alterada com sucesso. Faça login com a nova senha.";
});

if(location.pathname === "/redefinir"){
  ir("redefinir", false);
  fetch(`/auth/token?token=${encodeURIComponent(token)}`).then(r => r.json().then(c => ({ok: r.ok, c})))
    .then(({ok, c}) => {
      if(ok){
        el("redefQuem").innerHTML = `Usuário: <b>${esc(c.nome)}</b> <span class="doc-chip">${esc(c.documento)}</span>`;
        el("redUsuario").value = c.documento;   // o navegador associa a nova senha a este usuário
      } else {
        el("redefQuem").textContent = c.erro;
        el("etapa-redefinir").querySelectorAll(".campo, #redBtn").forEach(x => x.hidden = true);
      }
    });
} else if(location.pathname === "/confirmar"){
  ir("confirmar", false);
  // basta abrir o link: o e-mail é confirmado automaticamente
  post("/auth/confirmar", {token})
    .then(r => { el("confMsg").innerHTML = `✓ E-mail confirmado, <b>${esc(r.nome)}</b>! Você já pode entrar no NEXO.`; })
    .catch(err => { el("confMsg").textContent = err.message; })
    .finally(() => { el("confBtn").hidden = false; });
} else {
  ir(location.pathname === "/cadastro" ? "cadastro" : "login", false);
}
})();
