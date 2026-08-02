# Airflow + CLI do Docker, para as tasks dispararem etapas no container Spark
# via `docker exec` (o Airflow fala com o daemon pelo socket montado no compose).
FROM apache/airflow:2.9.3

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends docker.io && \
    rm -rf /var/lib/apt/lists/*
USER airflow
