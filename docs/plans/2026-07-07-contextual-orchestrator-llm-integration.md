# Contextual Orchestrator LLM integration (naruon)

**Goal:** route naruon's LLM calls through Contextual Orchestrator
(`ContextualWisdomLab/contextual-orchestrator`) so model selection, fallback,
and verification are centralized, and the OpenAI API key lives once in the org
Secrets on the orchestrator — not sprinkled per naruon tenant.

## Key fact: it's an OpenAI-compatible gateway
Contextual Orchestrator exposes **`POST /v1/chat/completions`** (server.py) with
the standard `model` / `messages` / `stream` body plus orchestration extras
(`orchestration`, `orchestration_mode`, `mode`, `include_orchestration_trace`).
Internally it routes across configured **agent pools** (model groups) with
fallback + verifier logic (`route_once` / `complete` / `_invoke`).

Because it is **OpenAI-wire-compatible**, naruon needs **almost no new code** —
naruon already speaks OpenAI-compatible base URLs (`OPENAI_BASE_URL`,
`LLMProvider.base_url`, `build_llm_provider_http_client`). This is a
config-level integration, not a bespoke client (unlike clearfolio/codec-carver).

## Integration (config-first)
1. **Point base_url at the orchestrator:** set the naruon LLM provider's
   `base_url` (or `OPENAI_BASE_URL`) to `https://<orchestrator>/v1`. The
   orchestrator holds the org OpenAI key and does the routing.
2. **Allowlist the host:** add the orchestrator host to
   `ALLOWED_LLM_BASE_URL_HOSTS` so naruon's SSRF-safe
   `build_llm_provider_http_client` accepts it.
3. **(Optional) orchestration passthrough:** to use routing modes, naruon can
   send the extra body keys (`orchestration_mode`, `mode`). Only worth a small
   client tweak if naruon wants to steer routing per call; otherwise the default
   policy applies and no naruon code changes at all.

## Why this is the lazy-correct shape
- No new client module, no new job/poll flow — the existing OpenAI client path
  carries it. Fewer moving parts than a bespoke integration.
- Key hygiene: the OpenAI key stays in the orchestrator (org Secrets), naruon
  holds none. Model/provider changes happen centrally in the orchestrator's
  agent pools without redeploying naruon.

## Slices
1. **Config + allowlist** — document + wire `ALLOWED_LLM_BASE_URL_HOSTS` +
   provider base_url pointing at the orchestrator; verify an existing naruon LLM
   path (search embedding / RAG answer) works unchanged through it.
2. **(Optional) orchestration hints** — a thin extra-body passthrough so naruon
   can request a routing `mode` per call, if wanted.

## Cross-repo note
Same org-central CI gate as the other repos (opencode/trivy) → `.github#323`
unblocks its merge queue too. Its PR #41 already adds a Clearfolio viewer
integration on the orchestrator side — the two integrations converge.
