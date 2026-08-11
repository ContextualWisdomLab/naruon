# ADR-0001: Local LLM and contextual-orchestrator boundary

- Status: Accepted
- Date: 2026-08-11

## Context

Naruon must run on macOS with Colima while retaining a portable Docker Compose
fallback. The host already exposes `mlx-lm`; `llama.cpp` is the next local
runtime, and the existing Compose Ollama service remains the final fallback.
Naruon already has OpenAI-compatible provider validation, project-graph LLM
extraction, and a contextual-orchestrator batch-embedding seam. MLX chat and
EmbeddingGemma may be separate local OpenAI-compatible endpoints.

## Decision

1. On macOS, `scripts/naruon_compose.sh` probes `/v1/models` in this order:
   `mlx-lm`, `llama.cpp`, then Ollama. `NARUON_COMPOSE_LLM_RUNTIME` can select
   one explicitly.
2. `mlx-lm` is the preferred chat runtime. EmbeddingGemma remains the preferred
   embedding model. When `OPENAI_EMBEDDING_BASE_URL` is configured for the
   local-environment provider, search and import use that separate endpoint;
   otherwise an embedding-capable `llama.cpp` or contextual-orchestrator
   endpoint must be configured for real vectors because the installed MLX
   server exposes chat completions but not `/v1/embeddings`. Local structured,
   translation, and draft calls pass MLX's `enable_thinking=false` template
   argument so reasoning tokens cannot exhaust the response before content.
   Import paths retain Naruon's existing zero-vector fallback.
3. Integration with contextual-orchestrator uses the existing OpenAI-compatible
   base-URL/provider seam and the existing batch embedding contract. No bespoke
   client or duplicate routing layer is added.
4. Every host-provider URL remains subject to the existing SSRF guard and
   explicit `host.docker.internal` allowlist entry.
5. In local Compose only, when `ALLOW_LOCAL_LLM_PROVIDERS` is enabled and the
   configured base URL resolves to an allowlisted local host, the explicit
   process-level host runtime takes precedence over a tenant API-key row. This
   prevents a tenant secret from being sent to a local server. An active DB
   provider remains authoritative, and external base URLs retain tenant
   configuration behavior.
6. `llmfit` selects the device-appropriate EmbeddingGemma candidate before
   installation. The official `ggml-org/embeddinggemma-300M-GGUF` artifact is
   cached through llama.cpp for an embedding-capable endpoint; an
   embedding-only server is not treated as a chat fallback. The macOS
   `homebrew.mxcl.naruon-embeddinggemma` LaunchAgent serves the verified local
   model on port 8082 when installed, and the Compose wrapper auto-detects it.
7. The separate embedding base URL is a local-environment setting only. It is
   never copied onto a tenant-configured external provider or an organization
   DB provider, preventing an external tenant API key from being sent to a
   local endpoint.

## Consequences

- The normal macOS stack starts without building the large Ollama image.
- Ollama remains available with `NARUON_COMPOSE_LLM_RUNTIME=ollama`.
- Embedding quality is explicit: EmbeddingGemma is preferred, but a chat-only
  MLX endpoint does not silently pretend to provide embeddings.
- A local MLX chat server and local llama.cpp embedding server can run
  concurrently without sharing a port or crossing tenant provider boundaries.
