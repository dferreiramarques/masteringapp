# MasteringApp — FastAPI + numpy DSP
# Railway detecta este ficheiro e faz o build automaticamente.
FROM python:3.12-slim

WORKDIR /app

# garantia: o soundfile já traz libsndfile na wheel, mas algumas imagens slim
# não têm as libs de runtime de áudio — instalar é barato.
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY static/ static/

# Railway injeta a variável PORT no deploy (TCP proxy)
ENV HOST=0.0.0.0
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
