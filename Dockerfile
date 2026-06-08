# Multi-stage build for the FastAPI agent service.
# Pre-downloads the sentence-transformers model so first boot is fast and
# the container survives without HuggingFace at runtime.

FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for asyncpg + lxml + torch wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Hatchling validates `readme = "README.md"` at metadata-generation time,
# so the README must be present even though we're only installing deps here.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && \
    pip install -e ".[embeddings]"

# Bake the embedding model into the image so the first /query call doesn't
# block on a HuggingFace download. ~80MB.
RUN python - <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer("all-MiniLM-L6-v2")
PY

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/root/.cache/huggingface \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python deps + the cached model from the builder stage.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache /root/.cache

COPY app ./app
COPY scripts ./scripts
COPY evals ./evals

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
