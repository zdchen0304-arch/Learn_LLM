FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend

WORKDIR /app/backend

RUN addgroup --system maars \
    && adduser --system --ingroup maars --home /nonexistent maars

COPY backend/requirements.txt backend/requirements.container.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.container.txt \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=maars:maars backend/ /app/backend/
COPY --chown=maars:maars frontend/ /app/frontend/

RUN mkdir -p /data/logs /data/sandbox \
    && chown -R maars:maars /data

USER maars

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "from urllib.request import urlopen; assert urlopen('http://127.0.0.1:3001/healthz', timeout=3).status == 200"

CMD ["python", "-m", "uvicorn", "main:asgi_app", "--host", "0.0.0.0", "--port", "3001", "--loop", "asyncio", "--http", "h11"]

# This target is intentionally opt-in. Docker socket access gives an Agent broad
# control over the host's containers, so only use it with compose.task-agent.yaml
# on a trusted development machine.
FROM runtime AS task-agent

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*
USER maars

# Keep the least-privileged runtime as the default `docker build` target.
FROM runtime AS final
