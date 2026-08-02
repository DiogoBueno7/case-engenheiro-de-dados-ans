-- ============================================================================
-- GOLD (Curated Layer)
-- Tabelas agregadas e otimizadas para consumo analítico. Cada tabela já
-- responde diretamente a uma das perguntas do case, evitando reprocessar os
-- ~4,8 milhões de registros da Silver a cada consulta (performance/caching).
-- ============================================================================

CREATE DATABASE IF NOT EXISTS gold
LOCATION '{{LAKE_ROOT}}/gold';

-- ---------------------------------------------------------------------------
-- (a) Beneficiários ativos por operadora
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE gold.beneficiarios_por_operadora
USING delta
AS
SELECT
    cd_operadora,
    nm_razao_social,
    SUM(qt_beneficiario_ativo) AS qt_beneficiarios_ativos
FROM silver.beneficiarios
GROUP BY cd_operadora, nm_razao_social;

-- ---------------------------------------------------------------------------
-- (b) Beneficiários ativos por faixa etária
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE gold.beneficiarios_por_faixa_etaria
USING delta
AS
SELECT
    de_faixa_etaria,
    SUM(qt_beneficiario_ativo) AS qt_beneficiarios_ativos
FROM silver.beneficiarios
GROUP BY de_faixa_etaria;

-- ---------------------------------------------------------------------------
-- (c) Beneficiários ativos por município
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE gold.beneficiarios_por_municipio
USING delta
AS
SELECT
    cd_municipio,
    nm_municipio,
    SUM(qt_beneficiario_ativo) AS qt_beneficiarios_ativos
FROM silver.beneficiarios
GROUP BY cd_municipio, nm_municipio;
