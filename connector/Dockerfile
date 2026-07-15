FROM python:3.14-slim@sha256:d3400aa122fa42cf0af0dbe8ec3091b047eac5c8f7e3539f7135e86d855dc015

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/backend

COPY connector/requirements-hashes.txt /app/connector/requirements-hashes.txt
RUN PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ONLY_BINARY=:all: \
    pip install --no-cache-dir --require-hashes -r /app/connector/requirements-hashes.txt

COPY connector /app/connector
COPY backend/runner/connector.py /app/backend/runner/connector.py

RUN useradd --system --create-home --home-dir /home/connector --shell /usr/sbin/nologin connector \
    && chown -R connector:connector /app
USER connector

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import connector; from connector.main import DEFAULT_WS_URL; assert DEFAULT_WS_URL.startswith('wss://')"

CMD ["python", "-m", "connector.main"]
