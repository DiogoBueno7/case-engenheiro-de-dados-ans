# CLAUDE.md

Guia técnico do projeto para retomada rápida de contexto.

## O que é

Pipeline de dados em **arquitetura Medallion** (Bronze → Silver → Gold) sobre os
dados públicos da **ANS** (beneficiários de planos de saúde de SP), resolvendo um
case de Engenheiro de Dados. Roda **localmente em Docker**, emulando a stack de
nuvem da empresa (AWS Glue/Athena/S3/Redshift + Databricks/Spark) sem custo.

- **Base:** `data/pda-024-icb-SP-2025_08.csv` — 1,46 GB, **4.830.707 registros**,
  UTF-8, separador `;`, campos entre aspas. Competência 2025-08.
- **Documento de apresentação/defesa:** ver [`docs/APRESENTACAO.md`](docs/APRESENTACAO.md)
  (narrativa, problemas enfrentados e Q&A).

## Stack (tudo em Docker)

| Papel            | Tecnologia local          | Equivalente produção                  |
|------------------|---------------------------|---------------------------------------|
| Orquestração     | Apache Airflow 2.9.3       | Airflow / MWAA / Databricks Workflows |
| Processamento    | PySpark 3.5.1             | AWS Glue / Databricks / Spark         |
| Formato do lake  | Delta Lake 3.2.0          | Delta Lake                            |
| Object storage   | MinIO (S3-compatible)     | Amazon S3                             |
| Consulta SQL     | Spark SQL                 | Amazon Athena / Databricks SQL        |
| Camada curada    | Gold (Delta)              | Amazon Redshift                       |
| Visualização/BI  | Streamlit                 | QuickSight / Power BI / Databricks     |

Serviços do `docker-compose.yml`: `minio` (S3), `minio-init` (cria bucket, é
one-shot e sai com código 0 — normal), `spark` (PySpark + Delta; motor de
processamento e alvo do `docker exec` do Airflow — fica vivo via `tail -f
/dev/null`), `jupyter` (JupyterLab estilo Databricks, mesma imagem/volumes do
`spark`, serviço separado só para ter linha/porta próprias no Docker Desktop),
`spark-history` (Spark History Server — Spark UI de execuções já finalizadas, lê
os event logs do volume `spark-events`), `postgres` (metastore do Airflow),
`airflow-init` (migra schema + cria admin, one-shot, Exited 0 esperado),
`airflow-webserver` (só a UI) e `airflow-scheduler` (agenda **e executa** as
tasks, via LocalExecutor). Login: `admin` / `admin`. Há ainda `streamlit`
(`case-streamlit`): dashboard/BI que lê os CSVs de `output/` (camada Gold) — não
usa Spark/Java, imagem própria e enxuta em `app/`.

Portas: **8501** Streamlit (dashboard) · **8888** JupyterLab · **9000/9001** MinIO
API/console · **4040** Spark UI (pipeline, `case-spark`) · **4041** Spark UI (jobs
do notebook, `case-jupyter`) · **18080** Spark History Server (execuções
finalizadas) · **8080** Airflow UI.

## Comandos

```bash
# Subir tudo (1ª build baixa jars/imagens; leva alguns minutos)
docker compose up -d --build

# Rodar o pipeline completo (Bronze -> Silver -> Gold -> Consultas)
docker compose exec spark python -m src.run_pipeline

# Rodar etapas específicas
docker compose exec spark python -m src.run_pipeline bronze
docker compose exec spark python -m src.run_pipeline silver gold

# Orquestração via Airflow (sem UI) — roda no container do scheduler
docker compose exec airflow-scheduler airflow dags test pipeline_medallion_ans 2025-08-01

# UI do Airflow em http://localhost:8080 — login fixo: admin / admin

# Zerar o data lake (MinIO) para reprocessar do zero
docker run --rm --entrypoint sh --network case_engenheiro_de_dados_default \
  minio/mc:latest -c "mc alias set local http://minio:9000 minioadmin minioadmin && \
  mc rm --recursive --force local/lakehouse/"
```

## Estrutura

```
sql/           lógica das camadas em Spark SQL (o "coração" do pipeline)
  00_bronze.sql / 01_silver.sql / 02_gold.sql / 03_consultas.sql
src/           execução em Python (orquestra o SQL, não contém regra de negócio)
  config.py        SparkSession (Delta + S3A/MinIO + metastore Hive persistente)
  sql_runner.py    lê/parametriza/executa os .sql (split de statements quote-aware)
  queries.py       roda as 3 consultas e salva em output/
  run_pipeline.py  runner Bronze->Silver->Gold->Consultas (aceita etapas como args)
airflow/       Dockerfile (Airflow + docker CLI) + dags/pipeline_medallion_dag.py
app/           dashboard Streamlit (BI): Dockerfile + requirements + streamlit_app.py
notebooks/     pipeline_medallion.ipynb (versão estilo Databricks)
output/        resultados das consultas + insights (CSV) — consumidos pelo dashboard
data/          CSV bruto (não versionado)
```

