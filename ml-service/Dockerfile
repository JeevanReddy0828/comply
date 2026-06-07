# Isolated ML service. Pinned to 3.12 for broadest ML-wheel availability
# (torch / faiss-cpu / sentence-transformers). Independent of the core backend's
# Python 3.14 — that's the point of keeping this separate.
FROM python:3.12-slim

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8100

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
