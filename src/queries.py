"""
Executa as 3 consultas do case sobre a camada Gold, imprime no console e
salva os resultados em output/ (CSV) para servirem de entregável.

O SQL das consultas vive em sql/03_consultas.sql (fonte única da verdade,
igual às demais camadas). Aqui só lemos os statements de lá, executamos e
salvamos cada resultado no CSV correspondente.
"""

from __future__ import annotations

from pathlib import Path

from pyspark.sql import DataFrame, SparkSession

from src.config import sql_params
from src.sql_runner import parse_named_sql_file

OUTPUT_DIR = Path("/app/output")

CONSULTAS_SQL = "03_consultas.sql"


def _save(df: DataFrame, name: str) -> None:
    """Salva o resultado como um único CSV legível em output/<name>.csv."""
    pdf = df.toPandas()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf.to_csv(OUTPUT_DIR / f"{name}.csv", index=False, encoding="utf-8")


def run_queries(spark: SparkSession) -> None:
    """Executa cada consulta de 03_consultas.sql e salva output/<nome>.csv.

    O nome (`-- out:`) e o rótulo (`-- label:`) vêm do próprio .sql, então
    adicionar, remover ou reordenar consultas é feito só no arquivo SQL.
    """
    for q in parse_named_sql_file(CONSULTAS_SQL, sql_params()):
        df = spark.sql(q.sql)
        print(f"\n{q.label}:")
        df.show(20, truncate=False)
        _save(df, q.name)

    print(f"\nResultados salvos em {OUTPUT_DIR}/")
