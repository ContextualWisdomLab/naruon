FROM python:3.14-slim@sha256:b877e50bd90de10af8d82c57a022fc2e0dc731c5320d762a27986facfc3355c1

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

CMD ["python", "-m", "connector.main"]
