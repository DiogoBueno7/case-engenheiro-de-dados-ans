-- ============================================================================
-- BRONZE (Raw Layer)
-- Ingestão do CSV da ANS "as-is": todas as colunas preservadas como texto,
-- sem tipagem nem transformação. Só adicionamos metadados de auditoria.
-- Formato de destino: Delta Lake, no bucket S3 (MinIO) sob o prefixo /bronze.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS bronze
LOCATION '{{LAKE_ROOT}}/bronze';

-- Lê o arquivo bruto diretamente via Spark SQL (separador ';', campos entre aspas).
CREATE OR REPLACE TEMPORARY VIEW raw_csv
USING csv
OPTIONS (
    path      '{{CSV_PATH}}',
    header    'true',
    sep       ';',
    quote     '"',
    encoding  'UTF-8',
    mode      'PERMISSIVE'
);

-- Tabela Bronze: cópia fiel do arquivo + colunas de auditoria.
CREATE OR REPLACE TABLE bronze.beneficiarios
USING delta
AS
SELECT
    *,
    current_timestamp()                       AS _ingested_at,
    '{{CSV_PATH}}'                            AS _source_file
FROM raw_csv;
