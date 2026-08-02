"""
Utilitário para executar arquivos .sql no Spark.

A lógica de transformação de cada camada mora em arquivos .sql (Spark SQL),
mantendo a linguagem SQL como pedido no case. Este runner:
  1. lê o arquivo;
  2. substitui placeholders {{LAKE_ROOT}}, {{CSV_PATH}} pelos valores reais;
  3. quebra em statements individuais e executa um a um.
"""

from __future__ import annotations

from pathlib import Path

from pyspark.sql import SparkSession

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def _render(sql_text: str, params: dict[str, str]) -> str:
    for key, value in params.items():
        sql_text = sql_text.replace("{{" + key + "}}", value)
    return sql_text


def _split_statements(sql_text: str) -> list[str]:
    """Quebra o script em statements.

    Ignora comentários de linha (--) e, principalmente, não quebra em ';'
    que estejam dentro de strings (ex.: o separador `sep ';'` do CSV).
    """
    lines = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        lines.append(line)
    joined = "\n".join(lines)

    statements = []
    current = []
    in_string = False
    for ch in joined:
        if ch == "'":
            in_string = not in_string
        if ch == ";" and not in_string:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def run_sql_file(
    spark: SparkSession, filename: str, params: dict[str, str]
) -> None:
    """Executa todos os statements de um arquivo .sql da pasta sql/."""
    path = SQL_DIR / filename
    sql_text = _render(path.read_text(encoding="utf-8"), params)
    statements = _split_statements(sql_text)
    print(f"\n=== {filename}  ({len(statements)} statements) ===")
    for i, stmt in enumerate(statements, start=1):
        preview = " ".join(stmt.split())[:80]
        print(f"  [{i}/{len(statements)}] {preview}...")
        spark.sql(stmt)
