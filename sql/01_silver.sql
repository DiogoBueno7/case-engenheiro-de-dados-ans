-- ============================================================================
-- SILVER (Refined Layer)
-- - Converte para formato tabular tipado (Delta).
-- - Aplica tipagem correta das colunas (quantidades -> INT, datas -> DATE).
-- - Aplica MASCARAMENTO de dado sensível: o CNPJ da operadora tem apenas a
--   raiz (8 primeiros dígitos) preservada; o restante é mascarado.
-- - Normaliza nomes de colunas para snake_case minúsculo.
-- - Particionada por competência (id_cmpt_movel), padrão para cargas mensais.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS silver
LOCATION '{{LAKE_ROOT}}/silver';

CREATE OR REPLACE TABLE silver.beneficiarios
USING delta
PARTITIONED BY (id_cmpt_movel)
AS
SELECT
    CAST(CD_OPERADORA        AS STRING)                       AS cd_operadora,
    TRIM(NM_RAZAO_SOCIAL)                                     AS nm_razao_social,
    -- Mascaramento: mantém a raiz do CNPJ (8 dígitos) e oculta o restante.
    CONCAT(SUBSTRING(NR_CNPJ, 1, 8), '******')               AS nr_cnpj_masc,
    TRIM(MODALIDADE_OPERADORA)                                AS modalidade_operadora,
    CAST(SG_UF               AS STRING)                       AS sg_uf,
    CAST(CD_MUNICIPIO        AS STRING)                       AS cd_municipio,
    TRIM(NM_MUNICIPIO)                                        AS nm_municipio,
    CAST(TP_SEXO             AS STRING)                       AS tp_sexo,
    TRIM(DE_FAIXA_ETARIA)                                     AS de_faixa_etaria,
    TRIM(DE_SEGMENTACAO_PLANO)                                AS de_segmentacao_plano,
    TRIM(DE_ABRG_GEOGRAFICA_PLANO)                            AS de_abrg_geografica_plano,
    TRIM(DE_CONTRATACAO_PLANO)                                AS de_contratacao_plano,
    TRIM(COBERTURA_ASSIST_PLAN)                               AS cobertura_assist_plan,
    TRIM(TIPO_VINCULO)                                        AS tipo_vinculo,
    CAST(QT_BENEFICIARIO_ATIVO      AS INT)                   AS qt_beneficiario_ativo,
    CAST(QT_BENEFICIARIO_ADERIDO    AS INT)                   AS qt_beneficiario_aderido,
    CAST(QT_BENEFICIARIO_CANCELADO  AS INT)                   AS qt_beneficiario_cancelado,
    CAST(DT_CARGA            AS DATE)                          AS dt_carga,
    CAST(ID_CMPT_MOVEL       AS STRING)                       AS id_cmpt_movel
FROM bronze.beneficiarios;
