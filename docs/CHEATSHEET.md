# Cheatsheet — revisar 5 min antes de apresentar

> Material completo: [`APRESENTACAO.md`](APRESENTACAO.md). Isto aqui é só o essencial.

## A espinha dorsal (decore isto e sustenta 80% da conversa)

1. **CSV de 4,8M linhas da ANS → lakehouse Medallion em Docker** que espelha a stack
   de produção (Spark/Delta/S3/Airflow) sem custo de nuvem.
2. **Regra de negócio vive em SQL** (`sql/*.sql`); Python só orquestra; Airflow só
   agenda e encadeia. **Ninguém duplica lógica.**
3. **Bronze** = cópia crua as-is + auditoria · **Silver** = tipado, CNPJ mascarado,
   particionado por competência · **Gold** = 1 tabela agregada por pergunta.
4. **O mesmo código roda no Databricks** — só trocar MinIO→S3 e caminhos.

## O fluxo do dado (saiba desenhar no quadro)

```
CSV 1,5GB ──Spark SQL──> BRONZE (Delta, texto puro + _ingested_at, _source_file)
                          │  tipa · mascara CNPJ · particiona por id_cmpt_movel
                          ▼
                         SILVER (Delta tipado)
                          │  SUM(qt_beneficiario_ativo) por operadora/faixa/município
                          ▼
                         GOLD (3 tabelas) ──queries──> output/*.csv ──> Streamlit
        Encadeado pelo Airflow: bronze → silver → gold → consultas
```

## As 3 respostas (competência 2025-08)

| # | Pergunta | Resposta |
|---|----------|----------|
| a | Top operadora por ativos | **Notre Dame Intermédica** — 4.324.507 |
| b | Faixa etária com mais ativos | **40 a 44 anos** — 3.100.823 |
| c | Município líder | **São Paulo** — 9.833.635 (de 646 municípios) |

## Stack — equivalência local ↔ produção

| Local (Docker) | Produção |
|----------------|----------|
| PySpark + Delta | AWS Glue / Databricks |
| MinIO | Amazon S3 |
| Spark SQL | Athena / Databricks SQL |
| Gold (Delta) | Amazon Redshift |
| Airflow (LocalExecutor) | MWAA / Databricks Workflows |
| Streamlit | QuickSight / Power BI |

## Q&A relâmpago (respostas de 1 linha)

- **Por que Spark pra 1,5GB? Pandas resolvia.** → Escolha de *plataforma*: a empresa
  usa Databricks/Glue e escala pras próximas UFs/meses sem trocar ferramenta.
- **Por que Delta e não Parquet?** → ACID + versionamento + schema evolution. Salvou
  a Silver/Gold quando um job deu OOM no meio (sem estado corrompido).
- **Por que mascarar o CNPJ?** → Case pede mascaramento na Silver. Mantenho a raiz
  (8 díg = grupo econômico) e oculto o resto → minimização de dados.
- **Como escala pra histórico mensal?** → Já particionei por `id_cmpt_movel`; troco
  `CREATE OR REPLACE` por `MERGE` (upsert) e parametrizo por arquivo/UF.
- **Gold pré-agregada não é redundante?** → Troca consciente: storage barato por
  consulta rápida. Evita varrer 4,8M linhas por pergunta. É o papel do "Redshift".
- **Como está o Airflow?** → Produção: **Postgres + webserver/scheduler separados +
  LocalExecutor**. Não é standalone.

## As 2 histórias de guerra (narrativa causa → efeito, não código)

- **OOM na Bronze:** Spark local sobe com heap de 1GB; escrita Parquet estourou.
  Diagnóstico: em modo local *o driver É o executor*. Fix: `--driver-memory 6g`
  antes da JVM subir + `local[4]`.
- **Airflow não via as tabelas (o mais sutil):** cada task é um processo separado
  (`docker exec`), catálogo só em memória sumia entre tasks. Fix: **metastore Hive
  persistente** (Derby em disco) + `.enableHiveSupport()`. *Lição: o que funciona
  num script monolítico quebra na orquestração distribuída.*

## Comandos que talvez precise ao vivo

```bash
docker compose up -d --build                      # sobe tudo
docker compose exec spark python -m src.run_pipeline   # roda o pipeline completo
# UIs: Streamlit 8501 · Airflow 8080 (admin/admin) · MinIO 9001 · Spark 4040
```

## Limitações (honestidade ajuda na defesa)

- Carga **full** de uma competência (não incremental) → evolução é `MERGE`.
- **LocalExecutor** single-node → escala real seria Celery/Kubernetes Executor.
- Sem testes de qualidade de dado (ex.: Great Expectations) → próximo passo.
- Metastore Derby embutido → em produção seria Glue Data Catalog / Unity Catalog.
