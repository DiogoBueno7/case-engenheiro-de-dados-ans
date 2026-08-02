"""
Orquestrador do pipeline Medallion completo.

Executa, em ordem:
    Bronze -> Silver -> Gold -> Consultas

Uso (dentro do container):
    docker compose exec spark python -m src.run_pipeline

Ou apenas uma etapa:
    docker compose exec spark python -m src.run_pipeline bronze
"""

from __future__ import annotations

import sys

from src.config import get_spark, sql_params
from src.queries import run_queries
from src.sql_runner import run_sql_file

STEPS = {
    "bronze": ("00_bronze.sql", "Ingestão do CSV as-is (Delta)"),
    "silver": ("01_silver.sql", "Tipagem + mascaramento de CNPJ (Delta particionado)"),
    "gold": ("02_gold.sql", "Tabelas agregadas para consumo analítico"),
}


def main() -> None:
    args = [a.lower() for a in sys.argv[1:]]
    spark = get_spark("case-ans-medallion")
    params = sql_params()

    steps_to_run = args if args else list(STEPS.keys()) + ["queries"]

    for step in steps_to_run:
        if step in STEPS:
            filename, desc = STEPS[step]
            print(f"\n########## {step.upper()} — {desc} ##########")
            run_sql_file(spark, filename, params)
        elif step == "queries":
            print("\n########## CONSULTAS ##########")
            run_queries(spark)
        else:
            print(f"[aviso] etapa desconhecida: {step}")

    print("\nPipeline concluído.")
    spark.stop()


if __name__ == "__main__":
    main()
