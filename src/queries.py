"""
Executa as 3 consultas do case sobre a camada Gold, imprime no console e
salva os resultados em output/ (CSV) para servirem de entregável.
"""

from __future__ import annotations

from pathlib import Path

from pyspark.sql import DataFrame, SparkSession

OUTPUT_DIR = Path("/app/output")


def _save(df: DataFrame, name: str) -> None:
    """Salva o resultado como um único CSV legível em output/<name>.csv."""
    pdf = df.toPandas()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf.to_csv(OUTPUT_DIR / f"{name}.csv", index=False, encoding="utf-8")


def run_queries(spark: SparkSession) -> None:
    # (a) Top 5 operadoras por beneficiários ativos
    top_operadoras = spark.sql(
        """
        SELECT cd_operadora, nm_razao_social, qt_beneficiarios_ativos
        FROM gold.beneficiarios_por_operadora
        ORDER BY qt_beneficiarios_ativos DESC
        LIMIT 5
        """
    )

    # (b) Faixa etária com mais beneficiários
    top_faixa = spark.sql(
        """
        SELECT de_faixa_etaria, qt_beneficiarios_ativos
        FROM gold.beneficiarios_por_faixa_etaria
        ORDER BY qt_beneficiarios_ativos DESC
        LIMIT 1
        """
    )

    # (c) Beneficiários por município (decrescente)
    por_municipio = spark.sql(
        """
        SELECT cd_municipio, nm_municipio, qt_beneficiarios_ativos
        FROM gold.beneficiarios_por_municipio
        ORDER BY qt_beneficiarios_ativos DESC
        """
    )

    print("\n(a) Top 5 operadoras por beneficiários ativos:")
    top_operadoras.show(truncate=False)

    print("(b) Faixa etária com mais beneficiários:")
    top_faixa.show(truncate=False)

    print("(c) Beneficiários por município (top 20 de", por_municipio.count(), "):")
    por_municipio.show(20, truncate=False)

    _save(top_operadoras, "a_top5_operadoras")
    _save(top_faixa, "b_faixa_etaria_top")
    _save(por_municipio, "c_beneficiarios_por_municipio")
    print(f"\nResultados salvos em {OUTPUT_DIR}/")
