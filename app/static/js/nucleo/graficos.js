/* NEXO — gráficos em SVG desenhados à mão (sem bibliotecas externas): área, rosca e barras. */
import {esc, fmtBRL} from "./utilidades.js";

export const charts = {
  area(alvo, pontos){
    if(pontos.length < 2){ alvo.innerHTML = `<div class="empty">Dados insuficientes no período.</div>`; return; }
    const W=760, H=250, P={t:14,r:14,b:26,l:54};
    const max = Math.max(...pontos.map(p=>p.valor),1)*1.1;
    const x = i => P.l + i*(W-P.l-P.r)/(pontos.length-1);
    const y = v => H-P.b - v/max*(H-P.t-P.b);
    const linha = pontos.map((p,i)=>`${i?"L":"M"}${x(i).toFixed(1)},${y(p.valor).toFixed(1)}`).join("");
    const area = `${linha}L${x(pontos.length-1)},${H-P.b}L${x(0)},${H-P.b}Z`;
    const ticks = [0,.25,.5,.75,1].map(f=>{
      const v = max*f, yy=y(v);
      return `<line x1="${P.l}" x2="${W-P.r}" y1="${yy}" y2="${yy}" stroke="var(--line)"/>
              <text x="${P.l-8}" y="${yy+4}" text-anchor="end" font-size="10" fill="var(--ink-3)">${(v/1000).toFixed(0)}k</text>`;
    }).join("");
    const passo = Math.ceil(pontos.length/7);
    const labels = pontos.map((p,i)=> i%passo===0 || i===pontos.length-1
      ? `<text x="${x(i)}" y="${H-8}" text-anchor="middle" font-size="10" fill="var(--ink-3)">${p.data.toLocaleDateString("pt-BR",{day:"2-digit",month:"2-digit"})}</text>` : "").join("");
    const marcas = pontos.map((p,i)=>`<circle cx="${x(i)}" cy="${y(p.valor)}" r="${p.valor?2.5:0}" fill="var(--blue)"/><circle cx="${x(i)}" cy="${y(p.valor)}" r="9" fill="transparent"><title>${p.data.toLocaleDateString("pt-BR")} · ${fmtBRL(p.valor)} · ${p.qtd} transação(ões)</title></circle>`).join("");
    alvo.innerHTML = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto">
      <defs><linearGradient id="gA" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--blue)" stop-opacity=".28"/><stop offset="100%" stop-color="var(--blue)" stop-opacity="0"/>
      </linearGradient></defs>
      ${ticks}<path d="${area}" fill="url(#gA)"/><path d="${linha}" fill="none" stroke="var(--blue)" stroke-width="2"/>${labels}${marcas}</svg>`;
  },

  rosca(alvo, fatias){
    const total = fatias.reduce((a,f)=>a+f.valor,0), R=74, r=48, cx=95, cy=95;
    if(!total){ alvo.innerHTML = `<div class="empty">Sem transações no período.</div>`; return; }
    let ang = -Math.PI/2, paths="";
    fatias.filter(f=>f.valor).forEach(f=>{
      // fatia de 100% vira círculo completo (arco SVG não fecha em 360°)
      const a2 = ang + Math.min(f.valor/total, 0.9999)*Math.PI*2, grande = (a2-ang)>Math.PI?1:0;
      const p = (raio,a)=>[cx+raio*Math.cos(a), cy+raio*Math.sin(a)];
      const [x1,y1]=p(R,ang),[x2,y2]=p(R,a2),[x3,y3]=p(r,a2),[x4,y4]=p(r,ang);
      paths += `<path d="M${x1},${y1}A${R},${R} 0 ${grande} 1 ${x2},${y2}L${x3},${y3}A${r},${r} 0 ${grande} 0 ${x4},${y4}Z" fill="${f.cor}"><title>${f.nome}: ${f.valor}</title></path>`;
      ang = a2;
    });
    alvo.innerHTML = `<div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap">
      <svg viewBox="0 0 190 190" style="width:170px;height:170px;flex:0 0 170px">${paths}
        <text x="95" y="92" text-anchor="middle" font-size="24" font-weight="700" fill="var(--ink)">${total}</text>
        <text x="95" y="108" text-anchor="middle" font-size="10" fill="var(--ink-3)">transações</text></svg>
      <div style="font-size:12.5px;line-height:2.1">
        ${fatias.map(f=>`<div><i style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${f.cor};margin-right:8px"></i>${f.nome} <b style="margin-left:6px">${f.valor}</b> <span style="color:var(--ink-3)">(${Math.round(f.valor/total*100)}%)</span></div>`).join("")}
      </div></div>`;
  },

  barras(alvo, itens, fmt=fmtBRL, eixo=v=>(v/1000).toFixed(0)+"k"){
    const W=620,H=200,P={t:12,r:10,b:30,l:52};
    const max = Math.max(...itens.map(i=>i.valor),1e-9)*1.15;
    const lg = (W-P.l-P.r)/itens.length;
    const mostra = Math.ceil(itens.length/14);
    const barras = itens.map((it,i)=>{
      const h = (it.valor/max)*(H-P.t-P.b), x=P.l+i*lg+lg*0.2, y=H-P.b-h;
      return `<rect x="${x}" y="${y}" width="${lg*0.6}" height="${Math.max(h,1)}" rx="2" fill="${it.cor||"var(--blue)"}" opacity=".85"><title>${esc(it.rotulo)}: ${fmt(it.valor)}</title></rect>
              ${i%mostra===0?`<text x="${x+lg*0.3}" y="${H-10}" text-anchor="middle" font-size="10" fill="var(--ink-3)">${esc(it.rotulo)}</text>`:""}`;
    }).join("");
    const base = [0,.5,1].map(f=>{const yy=H-P.b-f*(H-P.t-P.b);
      return `<line x1="${P.l}" x2="${W-P.r}" y1="${yy}" y2="${yy}" stroke="var(--line)"/><text x="${P.l-8}" y="${yy+4}" text-anchor="end" font-size="10" fill="var(--ink-3)">${eixo(max*f)}</text>`;}).join("");
    alvo.innerHTML = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto">${base}${barras}</svg>`;
  }
};
