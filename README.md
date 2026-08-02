# Case Engenheiro de Dados — Pipeline Medallion (ANS Beneficiários SP)

Pipeline de dados em **arquitetura Medallion** (Bronze → Silver → Gold) sobre os dados
públicos da **ANS** (operadoras e beneficiários de planos de saúde de São Paulo).

O projeto emula, **localmente via Docker**, a mesma stack usada em produção na nuvem
(AWS / Databricks) — sem qualquer custo de nuvem e 100% reproduzível:

| Papel no pipeline            | Tecnologia local (este projeto) | Equivalente em produção                    |
|------------------------------|---------------------------------|--------------------------------------------|
| Orquestração                 | **Apache Airflow**              | Airflow / MWAA / Databricks Workflows      |
| Processamento / ETL          | **PySpark**                     | AWS Glue / Databricks / Spark              |
| Formato do data lake         | **Delta Lake**                  | Delta Lake (Databricks)                    |
| Object storage (data lake)   | **MinIO** (S3-compatible)       | Amazon S3                                  |
| Consulta SQL analítica       | **Spark SQL**                   | Amazon Athena / Databricks SQL             |
| Camada curada (warehouse)    | **Gold (Delta)**                | Amazon Redshift                            |

O mesmo código Spark/Delta e os mesmos scripts SQL rodam sem alteração no
**Databricks** (basta apontar os caminhos para o S3 real).

---

## Arquitetura

![Arquitetura do pipeline](docs/arquitetura.png)

<details>
<summary>Versão em texto (Mermaid)</summary>

```mermaid
flowchart LR
    CSV[CSV bruto ANS<br/>~1,5 GB / 4,8M linhas] -->|Spark SQL| B

    subgraph LAKE[Data Lake - MinIO / S3]
        B[BRONZE<br/>Delta - as-is<br/>+ auditoria]
        S[SILVER<br/>Delta tipado<br/>CNPJ mascarado<br/>particionado por competência]
        G[GOLD<br/>Delta agregado<br/>por operadora / faixa / município]
    end

    B -->|tipagem + mascaramento| S
    S -->|agregações| G
    G -->|3 consultas| Q[Resultados<br/>output/*.csv]
```

</details>

### Camadas

- **Bronze** (`sql/00_bronze.sql`) — ingestão do CSV *as-is*, todas as colunas como
  texto, apenas com metadados de auditoria (`_ingested_at`, `_source_file`). Formato Delta.
- **Silver** (`sql/01_silver.sql`) — tipagem correta (quantidades → `INT`, `DT_CARGA` →
  `DATE`), normalização de nomes para `snake_case`, **mascaramento do CNPJ** (mantém a
  raiz de 8 dígitos e oculta o restante) e **particionamento por competência**
  (`id_cmpt_movel`), padrão para cargas mensais.
- **Gold** (`sql/02_gold.sql`) — tabelas agregadas, uma por pergunta do case, para
  consumo analítico rápido sem reprocessar os 4,8M de registros.

---

## Como executar

Pré-requisitos: **Docker** e **Docker Compose**. O arquivo
`data/pda-024-icb-SP-2025_08.csv` já deve estar na pasta `data/`.

```bash
# 1. (opcional) copie o exemplo de variáveis de ambiente
cp .env.example .env

# 2. suba o ambiente (MinIO + Spark/Jupyter) — a primeira build baixa os jars
docker compose up -d --build

# 3. rode o pipeline completo (Bronze -> Silver -> Gold -> Consultas)
docker compose exec spark python -m src.run_pipeline
```

- **JupyterLab** (notebooks estilo Databricks): http://localhost:8888
- **Console do MinIO** (ver os buckets bronze/silver/gold): http://localhost:9001
  (usuário/senha: `minioadmin` / `minioadmin`)
- **Spark UI** (durante um job): http://localhost:4040

Rodar apenas uma etapa:

```bash
docker compose exec spark python -m src.run_pipeline silver
```

Os resultados das 3 consultas são exibidos no console e salvos em `output/`.

---

## Orquestração (Apache Airflow)

Além de rodar o pipeline pela linha de comando, o projeto inclui um **DAG do
Airflow** que orquestra as etapas de forma programática, com dependências,
agendamento mensal (`@monthly`, acompanhando a atualização dos dados da ANS),
retry e interface visual.

A lógica **não é duplicada**: cada task do DAG apenas dispara a etapa
correspondente no container Spark via `docker exec` — a transformação continua
nos scripts SQL. Cada etapa é um processo isolado (como um *job task* no
Databricks Workflows / AWS Glue), e o catálogo é compartilhado entre elas por
um **metastore Hive persistente**.

```
bronze  ->  silver  ->  gold  ->  consultas
```

Acesso à UI: **http://localhost:8080**

- Usuário: `admin`
- Senha: `admin`

Na UI, habilite (toggle) o DAG `pipeline_medallion_ans` e clique em **Trigger**.
Também dá para rodar tudo pela linha de comando, sem a UI:

