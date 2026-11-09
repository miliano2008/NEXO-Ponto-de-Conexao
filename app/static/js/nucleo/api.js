/* NEXO — comunicação com o servidor.

   Todo pedido envia o cabeçalho X-Requested-With (proteção contra requisições
   forjadas de outros sites). Sessão expirada (401) volta para o login.
*/
import {el} from "./utilidades.js";

export async function api(url, opcoes={}){
  el("loading").classList.add("on");
  try{
    const r = await fetch(url, {headers:{"Content-Type":"application/json", "X-Requested-With":"NEXO"}, ...opcoes});
    if(r.status === 401){ location.href = "/login"; throw new Error("Sessão expirada."); }
    const corpo = await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(corpo.erro || `Erro ${r.status} no servidor`);
    return corpo;
  } finally { el("loading").classList.remove("on"); }
}
