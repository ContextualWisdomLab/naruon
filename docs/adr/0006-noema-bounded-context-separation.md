# ADR-0006: Noema is two separate Bounded Contexts, not one shared Agent core

**Status:** Accepted (Naruon-local boundary policy)
**Date:** 2026-09-02
**Decision owner:** Naruon maintainers
**Scope:** Naruon's own dependency and reuse boundary toward
`ContextualWisdomLab/.github`'s CI review automation. This ADR records only
what Naruon does and does not consume from `.github`; it cannot assign
authority to, or accept a decision for, `.github` or `contextual-orchestrator`.

## Context

The owner's request for this iteration: "Noema가 Review 뿐만 아니라 소프트웨어
자체는 naruon 에도 기능하는 Agent로서 개발되게 할 것 (DDD)" — Noema should not
exist only as a PR-review CI workflow; its reviewing/analysis capability
should be developed as a reusable Agent that Naruon can also invoke for its
own product needs, per this org's DDD convention
(`docs/product-goal-directive.md` §5: Bounded Context, Ubiquitous Language,
Anti-Corruption Layer, minimal Shared Kernel, Aggregate boundaries recorded in
an ADR).

Two "Noema"s already exist under that name, in two different repositories,
built by different, independently active work:

1. **`.github`'s Noema** (`scripts/ci/noema_review_gate.py`,
   `scripts/ci/noema_review_handoff.py`) is a required PR-review CI check. Its
   actual capability, read end to end for this ADR:
   - `call_llm()` (`noema_review_gate.py:1168`) builds one fixed prompt —
     "You are Noema, an independent pull request reviewer for
     ContextualWisdomLab" — against a diff plus bounded review-thread/changed-file
     context (`build_review_context()`, `noema_review_gate.py:697`), and posts
     it to an OpenAI-compatible endpoint resolved from
     `NOEMA_LLM_API_URL`/`NOEMA_LLM_API_KEY`/`NOEMA_LLM_MODEL` (the
     `contextual-orchestrator` sidecar in CI), with SSRF-hardened URL
     validation (`reject_private_llm_url`, `noema_review_gate.py:1093`).
   - `extract_json_object()` (`noema_review_gate.py:798`) and
     `validate_substantive_verdict()` (`noema_review_gate.py:426`) parse and
     enforce one fixed verdict schema: `decision` (`approve|request_changes|
     comment`), `summary`, `reviewed_lines`, an `adversarial_validation` block
     requiring falsified/confirmed probes at exact changed-diff locations, and
     `findings`.
   - `submit_review()` (`noema_review_gate.py:1415`) and `inspect_and_review()`
     (`noema_review_gate.py:1455`) are pure GitHub CI glue: GraphQL PR fetch,
     diff fetch, dedup-by-marker, and `gh api POST .../pulls/{n}/reviews`.
     `noema_review_handoff.py` (379 lines) is entirely GitHub-side plumbing —
     polling PR reviews, dispatching the workflow, parsing trusted footer
     markers out of review bodies for replay protection. None of it is
     reusable outside a GitHub PR.

   So `.github`'s reusable core, if extracted, would be: **a single-shot
   diff-review verdict generator** — diff + bounded context in, one
   JSON verdict (with line-cited findings and adversarial probes) out, over an
   OpenAI-compatible `contextual-orchestrator` endpoint. It is inherently
   shaped around one diff and one fixed review prompt/schema; it has no tools,
   no multi-turn reasoning loop, and no concept of mail, calendar, or tasks.

2. **Naruon's own Noema** (`backend/services/noema_agent.py`, 609 lines on
   `develop`; registered as `noema-general-agent` in `registered_agents.json`)
   is a `pydantic-ai` (MIT) multi-tool agent that reasons over the tenant's
   own mail, content-graph, and task data, with tools for
   `mail.search`/`mail.read`, `content_graph.query`, `tasks.read`/
   `tasks.update`, and (in active development — see below) calendar
   conflict-checking and opt-in audit-logged writeback via the self-hosted
   runner. It runs on `resolve_runtime_llm_provider()`'s tenant-configured LLM
   provider (Fernet-encrypted per-tenant records), not `.github`'s CI-scoped
   `NOEMA_LLM_API_URL`/`NOEMA_LLM_API_KEY`.

This second Noema is not something this ADR proposes — it already exists on
`develop`, and is under substantial, active, independent development:

