# Apple Silicon / MLX local path

The default `docker-compose.yml` keeps the Linux Ollama container. Use this
page only when you want a temporary override that points the backend at a host
MLX or other OpenAI-compatible server. Do not commit the override files.

Copy the existing project `.env` first so `POSTGRES_PASSWORD`,
`AUTH_SESSION_HMAC_SECRET`, and `ENCRYPTION_KEY` stay operator-injected. Then
append only the MLX model-path overrides. Do not invent defaults for those
runtime secrets.

```bash
cp .env .env.mlx
cat >> .env.mlx <<'EOF'
OPENAI_API_KEY=mlx
ALLOWED_LLM_BASE_URL_HOSTS=localhost,127.0.0.1,host.docker.internal
ALLOW_LOCAL_LLM_PROVIDERS=true
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
OPENAI_EMBEDDING_MODEL=embeddinggemma
OPENAI_MODEL=gemma4:e2b-it-qat
NARUON_FRONTEND_HOST_PORT=127.0.0.1:3000
NARUON_BACKEND_HOST_PORT=127.0.0.1:8000
NARUON_MLX_EXTRA_HOSTS=host-gateway
NARUON_MLX_ALLOWED_LLM_BASE_URL_HOSTS=localhost,127.0.0.1,host.docker.internal
NARUON_MLX_OPENAI_API_KEY=mlx
NARUON_MLX_BASE_URL=http://host.docker.internal:11434/v1
NARUON_MLX_EMBEDDING_MODEL=embeddinggemma
NARUON_MLX_LLM_MODEL=gemma4:e2b-it-qat
EOF

mlx_compose_override="$(mktemp "${TMPDIR:-/tmp}/docker-compose.mlx.XXXXXX.yml")"
cat > "$mlx_compose_override" <<'EOF'
services:
  backend:
    depends_on:
      db:
        condition: service_healthy
    environment:
      ALLOW_LOCAL_LLM_PROVIDERS: "true"
      ALLOWED_LLM_BASE_URL_HOSTS: ${NARUON_MLX_ALLOWED_LLM_BASE_URL_HOSTS:-localhost,127.0.0.1,host.docker.internal}
      OPENAI_API_KEY: ${NARUON_MLX_OPENAI_API_KEY:-mlx}
      OPENAI_BASE_URL: ${NARUON_MLX_BASE_URL:-http://host.docker.internal:11434/v1}
      OPENAI_EMBEDDING_MODEL: ${NARUON_MLX_EMBEDDING_MODEL:-embeddinggemma}
      OPENAI_MODEL: ${NARUON_MLX_LLM_MODEL:-gemma4:e2b-it-qat}
    extra_hosts:
      - "host.docker.internal:${NARUON_MLX_EXTRA_HOSTS:-host.docker.internal}"
    ports:
      - "${NARUON_BACKEND_HOST_PORT:-127.0.0.1:8000}:8000"
  frontend:
    ports:
      - "${NARUON_FRONTEND_HOST_PORT:-127.0.0.1:3000}:3000"
EOF

NARUON_ENV_FILE=.env.mlx \
docker compose --env-file .env.mlx -f docker-compose.yml -f "$mlx_compose_override" up -d --build

curl -sf http://127.0.0.1:11434/v1/models >/dev/null && \
  echo "MLX/OpenAI-compatible server is reachable" || \
  echo "MLX endpoint is not reachable on 127.0.0.1:11434"
```

Private mailbox HTTP smoke (`backend/scripts/private_mail_http_smoke.py`) can
mint a session cookie for the same-origin frontend proxy. Use a local mail
directory you can read; do not commit real mailbox exports. Pass
`--print-session-token` only on a trusted machine.

```bash
AUTH_SESSION_HMAC_SECRET="$(grep -E '^AUTH_SESSION_HMAC_SECRET=' .env.mlx | cut -d= -f2-)"
python3 backend/scripts/private_mail_http_smoke.py \
  --mail-dir "$MAIL_DIR" \
  --base-url http://127.0.0.1:3000 \
  --frontend-base-url http://127.0.0.1:3000 \
  --api-base-url http://127.0.0.1:8000 \
  --session-secret "$AUTH_SESSION_HMAC_SECRET" \
  --limit 20 \
  --require-browser-visible \
  --llm-smoke \
  --print-session-token
```
