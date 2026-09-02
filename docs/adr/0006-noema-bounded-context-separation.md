# ADR-0006: Noema's naruon and `.github` implementations have drifted apart — correcting toward the org's one-shared-runtime design

**Status:** Superseded-on-arrival — see "2026-09-02 correction" below. Kept (not deleted) per this
org's traceability convention: the investigation that produced the original text below is accurate
about the *current code*, and the correction explains why that current code is a drift to fix, not a
boundary to ratify.

**Date:** 2026-09-02 (original text), corrected same day after owner review
**Decision owner:** Naruon maintainers — **correction below overrides the original decision**
**Scope:** Naruon's dependency and reuse boundary toward `ContextualWisdomLab/.github`'s CI review
automation and `ContextualWisdomLab/quarantine-sandbox-runtime`.

## 2026-09-02 correction (read this first)

The original version of this ADR (below, kept verbatim for the record) concluded that `.github`'s
Noema and Naruon's Noema are "two separate Bounded Contexts... intentionally shar[ing] only a name,"
and recommended never sharing code between them. **That conclusion is wrong and is hereby withdrawn.**
It was reached by reading only the *current code* in both repos and never checking this org's
canonical architecture document, which is unambiguous on original intent:

> `docs/CWL-MASTER-CONTEXT.md` (ContextualWisdomLab/.github), §3, line 36: **"noema — agent runtime
> (Pydantic-AI / Codex-Python): a GitHub Review Agent in CI + a do-anything agent inside naruon + the
> lightweight quarantine sandbox."**
>
> Same file, §"Reading it" (line 230): **"`noema` is the shared agent runtime + quarantine sandbox
> (used by naruon, the GitHub review agent, and wardnet's AI SOC)."**

This is the org's standing, canonical architecture statement, not a proposal — Noema was designed from
the start to be **one shared agent runtime** with three consumers (`.github`'s CI review, naruon's
general-purpose workspace agent, wardnet's AI SOC artifact analysis), built on Pydantic-AI, and
including the quarantine sandbox (the `ContextualWisdomLab/quarantine-sandbox-runtime` repository) as
a first-class shared capability, not a bolt-on integration task separate from "Noema" itself.

What the original investigation below got right, and what remains true: `.github`'s
`noema_review_gate.py` core (`call_llm`/verdict-schema) is diff-review-shaped and cannot be adapted to
naruon's mail/calendar/task tool-use shape by simple code sharing, and naruon's `noema_agent.py`
(`backend/services/noema_agent.py`) is a real, independently useful `pydantic-ai` agent already in
active development (`naruon#1486`, `naruon#1384`). **The fix is not to force today's two divergent
implementations into one file** — it's to design the actual shared runtime the master context
describes (a common Pydantic-AI-based Noema core + quarantine-sandbox capability that both the CI
review path and naruon's agent path build on, per `docs/product-goal-directive.md` §5's Anti-Corruption
Layer / minimal-Shared-Kernel DDD convention — shared where it's genuinely the same capability,
per-context where the domain logic genuinely differs) rather than accept permanent divergence.

Concretely, until the real design lands: **do not cite this ADR's original "intentionally separate,
never share" framing as settled architecture.** The correct current status is "drifted apart from the
intended shared-runtime design; a corrected design is in progress" — see the follow-up work tracked
from this correction (check `docs/product-technical-gap-baseline.md` in `ContextualWisdomLab/.github`
and this repo's own issue tracker for the current state of that follow-up before assuming either
"still separate" or "already unified").

The naruon#1486/#1384 code-sharing analysis, and the `#1437`/`#1438` force-push/branch-reuse traceability
lesson below, remain valid observations and are not being retracted — only the "therefore, keep them
permanently separate" conclusion is.

---

## Original text (2026-09-02, superseded above)

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
  name." **(2026-09-02 correction above: that framing is not this org's
  actual design intent — see `docs/CWL-MASTER-CONTEXT.md`.)**
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

## Decision (superseded — see correction above)

~~Naruon's Noema does **not** import, vendor, or route through
`.github`'s `scripts/ci/noema_review_gate.py`/`noema_review_handoff.py`, and
will not depend on a future "extracted" package built directly from them.~~

This decision is withdrawn per the 2026-09-02 correction above. The actual
decision — how the shared Pydantic-AI Noema runtime + quarantine sandbox
described in `docs/CWL-MASTER-CONTEXT.md` should be designed so it serves
`.github`'s diff-review shape, naruon's multi-tool workspace-agent shape, and
wardnet's AI SOC shape without a monolithic Shared Kernel — is tracked as
follow-up work, not settled by this ADR.

## Alternatives rejected (context for the withdrawn decision — not current guidance)

### Extract `noema_review_gate.py`'s `call_llm`/verdict-schema pair into a shared library both repos depend on

This was rejected in the original analysis on the grounds that the extractable core is diff-review-shaped
and naruon's need is multi-tool. That specific code-sharing shape is still probably wrong (see
correction above) — but "no shared runtime should exist at all" does not follow from it, and is not
this ADR's position after correction.

### Have Naruon's Noema route through `.github`'s CI-scoped `contextual-orchestrator` sidecar

Rejected as a cross-tenant data-boundary violation: that sidecar's KV and
`orchestrator/free` pool are provisioned from GitHub Secrets for CI review
traffic, not for customer workspace data. `naruon#1486`'s description states
this explicitly. A tenant-scoped `contextual-orchestrator` gateway
(`naruon#1384`) is a distinct, still-open question this ADR does not settle.
This specific rejection (CI-scoped credentials should not carry tenant
workspace traffic) is unaffected by the correction above and remains valid.

### Do nothing / record no ADR

Rejected per `docs/product-goal-directive.md`'s own preamble and §5: this
decision needed to be made and recorded durably in the repo, not left as
unrecorded reasoning in PR prose that a future force-push or branch reuse
could lose (observed directly in this investigation: `.github#1437`/`#1438`
are closed PRs whose branches were later force-pushed to unrelated topics,
which is exactly the failure mode a committed ADR avoids). This observation
motivates writing the *correction* durably here too, rather than only in
chat.

## Consequences

- The original "keep permanently separate" consequences listed here are
  withdrawn. Do not cite them.
- The real follow-up: design the shared Pydantic-AI Noema runtime +
  quarantine-sandbox capability `docs/CWL-MASTER-CONTEXT.md` describes, using
  `contextual-orchestrator` as the shared LLM-orchestration layer underneath
  it (per `docs/product-goal-directive.md` §8-9), with `.github`'s diff-review
  logic and naruon's multi-tool agent logic as two callers of that shared
  core rather than either being rewritten to imitate the other.
- `naruon#1486` and `naruon#1384` both independently add a `docs/adr/0005-*.md`
  file; whichever merges second must renumber against whatever is on
  `develop` at that time, and against this ADR's `0006`. This collision risk
  is unaffected by the correction and still needs resolving.
- `naruon#1486`'s PR description text asserting permanent separation should
  be corrected or annotated to point at this ADR's correction before that PR
  merges, so the wrong framing doesn't become the merged historical record.

## References (APA 7th)

Evans, E. (2003). *Domain-driven design: Tackling complexity in the heart of
software*. Addison-Wesley.

Vernon, V. (2013). *Implementing domain-driven design*. Addison-Wesley.
