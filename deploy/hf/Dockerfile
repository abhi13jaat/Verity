# Backend image for Hugging Face Spaces (Docker SDK).
# Runs Alembic migrations -> Celery worker -> Uvicorn, all in one container.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# HF Spaces run the container as a non-root user (uid 1000).
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/home/user/app/.cache/fastembed \
    HF_HOME=/home/user/app/.cache/hf

WORKDIR /home/user/app

# Bake the embedding + reranker models BEFORE copying app code so this layer
# stays cached across code changes — faster auto-deploys, no re-download.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')" || true
RUN python -c "from fastembed.rerank.cross_encoder import TextCrossEncoder; TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2')" || true

COPY --chown=user . .

EXPOSE 7860
CMD ["bash", "deploy/hf/start.sh"]
