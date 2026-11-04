/* NEXO — utilidades de formatação e de HTML usadas por todas as telas. */

export const el = id => document.getElementById(id);

// escapa texto vindo de dados antes de colocar em innerHTML
export const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

export const fmtBRL = v => (+v).toLocaleString("pt-BR",{style:"currency",currency:"BRL"});
export const fmtNum = (v,d=2) => (+v).toLocaleString("pt-BR",{minimumFractionDigits:d,maximumFractionDigits:d});
export const fmtData = iso => iso ? iso.split("-").reverse().join("/") : "—";
export const fmtDataHora = iso => iso ? new Date(iso).toLocaleString("pt-BR",{dateStyle:"short",timeStyle:"short"}) : "—";
export const paraData = iso => { const [a,m,d] = iso.split("-").map(Number); return new Date(a, m-1, d); };

export const classeStatus = s => s==="Alta relevância" ? "alta" : s==="Em análise" ? "analise" : s==="Revisar" ? "revisar" : "normal";
export const pill = s => `<span class="pill ${classeStatus(s)}">${esc(s)}</span>`;
export const corStatus = s => s==="Alta relevância" ? "var(--red)" : s==="Em análise" ? "var(--amber)" : "var(--blue)";

const CORES_COM = ["#1B5FA8","#D99311","#1E7A5A","#C2263C","#7B4FC4","#0E8A9A","#B5578A","#6B7D1E","#8A5A2B","#4A5A6E","#2F9E44","#E8590C"];
export const corCom = n => CORES_COM[(n-1) % CORES_COM.length];

export const iniciais = nome => nome.split(/\s+/).filter(Boolean).map(p=>p[0]).slice(0,2).join("").toUpperCase();
export const digitos = t => String(t||"").replace(/\D/g,"");
