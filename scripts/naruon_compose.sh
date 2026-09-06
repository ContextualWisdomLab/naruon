#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -n "${NARUON_ENV_FILE:-}" ]; then
  env_file="${NARUON_ENV_FILE}"
elif [ -f "${HOME}/.env" ]; then
  env_file="${HOME}/.env"
else
  env_file=".env"
fi

if [ ! -f "${env_file}" ]; then
  cat >&2 <<EOF
Error: Naruon compose env file not found: ${env_file}
Set NARUON_ENV_FILE=/path/to/env or create ${HOME}/.env.
EOF
  exit 1
fi

llm_runtime="${NARUON_COMPOSE_LLM_RUNTIME:-auto}"

host_llm_endpoint_ready() {
  curl -fsS --max-time "${NARUON_LLM_PROBE_TIMEOUT_SECONDS:-1}" \
    "${1%/}/models" >/dev/null 2>&1
}

host_embedding_endpoint_ready() {
  curl -fsS --max-time "${NARUON_LLM_PROBE_TIMEOUT_SECONDS:-1}" \
    -H "Authorization: Bearer ${NARUON_HOST_LLM_API_KEY:-mlx}" \
    -H 'Content-Type: application/json' \
    -d '{"model":"embeddinggemma","input":["embedding probe"]}' \
    "${1%/}/embeddings" >/dev/null 2>&1
}

container_host_url() {
  case "$1" in
    http://127.0.0.1:*) printf 'http://host.docker.internal:%s\n' "${1#http://127.0.0.1:}" ;;
    http://localhost:*) printf 'http://host.docker.internal:%s\n' "${1#http://localhost:}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

if [ "${llm_runtime}" = "auto" ]; then
  llm_runtime="ollama"
  if [ "$(uname -s)" = "Darwin" ]; then
    if host_llm_endpoint_ready "${NARUON_MLX_BASE_URL:-http://127.0.0.1:8080/v1}"; then
      llm_runtime="mlx"
    elif host_llm_endpoint_ready "${NARUON_LLAMA_CPP_BASE_URL:-http://127.0.0.1:8081/v1}"; then
      llm_runtime="llama.cpp"
    fi
  fi
fi

case "${llm_runtime}" in
  ollama)
    compose_files=()
    ;;
  mlx|llama.cpp)
    if [ "${llm_runtime}" = "mlx" ]; then
      host_llm_base_url="${NARUON_MLX_BASE_URL:-http://host.docker.internal:8080/v1}"
      NARUON_HOST_LLM_BASE_URL="$(container_host_url "${host_llm_base_url}")" || exit 1
      export NARUON_HOST_LLM_BASE_URL
      export NARUON_HOST_LLM_ALLOWED_HOSTS="${NARUON_MLX_ALLOWED_LLM_BASE_URL_HOSTS:-host.docker.internal}"
      # mlx-lm serves chat completions but not /v1/embeddings. A local
      # placeholder key enables chat while embedding paths retain the
      # zero-vector fallback unless an embedding-capable endpoint is configured.
      export NARUON_HOST_LLM_API_KEY="${NARUON_MLX_OPENAI_API_KEY:-mlx}"
      export NARUON_HOST_LLM_EMBEDDING_MODEL="${NARUON_MLX_EMBEDDING_MODEL:-embeddinggemma}"
      export NARUON_HOST_LLM_MODEL="${NARUON_MLX_LLM_MODEL:-mlx-community/gemma-4-e4b-it-4bit}"
    else
      host_llm_base_url="${NARUON_LLAMA_CPP_BASE_URL:-http://host.docker.internal:8081/v1}"
      NARUON_HOST_LLM_BASE_URL="$(container_host_url "${host_llm_base_url}")" || exit 1
      export NARUON_HOST_LLM_BASE_URL
      export NARUON_HOST_LLM_ALLOWED_HOSTS="${NARUON_LLAMA_CPP_ALLOWED_LLM_BASE_URL_HOSTS:-host.docker.internal}"
      export NARUON_HOST_LLM_API_KEY="${NARUON_LLAMA_CPP_API_KEY:-llama.cpp}"
      export NARUON_HOST_LLM_EMBEDDING_MODEL="${NARUON_LLAMA_CPP_EMBEDDING_MODEL:-embeddinggemma}"
      export NARUON_HOST_LLM_MODEL="${NARUON_LLAMA_CPP_LLM_MODEL:-gemma4:e2b-it-qat}"
    fi
    embedding_base_url="${NARUON_HOST_LLM_EMBEDDING_BASE_URL:-}"
    if [ -z "${embedding_base_url}" ]; then
      if [ "${llm_runtime}" = "mlx" ]; then
        embedding_base_url="${NARUON_MLX_EMBEDDING_BASE_URL:-}"
      else
        embedding_base_url="${NARUON_LLAMA_CPP_EMBEDDING_BASE_URL:-}"
      fi
    fi
    if [ -z "${embedding_base_url}" ]; then
      embedding_probe_url="${NARUON_LLAMA_CPP_EMBEDDING_BASE_URL:-http://127.0.0.1:8082/v1}"
      if host_embedding_endpoint_ready "${embedding_probe_url}"; then
        embedding_base_url="${embedding_probe_url}"
      fi
    fi
    if [ -n "${embedding_base_url}" ]; then
      NARUON_HOST_LLM_EMBEDDING_BASE_URL="$(container_host_url "${embedding_base_url}")" || exit 1
      export NARUON_HOST_LLM_EMBEDDING_BASE_URL
    fi
    compose_files=(
      --file "${repo_root}/docker-compose.yml"
      --file "${repo_root}/docker-compose.macos.yml"
    )
    ;;
  *)
    echo "Error: NARUON_COMPOSE_LLM_RUNTIME must be auto, ollama, mlx, or llama.cpp" >&2
    exit 1
    ;;
esac

for arg in "$@"; do
  if [ "${arg}" = "--env-file" ]; then
    exec docker compose "${compose_files[@]}" "$@"
  fi
done

exec docker compose --env-file "${env_file}" "${compose_files[@]}" "$@"