```bash
# executa o DAG inteiro de forma síncrona
docker compose exec airflow airflow dags test pipeline_medallion_ans 2025-08-01
```

> Observação: o **primeiro boot** do Airflow é lento (migração do banco +
> criação de papéis). Se a UI na 8080 demorar a responder, aguarde alguns
> minutos ou rode `docker compose restart airflow` — no segundo boot ela sobe
> em segundos. O Airflow roda em modo `standalone` (SQLite + SequentialExecutor),
> adequado ao case; em produção usaria Postgres + Celery/Kubernetes Executor.

---

## Consultas do case

As três respostas estão em `sql/03_consultas.sql` e são executadas por
`src/queries.py`:

- **(a)** As 5 operadoras com maior número de beneficiários ativos.
- **(b)** A faixa etária com mais beneficiários (e o total).
- **(c)** Quantidade de beneficiários por município, em ordem decrescente.

Saídas geradas:

| Arquivo                                    | Consulta |
|--------------------------------------------|----------|
| `output/a_top5_operadoras.csv`             | (a)      |
| `output/b_faixa_etaria_top.csv`            | (b)      |
| `output/c_beneficiarios_por_municipio.csv` | (c)      |

### Resultados (competência 2025-08)

Processados **4.830.707 registros** do arquivo da ANS.

**(a) As 5 operadoras com maior número de beneficiários ativos**

| # | Código | Operadora                                  | Beneficiários ativos |
|---|--------|--------------------------------------------|---------------------:|
| 1 | 359017 | NOTRE DAME INTERMÉDICA SAÚDE S.A.          |            4.324.507 |
| 2 | 301949 | ODONTOPREV S/A                             |            2.844.728 |
| 3 | 326305 | AMIL ASSISTÊNCIA MÉDICA INTERNACIONAL S.A. |            2.671.950 |
| 4 | 006246 | SUL AMERICA COMPANHIA DE SEGURO SAÚDE      |            2.111.707 |
| 5 | 000582 | PORTO SEGURO - SEGURO SAÚDE S/A            |            1.391.580 |

**(b) Faixa etária com mais beneficiários**

A faixa **40 a 44 anos**, com **3.100.823** beneficiários ativos.

**(c) Beneficiários por município (decrescente)**

646 municípios no total. Top 10:

| # | Código | Município             | Beneficiários ativos |
|---|--------|-----------------------|---------------------:|
| 1 | 355030 | São Paulo             |            9.833.635 |
| 2 | 350950 | Campinas              |            1.031.975 |
| 3 | 351880 | Guarulhos             |            1.013.731 |
| 4 | 354870 | São Bernardo do Campo |              747.368 |
| 5 | 354780 | Santo André           |              703.818 |
| 6 | 353440 | Osasco                |              603.048 |
| 7 | 355220 | Sorocaba              |              596.055 |
| 8 | 354990 | São José dos Campos   |              581.614 |
| 9 | 354340 | Ribeirão Preto        |              563.972 |
|10 | 352590 | Jundiaí               |              444.951 |

Lista completa em `output/c_beneficiarios_por_municipio.csv`.

---

## Estrutura do projeto

```
.
├── docker-compose.yml      # MinIO (S3) + Spark/Jupyter + Airflow
├── Dockerfile              # imagem Spark + Delta + jars S3A
├── requirements.txt
├── data/                   # CSV bruto da ANS (não versionado)
├── sql/                    # lógica das camadas em Spark SQL
│   ├── 00_bronze.sql
│   ├── 01_silver.sql
│   ├── 02_gold.sql
│   └── 03_consultas.sql
├── src/                    # execução em Python
│   ├── config.py           # SparkSession (Delta + S3A/MinIO + metastore Hive)
│   ├── sql_runner.py       # executa os arquivos .sql
│   ├── queries.py          # roda e salva as 3 consultas
│   └── run_pipeline.py     # runner Bronze->Silver->Gold->Consultas
├── airflow/                # orquestração
│   ├── Dockerfile          # Airflow + CLI do Docker
│   └── dags/
│       └── pipeline_medallion_dag.py
├── notebooks/              # versão notebook (estilo Databricks)
└── output/                 # resultados das consultas
```

---

## Notas de engenharia

- **Formato Delta** em todas as camadas transacionais (Silver/Gold): tipagem forte,
  versionamento (time travel) e leitura/escrita otimizadas.
- **Mascaramento** aplicado na Silver, cumprindo a regra de dado sensível do case.
- **Particionamento** por competência na Silver e **pré-agregação** na Gold como
  estratégias de performance.
- **Modularidade**: cada camada é um script SQL isolado; o Python só executa.
- **Orquestração**: DAG do Airflow com dependências, agendamento e retry,
  reaproveitando as mesmas etapas sem duplicar lógica.
- **Portabilidade**: trocar MinIO por S3 real e Spark local por Databricks exige
  apenas ajustar credenciais/caminhos — o SQL não muda.
