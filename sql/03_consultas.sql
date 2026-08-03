-- ============================================================================
-- CONSULTAS SOLICITADAS NO CASE
-- Rodam sobre a camada Gold (já agregada). Equivalente ao que seria executado
-- no AWS Athena / Databricks SQL sobre as tabelas curadas.
--
-- Cada consulta é anotada com `-- out: <nome>`: o runner usa esse nome para
-- salvar o resultado em output/<nome>.csv. Opcionalmente, `-- label: <texto>`
-- define o rótulo exibido no console (na ausência, usa o próprio <nome>). A
-- ordem das consultas aqui é irrelevante — cada uma carrega seu próprio nome.
-- Para adicionar/remover uma resposta ou insight, basta editar este arquivo
-- (nada muda no Python).
-- ============================================================================

-- (a) As 5 operadoras com maior número de beneficiários ativos
-- out: a_top5_operadoras
-- label: (a) Top 5 operadoras por beneficiários ativos
SELECT
    cd_operadora,
    nm_razao_social,
    qt_beneficiarios_ativos
FROM gold.beneficiarios_por_operadora
ORDER BY qt_beneficiarios_ativos DESC
LIMIT 5;

-- (b) A faixa etária com mais beneficiários (e quantos são)
-- out: b_faixa_etaria_top
-- label: (b) Faixa etária com mais beneficiários
SELECT
    de_faixa_etaria,
    qt_beneficiarios_ativos
FROM gold.beneficiarios_por_faixa_etaria
ORDER BY qt_beneficiarios_ativos DESC
LIMIT 1;

-- (c) Quantidade de beneficiários por município, em ordem decrescente
-- out: c_beneficiarios_por_municipio
-- label: (c) Beneficiários por município (ordem decrescente)
SELECT
    cd_municipio,
    nm_municipio,
    qt_beneficiarios_ativos
FROM gold.beneficiarios_por_municipio
ORDER BY qt_beneficiarios_ativos DESC;

-- ============================================================================
-- INSIGHTS ADICIONAIS (fora do escopo das 3 respostas do case)
-- Distribuições completas usadas pelo dashboard Streamlit para análises de
-- concentração de mercado e perfil demográfico.
-- ============================================================================

-- Ranking completo de operadoras (concentração de mercado / market share)
-- out: insight_operadoras
SELECT
    cd_operadora,
    nm_razao_social,
    qt_beneficiarios_ativos
FROM gold.beneficiarios_por_operadora
ORDER BY qt_beneficiarios_ativos DESC;

-- Distribuição completa por faixa etária (pirâmide demográfica)
-- out: insight_faixa_etaria
SELECT
    de_faixa_etaria,
    qt_beneficiarios_ativos
FROM gold.beneficiarios_por_faixa_etaria
ORDER BY qt_beneficiarios_ativos DESC;
