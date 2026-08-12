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
8. Import embedding inputs are the existing content-graph parser's semantic
   segments: headings, paragraphs, sections, and structured fields. A segment's
   `heading_path` is prefixed to non-heading text so the embedding retains its
   ontology context without merging unrelated segments.
9. The physical provider limit is a safety boundary, not the semantic chunking
   policy. Only an oversized semantic segment is further split by the shared
   boundary-aware embedding splitter, with no overlap, before it reaches a
   provider. The current local EmbeddingGemma/llama.cpp contract uses a
   conservative 256-character request ceiling because the runtime's physical
   token batch limit is lower than the length of some real mail bodies and
   attachments.
10. The existing `Email.embedding` and `Attachment.embedding` columns remain
    source-level compatibility vectors. Import mean-pools segment embeddings
    into one centroid per email or attachment, while the persisted content
    segments remain the authoritative Ontology/Project Graph citation units.
    Segment-level dense retrieval is explicitly out of scope until it has a
    separate schema and retrieval decision.

### Non-goals

- Do not use a fixed character window as the primary semantic unit.
- Do not add a segment-vector column or change dense-search result identity in
  this incident fix.

### Implementation plan

- Reuse `services.content_graph.parse_content` in
  `services.email_import_service` to build the embedding inputs and graph
  records from the same `ParseResult`.
- Keep `services.embedding.generate_embeddings` as the provider safety boundary
  for oversized individual semantic segments and retain the existing
  contextual-orchestrator batch seam.
- Mean-pool segment vectors back to the existing source-level vector columns.

### Verification

- [x] Regression test proves heading context is preserved and semantic
  segments are sent separately before source pooling.
- [x] Regression test proves oversized provider inputs remain below the local
  physical request ceiling.
- [ ] Live mail import proves source visibility, search visibility, and zero
  residual advisory locks after the semantic-input change.

## Consequences

- The normal macOS stack starts without building the large Ollama image.
- Ollama remains available with `NARUON_COMPOSE_LLM_RUNTIME=ollama`.
- Embedding quality is explicit: EmbeddingGemma is preferred, but a chat-only
  MLX endpoint does not silently pretend to provide embeddings.
- A local MLX chat server and local llama.cpp embedding server can run
  concurrently without sharing a port or crossing tenant provider boundaries.
- Real mail bodies larger than the local embedding context remain importable;
  retrieval keeps one fitted source centroid per email/attachment instead of
  exposing a provider context error to the import API, while Ontology and
  Project Graph processing continues to see the original cited segments.

## References

- Henrique Schechter Vera et al., [“EmbeddingGemma: Powerful and Lightweight
  Text Representations”](https://arxiv.org/abs/2509.20354), arXiv:2509.20354
  (2025). The paper reports a 300M embedding model evaluated across multilingual,
  English, and code tasks, including quantized and truncated variants; that
  supports EmbeddingGemma as a low-memory embedding candidate, not as a chat
  runtime.
- Niklas Muennighoff et al., [“MTEB: Massive Text Embedding
  Benchmark”](https://arxiv.org/abs/2210.07316), arXiv:2210.07316 (2023).
  MTEB spans multiple tasks, datasets, and languages and finds no universal
  embedding method; this supports measuring the selected local model in
  Naruon's retrieval workload instead of assuming that a chat model is a good
  embedder.

The source PDFs are not bundled because redistribution rights were not
established; stable links and summaries are provided instead.
