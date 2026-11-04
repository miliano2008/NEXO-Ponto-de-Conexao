/* NEXO — tela Arquitetura: camadas do sistema, ferramentas e etapas do cálculo. */
import {el} from "../nucleo/utilidades.js";

const camadas = [
  ["Excel → CSV → MySQL (Aiven)","Planilha exportada para CSV (banco/exportar_excel.py) e carregada no MySQL do Aiven (banco/migrar_mysql.py), com SSL."],
  ["Python — leitura e validação","banco/repositorio.py lê as tabelas contas/transacoes do MySQL (ou os CSVs no modo local) e valida IDs, contas, valores, datas e horas."],
  ["NumPy + NetworkX","Grafo dirigido, matrizes A, W, D, L, centralidades e Louvain."],
  ["Análise matemática","Laplaciana simétrica, autovalores/autovetores, score min-max e padrões."],
  ["API Flask (app/servidor.py)","/api/resultados, /api/matrizes, /api/transacoes (simulação por usuário), /api/exportar. Respostas compactadas e resultados reaproveitados (cache)."],
  ["Interface web","Esta tela: consome o JSON da API e desenha grafos, matrizes e dashboards."]
];
const ferramentas = [
  ["MySQL no Aiven","Tabelas contas, transacoes, usuarios, convites, auditoria, simulacoes e analises, criadas por migrações numeradas (banco/migracoes.py)."],
  ["Exportação","JSON hoje; PDF, Excel, CSV, Word e PowerPoint nas próximas fases."],
  ["GitHub","Versionamento do código e das entregas."]
];
const passos = ["Validação dos dados","Grafo dirigido agregado","Matrizes A, W, D, L","Degree, flow e imbalance",
  "Betweenness e closeness","Louvain (comunidades)","Análise espectral","Score e ranking","Padrões estruturais","API e visualização"];
export function iniciar(){
  el("archFlow").innerHTML = camadas.map(([n,d],i)=>
    `<div class="flow-box"><strong>${n}</strong><span>${d}</span></div>${i<camadas.length-1?'<div class="flow-arrow"></div>':""}`).join("");
  el("archTools").innerHTML = ferramentas.map(([n,d])=>
    `<div class="switch" style="align-items:flex-start"><div><p>${n}</p><span>${d}</span></div></div>`).join("");
  el("archSteps").innerHTML = passos.map(p=>`<li>${p}</li>`).join("");
}
