-- ============================================================================
-- CONSULTAS SOLICITADAS NO CASE
-- Rodam sobre a camada Gold (já agregada). Equivalente ao que seria executado
-- no AWS Athena / Databricks SQL sobre as tabelas curadas.
-- ============================================================================

-- (a) As 5 operadoras com maior número de beneficiários ativos
SELECT
    cd_operadora,
    nm_razao_social,
    qt_beneficiarios_ativos
FROM gold.beneficiarios_por_operadora
ORDER BY qt_beneficiarios_ativos DESC
LIMIT 5;

-- (b) A faixa etária com mais beneficiários (e quantos são)
SELECT
    de_faixa_etaria,
    qt_beneficiarios_ativos
FROM gold.beneficiarios_por_faixa_etaria
ORDER BY qt_beneficiarios_ativos DESC
LIMIT 1;

-- (c) Quantidade de beneficiários por município, em ordem decrescente
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
SELECT
    cd_operadora,
    nm_razao_social,
    qt_beneficiarios_ativos
FROM gold.beneficiarios_por_operadora
ORDER BY qt_beneficiarios_ativos DESC;

-- Distribuição completa por faixa etária (pirâmide demográfica)
SELECT
    de_faixa_etaria,
    qt_beneficiarios_ativos
FROM gold.beneficiarios_por_faixa_etaria
ORDER BY qt_beneficiarios_ativos DESC;
