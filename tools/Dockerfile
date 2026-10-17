FROM python:3.12-slim
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && python -c "import duckdb; duckdb.sql('install httpfs; install aws')"
ENV PYTHONPATH=/work/tools:/work/lambda/ingest PYTHONUNBUFFERED=1
WORKDIR /work
