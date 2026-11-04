-- =====================================================================
-- NEXO — consultas prontas para o MySQL Workbench (somente leitura)
-- Abra este arquivo no Workbench (File → Open SQL Script) e execute
-- uma consulta por vez: clique na linha e aperte Ctrl+Enter.
-- =====================================================================

USE nexo;

-- 1. Tabelas do banco e quantidade de linhas
SELECT table_name AS tabela, table_rows AS linhas_aprox
FROM information_schema.tables
WHERE table_schema = 'nexo'
ORDER BY table_name;

-- 2. Conferência da base (deve dar 40 contas, 160 transações, R$ 880.273,77)
SELECT (SELECT COUNT(*) FROM contas)     AS contas,
       (SELECT COUNT(*) FROM transacoes) AS transacoes,
       (SELECT SUM(valor) FROM transacoes) AS volume_total;

-- 3. Contas por tipo de titular
SELECT tipo_titular, COUNT(*) AS quantidade
FROM contas
GROUP BY tipo_titular
ORDER BY quantidade DESC;

-- 4. Transações por tipo (PIX, TED, Transferência)
SELECT tipo_transacao, COUNT(*) AS quantidade, SUM(valor) AS volume
FROM transacoes
GROUP BY tipo_transacao
ORDER BY volume DESC;

-- 5. Volume por período (Período A: agosto, Período B: setembro)
SELECT DATE_FORMAT(data, '%Y-%m') AS mes, COUNT(*) AS transacoes, SUM(valor) AS volume
FROM transacoes
GROUP BY mes
ORDER BY mes;

-- 6. Entradas, saídas e flow por conta (base do Flow e do Imbalance do score)
SELECT c.id_conta,
       c.tipo_titular,
       COALESCE(e.total, 0)                        AS entrada,
       COALESCE(s.total, 0)                        AS saida,
       COALESCE(e.total, 0) + COALESCE(s.total, 0) AS flow
FROM contas c
LEFT JOIN (SELECT conta_destino, SUM(valor) AS total FROM transacoes GROUP BY conta_destino) e
       ON e.conta_destino = c.id_conta
LEFT JOIN (SELECT conta_origem, SUM(valor) AS total FROM transacoes GROUP BY conta_origem) s
       ON s.conta_origem = c.id_conta
ORDER BY flow DESC;

-- 7. Degree de cada conta (contas DISTINTAS de entrada e de saída)
SELECT c.id_conta,
       (SELECT COUNT(DISTINCT conta_origem)  FROM transacoes WHERE conta_destino = c.id_conta) AS in_degree,
       (SELECT COUNT(DISTINCT conta_destino) FROM transacoes WHERE conta_origem  = c.id_conta) AS out_degree
FROM contas c
ORDER BY in_degree + out_degree DESC;

-- 8. Arestas do grafo: pares origem → destino com quantidade e valor
SELECT conta_origem, conta_destino, COUNT(*) AS quantidade, SUM(valor) AS valor_total
FROM transacoes
GROUP BY conta_origem, conta_destino
ORDER BY quantidade DESC, valor_total DESC;

-- 9. Todas as transações de uma conta (troque C025 pela conta desejada)
SELECT * FROM transacoes
WHERE conta_origem = 'C025' OR conta_destino = 'C025'
ORDER BY data, hora;

-- 10. Contas sem nenhuma transação (ex.: C040)
SELECT c.id_conta, c.tipo_titular
FROM contas c
WHERE NOT EXISTS (SELECT 1 FROM transacoes t
                  WHERE t.conta_origem = c.id_conta OR t.conta_destino = c.id_conta);

-- 11. Usuários do sistema (sem o hash da senha)
SELECT id, documento, tipo_documento, nome, email, cargo, ativo, ultimo_login, criado_em
FROM usuarios
ORDER BY nome;

-- 12. Últimos 50 eventos de acesso (trilha de auditoria)
SELECT data, evento, documento, detalhe, ip
FROM auditoria
ORDER BY id DESC
LIMIT 50;

-- 13. Tentativas de senha incorreta por documento
SELECT documento, COUNT(*) AS falhas, MAX(data) AS ultima
FROM auditoria
WHERE evento = 'login_falhou'
GROUP BY documento
ORDER BY falhas DESC;

-- 14. Estrutura das tabelas (tipos, chaves e regras)
SHOW CREATE TABLE contas;
SHOW CREATE TABLE transacoes;
