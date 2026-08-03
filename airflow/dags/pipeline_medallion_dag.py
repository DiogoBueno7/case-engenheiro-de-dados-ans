"""
DAG de orquestração do pipeline Medallion (ANS Beneficiários SP).

Cada etapa vira uma task que dispara o mesmo código Spark/SQL já existente,
executando-o no container `case-spark` via `docker exec`. A lógica de
transformação continua 100% nos scripts SQL (sql/) — o Airflow só orquestra:
ordem, dependências, agendamento mensal, retry e observabilidade.

Fluxo:  bronze -> silver -> gold -> consultas
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

SPARK_CONTAINER = "case-spark"


def step_cmd(step: str) -> str:
    """Comando que executa uma etapa do pipeline dentro do container Spark."""
    return f"docker exec {SPARK_CONTAINER} python -m src.run_pipeline {step}"


default_args = {
    "owner": "data-engineering",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="pipeline_medallion_ans",
    description="Pipeline Medallion ANS (Bronze -> Silver -> Gold -> Consultas)",
    default_args=default_args,
    # Dados da ANS são atualizados mensalmente.
    schedule="@monthly",
    start_date=pendulum.datetime(2025, 8, 1, tz="America/Sao_Paulo"),
    catchup=False,
    tags=["medallion", "ans", "spark", "delta"],
) as dag:

    bronze = BashOperator(
        task_id="bronze_ingestao_csv_raw",
        bash_command=step_cmd("bronze"),
        doc_md="Ingestão do CSV as-is para Delta (camada Bronze).",
    )

    silver = BashOperator(
        task_id="silver_tipagem_mascaramento_cnpj",
        bash_command=step_cmd("silver"),
        doc_md="Tipagem, mascaramento de CNPJ e particionamento (camada Silver).",
    )

    gold = BashOperator(
        task_id="gold_agregacoes_analiticas",
        bash_command=step_cmd("gold"),
        doc_md="Tabelas agregadas para consumo analítico (camada Gold).",
    )

    consultas = BashOperator(
        task_id="consultas_respostas_case",
        bash_command=step_cmd("queries"),
        doc_md="Executa as 3 consultas do case e salva os resultados em output/.",
    )

    bronze >> silver >> gold >> consultas
