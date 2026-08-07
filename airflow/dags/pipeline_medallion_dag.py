"""
DAG de orquestração do pipeline Medallion (ANS Beneficiários SP).

Cada etapa vira uma task que dispara o mesmo código Spark/SQL já existente,
executando-o no container do serviço `spark` via `docker exec`. A lógica de
transformação continua 100% nos scripts SQL (sql/) — o Airflow só orquestra:
ordem, dependências, agendamento mensal, retry e observabilidade.

Fluxo:  bronze -> silver -> gold -> consultas
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

# Serviço do Compose (NÃO um nome de container fixo). O container é resolvido em
# tempo de execução pelo label que o Compose atribui — assim o DAG funciona
# independentemente da pasta/projeto em que o repo foi clonado (o Compose nomeia
# os containers como `<projeto>-spark-1`, sem `container_name` fixo). Como as
# portas do host impedem duas stacks simultâneas, há sempre um único `spark`
# rodando, então o filtro por label resolve para o container certo.
SPARK_SERVICE = "spark"


def step_cmd(step: str) -> str:
    """Comando que executa uma etapa do pipeline dentro do container Spark.

    Resolve o container do serviço `spark` pelo label do Compose (evita
    `container_name` fixo, que colidia entre clones do repo). Sem chaves de
    Go-template (`{{ }}`) de propósito: o BashOperator renderiza o comando com
    Jinja e elas seriam interpretadas.
    """
    return (
        f"CID=$(docker ps -q --filter label=com.docker.compose.service={SPARK_SERVICE} | head -n1); "
        'if [ -z "$CID" ]; then '
        f"echo \"Container do servico '{SPARK_SERVICE}' nao encontrado (a stack esta de pe?)\"; "
        "exit 1; fi; "
        f'docker exec "$CID" python -m src.run_pipeline {step}'
    )


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
