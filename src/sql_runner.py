"""
Utilitário para executar arquivos .sql no Spark.

A lógica de transformação de cada camada mora em arquivos .sql (Spark SQL),
mantendo a linguagem SQL como pedido no case. Este runner:
  1. lê o arquivo;
  2. substitui placeholders {{LAKE_ROOT}}, {{CSV_PATH}} pelos valores reais;
  3. quebra em statements individuais e executa um a um.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from pyspark.sql import SparkSession

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

# Marcadores (linha de comentário) que antecedem um statement:
#   `-- out: <nome>`     obrigatório — identifica o resultado (ex.: nome do CSV).
#   `-- label: <texto>`  opcional     — rótulo amigável para exibir no console.
_OUT_TAG = re.compile(r"^\s*--\s*out:\s*(\S+)\s*$", re.IGNORECASE)
_LABEL_TAG = re.compile(r"^\s*--\s*label:\s*(.+?)\s*$", re.IGNORECASE)


class NamedStatement(NamedTuple):
    """Um statement de um .sql anotado, com seu nome e rótulo."""
    name: str          # do marcador `-- out:` (ex.: arquivo de saída)
    label: str         # do marcador `-- label:` (cai para `name` se ausente)
    sql: str           # o statement SQL em si


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


def parse_sql_file(filename: str, params: dict[str, str]) -> list[str]:
    """Lê um arquivo .sql da pasta sql/, aplica os placeholders e devolve os
    statements individuais — sem executá-los.

    Útil para quem precisa dos statements como DataFrames (ex.: as consultas do
    case em queries.py), mantendo o SQL como fonte única da verdade.
    """
    path = SQL_DIR / filename
    sql_text = _render(path.read_text(encoding="utf-8"), params)
    return _split_statements(sql_text)


def parse_named_sql_file(
    filename: str, params: dict[str, str]
) -> list[NamedStatement]:
    """Lê um .sql anotado e devolve os statements com seu nome e rótulo.

    Cada statement é precedido por `-- out: <nome>` (obrigatório) e,
    opcionalmente, `-- label: <texto>`. Como o nome/rótulo vivem no próprio .sql,
    junto da consulta, a ordem no arquivo é irrelevante e não há mapeamento a
    manter no Python — adicionar/remover/reordenar consultas é feito só aqui.
    """
    path = SQL_DIR / filename
    sql_text = _render(path.read_text(encoding="utf-8"), params)

    results: list[NamedStatement] = []
    pending_name: str | None = None
    pending_label: str | None = None
    buffer: list[str] = []
    in_string = False

    def flush() -> None:
        nonlocal pending_name, pending_label
        stmt = "".join(buffer).strip()
        buffer.clear()
        if not stmt:
            return
        if pending_name is None:
            raise ValueError(
                f"{filename}: statement sem '-- out: <nome>' antes dele: "
                f"{' '.join(stmt.split())[:60]}..."
            )
        results.append(
            NamedStatement(pending_name, pending_label or pending_name, stmt)
        )
        pending_name = pending_label = None

    for line in sql_text.splitlines():
        m = _OUT_TAG.match(line)
        if m:
            pending_name = m.group(1)
            continue
        m = _LABEL_TAG.match(line)
        if m:
            pending_label = m.group(1)
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        for ch in line:
            if ch == "'":
                in_string = not in_string
            if ch == ";" and not in_string:
                flush()
            else:
                buffer.append(ch)
        buffer.append("\n")

    flush()  # statement final sem ';' à direita
    return results


def run_sql_file(
    spark: SparkSession, filename: str, params: dict[str, str]
) -> None:
    """Executa todos os statements de um arquivo .sql da pasta sql/."""
    statements = parse_sql_file(filename, params)
    print(f"\n=== {filename}  ({len(statements)} statements) ===")
    for i, stmt in enumerate(statements, start=1):
        preview = " ".join(stmt.split())[:80]
        print(f"  [{i}/{len(statements)}] {preview}...")
        spark.sql(stmt)
