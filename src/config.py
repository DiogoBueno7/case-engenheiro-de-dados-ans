"""
Configuração central do pipeline.

Cria a SparkSession já habilitada para:
  - Delta Lake (formato das camadas Silver/Gold);
  - acesso ao MinIO via protocolo S3A (emulando o Amazon S3).

Também centraliza os caminhos (paths) e a leitura das variáveis de ambiente,
para que os módulos de cada camada não repitam configuração.
"""

from __future__ import annotations

import os

# Define a memória do driver ANTES de a JVM subir. Em modo local o driver é
# também o executor, então este heap é o que processa os ~4,8M de registros.
# Precisa ser setado via PYSPARK_SUBMIT_ARGS (config na sessão não pega a tempo).
os.environ.setdefault(
    "PYSPARK_SUBMIT_ARGS", "--driver-memory 6g pyspark-shell"
)

from delta import configure_spark_with_delta_pip  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402

# Jars adicionais para o conector S3A (Hadoop) conversar com o MinIO/S3.
# As versões são compatíveis com o Hadoop 3.3.4 que acompanha o PySpark 3.5.x.
_S3_PACKAGES = [
    "org.apache.hadoop:hadoop-aws:3.3.4",
    "com.amazonaws:aws-java-sdk-bundle:1.12.262",
]


def get_spark(app_name: str = "case-ans-medallion") -> SparkSession:
    """Retorna uma SparkSession com Delta Lake e acesso ao MinIO (S3A)."""
    endpoint = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")

    builder = (
        SparkSession.builder.appName(app_name)
        # Modo local; limita os cores para evitar writers demais competindo
        # pela memória (cada writer Parquet bufferiza um row group).
        .master("local[4]")
        # --- Delta Lake ---
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        # --- Conexão S3A -> MinIO ---
        .config("spark.hadoop.fs.s3a.endpoint", endpoint)
        .config("spark.hadoop.fs.s3a.access.key", access_key)
        .config("spark.hadoop.fs.s3a.secret.key", secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config(
            "spark.hadoop.fs.s3a.impl",
            "org.apache.hadoop.fs.s3a.S3AFileSystem",
        )
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        # --- Performance ---
        .config("spark.sql.shuffle.partitions", "8")
        # --- Event log (Spark History Server) ---
        # Grava o histórico de cada execução em disco (volume compartilhado), para
        # que o History Server (container case-spark-history, porta 18080) mostre a
        # Spark UI de jobs JÁ FINALIZADOS — a 4040/4041 só existe durante o job.
        .config("spark.eventLog.enabled", "true")
        .config("spark.eventLog.dir", "file:///spark-events")
        # --- Metastore persistente (Hive/Derby) ---
        # Sem isto, o catálogo (databases/tabelas) fica só em memória e some ao
        # fim do processo. Como cada task do Airflow roda em um processo próprio
        # (docker exec), precisamos que o catálogo persista em disco para uma
        # etapa enxergar as tabelas criadas pela anterior.
        .config(
            "javax.jdo.option.ConnectionURL",
            "jdbc:derby:;databaseName=/app/metastore_db;create=true",
        )
        .config("spark.sql.warehouse.dir", "/app/spark-warehouse")
        .enableHiveSupport()
    )

    spark = configure_spark_with_delta_pip(
        builder, extra_packages=_S3_PACKAGES
    ).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def lake_root() -> str:
    """Raiz do lakehouse (ex.: s3a://lakehouse)."""
    return os.environ.get("LAKE_ROOT", "s3a://lakehouse")


def csv_path() -> str:
    """Caminho do arquivo bruto da ANS (dentro do container)."""
    return os.environ.get("CSV_PATH", "/app/data/pda-024-icb-SP-2025_08.csv")


def sql_params() -> dict[str, str]:
    """Parâmetros injetados nos arquivos .sql (substituição de {{PLACEHOLDER}})."""
    return {
        "LAKE_ROOT": lake_root(),
        "CSV_PATH": csv_path(),
    }
