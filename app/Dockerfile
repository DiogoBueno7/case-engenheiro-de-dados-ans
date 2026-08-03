# Imagem enxuta só para o dashboard (não precisa de Java/Spark: lê os CSVs
# já materializados da camada Gold em output/).
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY streamlit_app.py .

EXPOSE 8501

# --server.address=0.0.0.0 para expor fora do container; sem coleta de estatística.
CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--browser.gatherUsageStats=false"]
