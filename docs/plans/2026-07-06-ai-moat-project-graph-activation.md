# AI Moat: Activate the Project Semantic Graph Pipeline

> **For agentic workers:** use the repo's RED/GREEN discipline. Phase 1 is a
> behavior change on the import path (it starts writing project-graph rows), so
> land it test-first and owner-scoped, behind a flag, and off the synchronous
> import critical path.

**Status:** Proposal (evidence-backed). Not yet implemented.

## Why this is the highest-leverage AI work

A defensible AI advantage is the single biggest thing missing for a top-tier
valuation. Today the "AI" is mostly single-shot OpenAI calls plus keyword/regex
heuristics — copyable in a week. The **one** place with a genuine *data-moat*
path (per-tenant, human-corrected knowledge graph over the customer's own email)
already exists in the schema and API **but is not running**.

## Current state (code-verified)

- **The substrate IS built and wired.** Every email import parses content into a
  node/segment tree and persists `ContentSegmentRecord` rows:
  `email_import_service.py:25` imports `parse_content`, and
  `email_import_service.py:307` calls `_append_email_content_graph(...)`. So
  content-addressed segments accumulate per tenant on every import.
- **The extraction step is DEAD CODE.** `extract_project_semantics`
  (`services/project_graph/extractors.py:227`) and
  `persist_project_graph_projection` (`services/project_graph/projection.py:11`)
  have **zero non-test callers** (full-tree grep). Nothing turns segments into
  `project_graph_objects`.
- **The read + feedback surfaces already assume it runs.** `api/projects.py`
  serves `/candidates` from `list_project_candidates` and exposes traceability;
  `apply_project_graph_correction` (`projection.py:30`) + `repository.apply_correction`
  capture human corrections. These query/annotate tables that **nothing outside
  test fixtures populates**.
- **The extractor is not ML.** `extract_project_semantics` is a deterministic
  bilingual keyword table (`_RULES`) with a linear `_confidence`
  (`extractors.py`). Good as a v0 baseline, not a moat by itself.

Net: a wired substrate + read/feedback APIs, with an unfilled schema in the
middle. Filling it — and upgrading how it's filled — is the moat.

## Design

### Phase 1 — Activate the pipeline (turn dead code live)
Call the existing extract→persist step so `project_graph_objects` actually get
populated and `/candidates` returns real data.

- Insertion point: `email_import_service.py`, right after
  `_append_email_content_graph(...)` (line 307), where the parsed segments for
  the email already exist.
- Run `extract_project_semantics` over the email's `ContentSegmentRecord`s, then
  `persist_project_graph_projection(session, ...)` with the same owner scope
  (`user_id`/`organization_id`/`workspace_id`) the rest of the import uses.
- **Off the critical path:** do not block synchronous import on extraction —
  enqueue it (reuse the existing worker/queue pattern) or run it in a
  post-commit task. Import latency and reliability must not regress.
- **Flag it:** gate behind an owner-scoped/config flag so it can roll out per
  tenant and be disabled instantly.
- Ships the keyword baseline: crude but real candidates, and it makes the
  projects surfaces honest (they stop reading an empty store).

### Phase 2 — Upgrade extraction from keywords to grounded LLM/embedding
Replace the `_RULES` keyword matcher with an extraction step that consumes the
same `ContentSegmentRecord`s and emits `ProjectSemanticObject`s with
`source_segment_uids` citations (already in the model — `extractors.py:287`).

- Ground every extracted object/edge in cited segments (no citation → drop).
- Reuse the SSRF-hardened provider gateway (`llm_provider_urls.py`) and
  tenant-scoped provider selection; no business-logic/domain-policy fabrication.
- Keep the keyword extractor as a cheap fallback and a regression baseline.

### Phase 3 — Close the feedback loop → the actual moat
`apply_project_graph_correction` already records human corrections
(before/after JSON, actor, rationale). Turn that into an asset:

- Build a per-tenant eval set from corrections (accepted / rejected / edited).
- Add a **calibrated** confidence: verify extracted objects against their cited
  segments instead of trusting the model's self-reported number, and calibrate
  against corrections.
- Stand up an eval harness (there is none today; `ai_hub` `readiness_score`
  counts prompts/providers, it does not measure extraction quality). A
  proprietary, human-corrected email→graph eval set is the measurement moat.

## Guardrails / non-goals
- Strict owner scoping on every write (mirror existing import scoping).
- No fabricated domain copy/policy — cited-segment-backed objects only; unknown
  → TBD/Review, never invented.
- Cost + rate controls on Phase 2 LLM calls; batch per import, cap per tenant.
- Extraction must be idempotent per `object_uid` so re-imports don't duplicate.

## Tasks
- [ ] RED: `@pytest.mark.postgres` test — import an email, assert
  `project_graph_objects` rows are created with correct owner scope and
  `source_segment_uids` pointing at real segments. Fails today (nothing populates).
- [ ] Phase 1: wire extract→persist after `_append_email_content_graph`, async +
  owner-scoped + flagged; keep import latency unchanged (assert in test).
- [ ] GREEN: candidates endpoint returns activated objects for the tenant.
- [ ] Phase 2 (separate PR): grounded LLM/embedding extractor with segment
  citations; keyword fallback; eval vs. a small labeled set.
- [ ] Phase 3 (separate PR): corrections→eval-set + calibrated confidence +
  eval harness.

## Why now
This converts an existing, paid-for substrate (segments persisted on every
import) into the one capability here that compounds with proprietary data and
human feedback. It is the difference between "we call OpenAI" and "a per-tenant
knowledge graph over your email that gets better as your team corrects it."
