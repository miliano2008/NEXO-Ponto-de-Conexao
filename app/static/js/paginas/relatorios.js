/* NEXO — tela Relatórios: rede, contas, memorial de cálculo, validação matemática e exportação. */
import {obterMatrizes} from "../nucleo/dados.js";
import {estado} from "../nucleo/estado.js";
import {ui} from "../nucleo/ui.js";
import {esc, el, fmtBRL, fmtNum, pill} from "../nucleo/utilidades.js";

async function conteudo(i){
  const d = estado.dados, n = d.contas.length, m = d.rede.arestas.length;
  if(i===0) return `<dl class="kv"><dt>Nós</dt><dd>${n}</dd><dt>Conexões dirigidas</dt><dd>${m}</dd><dt>Transações</dt><dd>${d.transacoes.length}</dd>
    <dt>Densidade</dt><dd>${fmtNum(m/(n*(n-1)),4)}</dd><dt>Comunidades</dt><dd>${d.dashboard.total_comunidades}</dd>
    <dt>Modularidade</dt><dd>${fmtNum(d.dashboard.modularidade_louvain,4)}</dd><dt>Componentes conexas</dt><dd>${d.espectral.componentes_conexas}</dd>
    <dt>Volume total</dt><dd>${fmtBRL(d.dashboard.volume_total)}</dd></dl>`;
  if(i===1) return `<table><thead><tr><th>#</th><th>Conta</th><th class="num">Score</th><th class="num">Degree</th><th class="num">Flow</th><th>Status</th></tr></thead><tbody>
    ${d.contas.slice(0,10).map(c=>`<tr class="clickable" data-conta="${c.id}"><td>${c.ranking}</td><td class="mono-id">${c.id}</td><td class="num">${fmtNum(c.score,1)}</td><td class="num">${c.degree}</td><td class="num">${fmtBRL(c.flow)}</td><td>${pill(c.status)}</td></tr>`).join("")}</tbody></table>`;
  if(i===2) return `<dl class="kv" style="grid-template-columns:180px 1fr">
    ${Object.entries(d.parametros).filter(([k])=>k!=="pesos_score"&&k!=="limiares_ilustrativos").map(([k,v])=>`<dt>${esc(k.replace(/_/g," "))}</dt><dd>${esc(v)}</dd>`).join("")}
    <dt>Pesos</dt><dd>${Object.entries(d.parametros.pesos_score).map(([k,v])=>`${k} ${v}`).join(" · ")}</dd>
    <dt>Limiares</dt><dd>em análise ${d.parametros.limiares_ilustrativos.em_analise} · alta ${d.parametros.limiares_ilustrativos.alta_relevancia}</dd></dl>`;
  if(i===3){
    const M = await obterMatrizes(), ok = b => b ? "✔ confere" : "✖ diverge";
    const Lok = M.L.every((l,a)=>l.every((v,b)=>v===M.D[a][b]-M.A[a][b]));
    const Ls0 = M.L_simetrica.every(l=>Math.abs(l.reduce((x,y)=>x+y,0))<1e-9);
    const sim = M.L_simetrica.every((l,a)=>l.every((v,b)=>v===M.L_simetrica[b][a]));
    const qtd = d.rede.arestas.reduce((a,e)=>a+e.quantidade,0)===d.transacoes.length;
    const zeros = d.espectral.autovalores.filter(v=>v<1e-8).length===d.espectral.componentes_conexas;
    const com = d.comunidades.reduce((a,c)=>a+c.quantidade_contas,0)===n;
    return `<table><tbody>
      <tr><td>L = D − A</td><td>${ok(Lok)}</td></tr>
      <tr><td>L simétrica = Lᵀ</td><td>${ok(sim)}</td></tr>
      <tr><td>Soma das linhas de L simétrica = 0</td><td>${ok(Ls0)}</td></tr>
      <tr><td>Σ quantidades nas arestas = nº de transações</td><td>${ok(qtd)}</td></tr>
      <tr><td>Nº de autovalores nulos = componentes conexas</td><td>${ok(zeros)}</td></tr>
      <tr><td>Comunidades cobrem todas as ${n} contas</td><td>${ok(com)}</td></tr>
      <tr><td>Scores entre 0 e 100</td><td>${ok(d.contas.every(c=>c.score>=0&&c.score<=100))}</td></tr>
    </tbody></table><p style="font-size:12px;color:var(--ink-3)">Conferências executadas no navegador sobre o JSON do backend. A validação completa está em <code>testes/test_nucleo.py</code>.</p>`;
  }
  return `<p style="margin-top:0">Exporta todos os resultados atuais (incluindo simulações e período selecionado) em JSON, pronto para Power BI ou para o relatório A3.</p>
    <a class="btn" style="text-decoration:none;display:inline-block" href="/api/exportar?dias=${estado.periodo}">Baixar resultados_nexo.json</a>`;
}
const itens = [
  ["Relatório de Rede","Panorama do grafo: número de nós, arestas, densidade, comunidades e conectividade.","Gerado"],
  ["Análise de Contas","Top 10 contas por relevância estrutural, com score e métricas.","Gerado"],
  ["Memorial de Cálculo","Parâmetros matemáticos adotados pelo backend.","Gerado"],
  ["Validação Matemática","Conferências automáticas de consistência das matrizes, espectral e Louvain.","Gerado"],
  ["Exportar resultados","JSON completo para integração (Power BI / Relatório A3).","Disponível"]
];
export function iniciar(){
  el("reportGrid").innerHTML = itens.map(([nome,desc,st],i)=>`
    <div class="card"><div class="card-body">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
        <h3 style="margin:0 0 6px;font-size:15px">${nome}</h3><span class="pill normal">${st}</span>
      </div>
      <p style="margin:0 0 14px;font-size:12.5px;color:var(--ink-2)">${desc}</p>
      <button class="btn ghost sm" data-rel="${i}">Visualizar</button>
    </div></div>`).join("");
  el("reportGrid").addEventListener("click", async e=>{
    const b = e.target.closest("button[data-rel]"); if(!b) return;
    try{ ui.modal(itens[+b.dataset.rel][0], await conteudo(+b.dataset.rel)); }
    catch(err){ ui.toast(esc(err.message), true); }
  });
}
