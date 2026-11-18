# Build a partir da RAIZ do repositório:
#   docker build -f api/Dockerfile -t alertabueiro-api .
# No Render o render.yaml já aponta para este arquivo.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8000
WORKDIR /app

COPY api/requirements.txt api/requirements.txt
RUN pip install -r api/requirements.txt

COPY api/ api/
# best.onnx e metrics.json; sem modelo a API roda em modo demo
COPY model/ model/

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
