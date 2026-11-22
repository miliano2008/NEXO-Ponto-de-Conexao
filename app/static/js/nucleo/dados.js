/* NEXO — carga da análise vinda da API e classificação pelos limiares atuais. */
import {api} from "./api.js";
import {emitir, estado} from "./estado.js";
import {consulta, descreverRecorte} from "./filtros.js";
import {el, fmtData, paraData} from "./utilidades.js";

/* status das contas pelos limiares atuais; transações herdam a maior nota das duas contas */
export function classificar(){
  const {analise, alta} = estado.limiares;
  estado.dados.contas.forEach(c => {
    c.status = c.score >= alta ? "Alta relevância" : c.score >= analise ? "Em análise"
             : c.score >= analise*0.66 ? "Revisar" : "Normal";
  });
  estado.dados.transacoes.forEach(t => {
    const nota = Math.max(estado.porId[t.de].score, estado.porId[t.para].score);
    t.status = nota >= alta ? "Alta relevância" : nota >= analise ? "Em análise" : "Normal";
  });
}

/* situação da investigação de cada conta (pequena: só as contas com registro) */
export async function carregarCasos(){
  const r = await api("/api/casos");
  estado.casos = r.casos; estado.situacoes = r.situacoes;
}

export async function carregar(){
  const [dados] = await Promise.all([api(`/api/resultados?${consulta()}`), carregarCasos()]);
  estado.dados = dados;
  estado.versaoDados++;
  estado.porId = Object.fromEntries(dados.contas.map(c=>[c.id,c]));
  const ref = paraData(dados.simulacao.recorte.fim_efetivo);   // "dias" contados a partir do fim do recorte
  dados.transacoes.forEach(t => { t.dias = Math.round((ref - paraData(t.data))/86400000); });
  classificar();
  el("sysStatus").textContent = `Backend Python conectado · ${dados.simulacao.transacoes_simuladas} simulada(s)`;
  const base = dados.base?.origem === "arquivo" ? `${dados.base.nome} · ` : "";   // base importada (Fase 6)
  el("baseLabel").textContent = `${base}referência ${fmtData(dados.simulacao.data_referencia)} · ${dados.dashboard.total_contas} contas`;
  el("periodLabel").textContent = descreverRecorte();
  emitir("dados");
}

/* matrizes n×n: pesadas, então só são buscadas quando uma tela precisa delas */
let matrizes = {versao: -1, pedido: null};

export function obterMatrizes(){
  if(matrizes.versao !== estado.versaoDados){
    const versao = estado.versaoDados;
    const pedido = api(`/api/matrizes?${consulta()}`).then(r => r.matrizes)
      .catch(erro => { matrizes.versao = -1; throw erro; });   // falhou: tenta de novo na próxima vez
    matrizes = {versao, pedido};
  }
  return matrizes.pedido;
}