- `ContextualWisdomLab/naruon#1486` ("feat(noema-agent): add calendar
  conflict-check tool", 49 commits, last commit 2026-09-01) adds a
  `check_calendar_conflict` tool that reuses Naruon's own deterministic,
  tested `services.calendar_conflict_policy.evaluate_calendar_conflicts`
  (backing `POST /api/calendar/conflicts/evaluate`) as a Noema tool, and
  states explicitly in its description that Naruon's Noema and `.github`'s
  review-bot Noema "are two separate agents that intentionally share only a
  name."
- `ContextualWisdomLab/naruon#1384` ("feat(noema): route LLM through
  contextual-orchestrator", 18 commits, last commit 2026-08-21) is a
  narrower, currently-stalled slice that would route `run_noema_agent`'s
  completions through a tenant-scoped `contextual-orchestrator` gateway
  contract (its own encrypted token and model alias) instead of the
  tenant's directly-configured provider. It does not touch `.github`'s
  review-specific gateway, prompts, or verdict schema either.

Both are open, unmerged, and independently modify `noema_agent.py` and
`registered_agents.json` — they will collide with each other (and both
independently added a `docs/adr/0005-*.md`, colliding with each other and
with this ADR's numbering) whenever either lands first. That collision is
this ADR's one flagged follow-up, not something this ADR resolves.

## Decision

Naruon's Noema does **not** import, vendor, or route through
`.github`'s `scripts/ci/noema_review_gate.py`/`noema_review_handoff.py`, and
will not depend on a future "extracted" package built directly from them.

1. **Two Bounded Contexts, not one Shared Kernel.** `.github`'s Noema is a PR
   diff-review Domain Service in the CI-governance context: one prompt, one
   verdict schema, GitHub as its only I/O. Naruon's Noema is a
   general-purpose workspace-assistant Domain Service in Naruon's own
   product context: multiple tools, tenant-scoped data, a
   `pydantic-ai` agent loop. Forcing them onto one shared "Noema core"
   package would be exactly the monolithic Shared Kernel
   `docs/product-goal-directive.md` §5 says to minimize — the two verdict
   shapes, prompts, and I/O surfaces do not overlap enough to share code
   without one side distorting the other.
2. **What can be shared is the LLM-orchestration gateway, not the agent
   logic** — and even that is intentionally not wired the same way in both
   repos today. `contextual-orchestrator` (`ContextualWisdomLab/
   contextual-orchestrator`) is already its own repository and the org's
   designated shared LLM-orchestration product
   (`docs/product-goal-directive.md` §8-9). `.github`'s Noema calls it
   through a CI-only sidecar credentialed from GitHub Secrets
   (`scripts/ci/contextual_orchestrator_review_sidecar.sh`, fail-closed
   `orchestrator/free` pool). Naruon's Noema, as merged on `develop`, calls
   whatever LLM provider the tenant configured — deliberately never the
   CI-scoped review gateway, so one tenant's workspace data is never sent
   through org-shared review infrastructure. `naruon#1384`'s open, stalled
   proposal to add a *tenant-scoped* `contextual-orchestrator` gateway
   option is a Naruon-side product decision about which upstream providers a
   tenant may pick from; it does not reopen sharing `.github`'s review logic,
   prompts, or credentials, and this ADR takes no position on whether
   `#1384` should land.
3. **No fabricated consumer.** This ADR does not add a new naruon call site
   for `.github`'s review core, because none is needed: Naruon's own,
   already-in-flight Noema work (`#1486`) supplies the actual naruon-side
   need (a calendar-aware workspace assistant) using Naruon's own domain
   logic (`calendar_conflict_policy.py`), not a copy of PR-review code.

## Alternatives rejected

### Extract `noema_review_gate.py`'s `call_llm`/verdict-schema pair into a shared library both repos depend on

Rejected. The extractable core is diff-review-shaped (one diff, one fixed
JSON verdict schema keyed on changed-diff line locations). Naruon's Noema
needs a multi-tool, multi-turn agent over mail/calendar/tasks — adapting the
diff-review schema to that shape would require rewriting most of it, at
which point nothing meaningful is actually shared. The instruction author's
own fallback applies here directly: no genuine Naruon need for this specific
core was found, because Naruon already built (and is actively extending) its
own, better-fitted agent instead.

### Have Naruon's Noema route through `.github`'s CI-scoped `contextual-orchestrator` sidecar

Rejected as a cross-tenant data-boundary violation: that sidecar's KV and
`orchestrator/free` pool are provisioned from GitHub Secrets for CI review
traffic, not for customer workspace data. `naruon#1486`'s description states
this explicitly. A tenant-scoped `contextual-orchestrator` gateway
(`naruon#1384`) is a distinct, still-open question this ADR does not settle.

### Do nothing / record no ADR

Rejected per `docs/product-goal-directive.md`'s own preamble and §5: this
decision — whether to extract a shared Noema core — needed to be made and
recorded durably in the repo, not left as unrecorded reasoning in PR prose
that a future force-push or branch reuse could lose (observed directly in
this investigation: `.github#1437`/`#1438` are closed PRs whose branches were
later force-pushed to unrelated topics, which is exactly the failure mode a
committed ADR avoids).

## Consequences

- `backend/services/noema_agent.py` keeps evolving independently of
  `.github/scripts/ci/noema_review_gate.py`; a reviewer should not expect or
  request code sharing between them on the strength of the shared "Noema"
  name.
- If a genuine cross-repo reuse need is found later, the correct extension
  point is `contextual-orchestrator` itself (already its own repository), not
  either product's Noema module — e.g., a new orchestrator-side capability
  both callers invoke with their own prompts/schemas, never a shared Python
  package imported by both `.github` and Naruon.
- `naruon#1486` and `naruon#1384` both independently add a `docs/adr/0005-*.md`
  file; whichever merges second must renumber against whatever is on
  `develop` at that time, and against this ADR's `0006`.
- This ADR does not authorize, and does not itself implement, `#1384`'s
  tenant-scoped `contextual-orchestrator` gateway option; that remains a
  separate, already-open decision.

## References (APA 7th)

Evans, E. (2003). *Domain-driven design: Tackling complexity in the heart of
software*. Addison-Wesley.

Vernon, V. (2013). *Implementing domain-driven design*. Addison-Wesley.
