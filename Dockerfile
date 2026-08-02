# bookworm (Debian 12) ainda traz o OpenJDK 17, versão suportada pelo Spark 3.5.
# (o slim padrão migrou para trixie, que só oferece o JDK 21)
FROM python:3.11-slim-bookworm

# Java (necessário para o Spark) + utilitários
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        procps \
        curl && \
    rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PYSPARK_PYTHON=python3
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pré-baixa os jars do Delta + S3A (hadoop-aws) para o cache do Ivy,
# evitando download a cada execução do pipeline.
RUN python -c "\
from pyspark.sql import SparkSession; \
from delta import configure_spark_with_delta_pip; \
b = SparkSession.builder.appName('warmup'); \
extra = ['org.apache.hadoop:hadoop-aws:3.3.4','com.amazonaws:aws-java-sdk-bundle:1.12.262']; \
s = configure_spark_with_delta_pip(b, extra_packages=extra).getOrCreate(); \
s.stop()"

EXPOSE 8888

# Sobe o JupyterLab por padrão (para desenvolver/rodar os notebooks estilo Databricks).
# O pipeline em si pode ser rodado via: docker compose exec spark python -m src.run_pipeline
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--NotebookApp.token=''"]