## Decisões técnicas importantes

- **SQL como linguagem central:** toda transformação está em `sql/*.sql`; o Python
  só orquestra. Placeholders `{{LAKE_ROOT}}` / `{{CSV_PATH}}` são substituídos em
  `sql_runner.py`.
- **Idempotência por full-refresh (sem duplicação):** todas as tabelas são criadas
  com `CREATE OR REPLACE TABLE` (Bronze/Silver/Gold). Cada execução **descarta e
  reescreve a tabela inteira**, então rodar N vezes — pelo Airflow, pelo
  `run_pipeline` ou pelo notebook — produz sempre o mesmo estado final: não há como
  acumular linhas repetidas. **Não existe `INSERT INTO` nem `.mode("append")` em
  nenhum ponto do fluxo.** Trade-off assumido: é carga **cheia** de uma competência,
  não incremental. A Silver é `PARTITIONED BY (id_cmpt_movel)` (padrão para cargas
  mensais), mas o `CREATE OR REPLACE` apaga *todas* as competências e recria só a do
  CSV atual — carregar 2025-09 hoje **substituiria** 2025-08, não somaria. Para
  histórico multi-mês, a evolução natural é trocar o `CREATE OR REPLACE` da Silver por
  `INSERT OVERWRITE` com `replaceWhere id_cmpt_movel = '<competência>'` (ou `MERGE`),
  sobrescrevendo só a partição do mês carregado e mantendo idempotência.
- **Mascaramento (Silver):** CNPJ vira `CONCAT(SUBSTRING(nr_cnpj,1,8),'******')`
  (mantém só a raiz de 8 dígitos).
- **Particionamento:** Silver particionada por `id_cmpt_movel` (competência mensal);
  Gold pré-agregada (uma tabela por pergunta do case) para performance.
- **Metastore Hive persistente** (`config.py`, Derby em `/app/metastore_db`): sem
  isso o catálogo fica só em memória e cada task do Airflow (processo separado) não
  enxerga as tabelas das etapas anteriores. `.enableHiveSupport()` é obrigatório
  para a orquestração distribuída funcionar.
- **Airflow em modo produção (não standalone):** metadados em **Postgres** e
  serviços separados (`airflow-webserver` + `airflow-scheduler`) com **LocalExecutor**
  — o padrão real de produção. O standalone com SQLite foi abandonado porque o
  SQLite não suporta a concorrência dos 3 componentes e o webserver não completava
  o boot (a 8080 nunca entrava em LISTEN). Como as tasks rodam no processo do
  scheduler (LocalExecutor), é o **scheduler** que monta o `docker.sock` para o
  `docker exec case-spark`.
- **Airflow não duplica lógica:** cada task faz `docker exec case-spark python -m
  src.run_pipeline <etapa>`.
- **Streamlit desacoplado do Spark:** o dashboard (`app/`) só lê os CSVs de
  `output/` (agregados da Gold) — imagem própria sem Java/Spark, sobe em segundos.
  As 3 respostas do case (`a_`/`b_`/`c_`) e os insights (`insight_*`) são gerados
  por `src/queries.py`. O app degrada com elegância: se os `insight_*.csv` não
  existirem, cai para as versões reduzidas (top5 operadoras / top1 faixa).

## Armadilhas conhecidas (gotchas)

- **Base Docker:** usar `python:3.11-slim-bookworm` (não `-slim` puro). O `-slim`
  migrou para Debian trixie, que não tem `openjdk-17` (só 21, não suportado pelo Spark 3.5).
- **Memória do Spark:** driver com **6g** (`PYSPARK_SUBMIT_ARGS` em `config.py`) e
  `master local[4]`. Com o heap padrão de 1g a escrita da Bronze dá **OOM**.
- **Split de SQL:** o separador de statements ignora `;` dentro de aspas (o CSV usa
  `sep ';'`). Não trocar por um `split(';')` ingênuo.
- **Airflow 1º boot é lento** (webserver leva ~30–60s pós-migração). A ordem é
  garantida por healthchecks: `postgres` (healthy) → `airflow-init` (Exited 0) →
  webserver/scheduler. O webserver tem `start_period: 60s` no healthcheck.
- **`minio-init` e `airflow-init` saírem (Exited 0) é esperado** — são containers
  de tarefa única.

## Resultados de referência (competência 2025-08)

- **(a)** Top operadora: Notre Dame Intermédica (4.324.507 ativos).
- **(b)** Faixa etária com mais beneficiários: **40 a 44 anos** (3.100.823).
- **(c)** Município líder: São Paulo (9.833.635), de 646 municípios.
