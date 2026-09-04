FROM python:3.14-slim@sha256:a7fb1e634c4a578f9e0bd6327f11a3cde11b7a9395f48e24360c0988bcc5c2bc

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/backend

COPY backend/requirements-hashes.txt /app/backend/requirements-hashes.txt
COPY connector/requirements-hashes.txt /app/connector/requirements-hashes.txt
RUN PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ONLY_BINARY=:all: \
    pip install --no-cache-dir --require-hashes \
      -r /app/backend/requirements-hashes.txt \
      -r /app/connector/requirements-hashes.txt

COPY connector /app/connector
COPY backend /app/backend

RUN python -c "import os, secrets; os.environ['DATABASE_URL'] = 'postgresql+asyncpg://connector:connector@db.invalid/naruon'; os.environ['AUTH_SESSION_HMAC_SECRET'] = secrets.token_urlsafe(48); from runner.local_dav_adapters import LocalDavAdapters; from runner.local_mail_adapters import LocalMailAdapters"

RUN useradd --system --create-home --home-dir /home/connector --shell /usr/sbin/nologin connector \
    && chown -R connector:connector /app
USER connector

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import connector; from connector.main import DEFAULT_WS_URL; assert DEFAULT_WS_URL.startswith('wss://')"

CMD ["python", "-m", "connector.main"]
