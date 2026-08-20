# Noema orchestrator routing

Status: first slice implemented. `run_noema_agent` sends completions only to
contextual-orchestrator. Catalog files stay catalog-only. A Decision Points
/ `mail.triage` dispatcher is a later slice and is not in this change.

The runnable contract lives in
[`backend/services/noema_agent.py`](../../backend/services/noema_agent.py) and
[`backend/services/orchestrator_gateway.py`](../../backend/services/orchestrator_gateway.py).

## Problem

naruon already registered a Noema stub (`registered_agents.json` →
`run_noema_agent`) that called the tenant LLM provider directly through
`resolve_runtime_llm_provider`. That path used a tenant `OpenAIChatModel`
(default `gpt-4o`) and left model choice inside naruon. The owner
requirement is the opposite: **model selection must go through
contextual-orchestrator**.

`run_noema_agent` has no production callers. `registered_agents.json` and
`task_agent_mapping.json` are catalog only. Wiring Decision Points first
would lock the wrong picker.

## Design

naruon is a consumer. It does not reimplement the orchestrator catalog, Fugu /
Conductor / TRINITY selection, or list-price bookkeeping for free-but-priced
models. Those stay in ContextualWisdomLab/contextual-orchestrator.

Noema sends one OpenAI-compatible chat request to:

* a dedicated gateway inference token from the Fernet tenant KV
  (`tenant_configs.noema_orchestrator_token`)
* an HTTPS base URL that ends in `/v1`
  (`tenant_configs.noema_orchestrator_base_url`)
* the single model alias `contextual-orchestrator`

There is no sequential model list and no fail-over to the next agent or
provider inside naruon. Missing or rejected gateway config fails closed with
`error_code=orchestrator_gateway_unavailable`.

This slice does **not** copy draft email-writing clients that still require a
tenant `model_profile_id`. Keep the existing tools, owner-scope, and opt-in
writeback surface.

The setup contract is [`ADR-0005`](../adr/0005-signed-noema-gateway-settings.md):
`GET` and `PUT /api/noema-gateway` use the signed session's current owner scope,
validate the HTTPS allowlist, persist the token through Fernet, and return only
readiness metadata. Mailbox self-service fields and cross-user administration
are intentionally outside this route.

Upstream org secrets (`NVIDIA_NIM_API_KEY`, `NVIDIA_NIM_API_KEY_SUB`,
`BYTEZ_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY`) belong in the
orchestrator KV. naruon must not read them at request time. GitHub Models and
`COPILOT_GITHUB_TOKEN` are never a Noema path. OpenCode sidecar model lists
are not copied here.

## Grounding

Cost-aware routing belongs in a dedicated gateway, not in each caller
(Chen et al., 2023; Ong et al., 2024; Ding et al., 2024). naruon therefore
submits a single alias and lets contextual-orchestrator choose.

## References

Chen, L., Zaharia, M., & Zou, J. (2023). *FrugalGPT: How to use large language
models while reducing cost and improving performance*. arXiv.
https://doi.org/10.48550/arXiv.2305.05176

Ding, D., Mallick, A., Wang, C., Sim, R., Mukherjee, S., Rühle, V.,
Lakshmanan, L. V. S., & Awadallah, A. H. (2024). *Hybrid LLM: Cost-efficient
and quality-aware query routing*. arXiv.
https://doi.org/10.48550/arXiv.2404.14618

Ong, I., Almahairi, A., Wu, V., Chiang, W.-L., Wu, T., Gonzalez, J. E.,
Kadous, M. W., & Stoica, I. (2024). *RouteLLM: Learning to route LLMs with
preference data*. arXiv. https://doi.org/10.48550/arXiv.2406.18665
