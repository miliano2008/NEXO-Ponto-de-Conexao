/* NEXO — janelas da interface: modal, painel lateral (drawer) e avisos (toast). */
import {el} from "./utilidades.js";

let temporizador = null;

export const ui = {
  modal(titulo, html){ el("modalTitle").textContent = titulo; el("modalBody").innerHTML = html; el("overlay").classList.add("open"); },
  closeModal(){ el("overlay").classList.remove("open"); },
  drawer(titulo, html){ el("drawerTitle").textContent = titulo; el("drawerBody").innerHTML = html; el("drawer").classList.add("open"); },
  closeDrawer(){ el("drawer").classList.remove("open"); },
  toast(msg, erro=false){
    const t = el("toast"); t.innerHTML = msg; t.classList.toggle("erro", erro); t.classList.add("on");
    clearTimeout(temporizador); temporizador = setTimeout(()=>t.classList.remove("on"), erro ? 5000 : 3800);
  }
};
