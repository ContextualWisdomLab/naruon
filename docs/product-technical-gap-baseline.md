# Product & Technical Gap Baseline

> Evidence date: 2026-08-21. This file distinguishes protected-branch product
> truth, open-PR implementation, and planned integration. Queued, stale-head,
> draft-only, or model-only evidence is not treated as shipped capability.

## 1. Protected baseline and delivery load

- Protected integration branch observed at
  `develop@81c105645ca6e680f5f8c15ba9c33b67eb63c48b` before this branch.
- The repository had 94 open pull requests when this baseline was refreshed.
  That count is a delivery-risk observation, not a product metric; refetch before
  using it for action.
- Protected `develop` enforces backend, frontend, security, CodeQL, dependency,
  supply-chain, image, coverage, Strix, and OpenCode review contexts. Exact-head
  required workflow and independent approval evidence remain mandatory.
- Current branch:
  `feat/lineageweave-calendar-projection-provider-contract`, created directly
  from the protected baseline above. It is not protected-branch product truth.

## 2. Current product authority

Naruon is the customer-owned communication and workspace control plane. It owns:

```text
mail/calendar/contact/file provider access
canonical source and message identity
workspace/tenant authorization
provider write intent and runner dispatch
retry/reconciliation evidence
project/task/commitment records owned by Naruon
```

It does not transfer provider credentials, browser sessions, or application
SQL authority to LineageWeave or other CWL products.

## 3. LineageWeave integration tracks

### 3.1 Email and project lineage

- Naruon issue #1437 defines the future consumer boundary.
- LineageWeave PR #343 publishes the provider-side external lineage analysis
  package contract: bounded opaque evidence, `available_at <= knowledge_cutoff`,
  observed/inferred/proposed truth separation, deterministic digests, and no
  Naruon DB or provider access.
- Naruon runtime consumption is still **disabled and unimplemented**.

Required Naruon consumer work remains:

1. canonical email/thread identity and provenance from issue #1350;
2. explicit admission policy so unrelated/private mail is never submitted;
3. durable idempotent external analysis jobs with timeout/cancellation/retry;
4. immutable LineageWeave artifact and schema pin;
5. normalized result/candidate/decision projection;
6. accept/correct/reject/supersede audit without provider mutation;
7. integration into existing email/thread/project surfaces rather than a second
   product UI;
8. outage/degraded behavior that leaves normal mail/project operation usable.

### 3.2 Calendar projection

- The inherited LineageWeave PR #337 was closed without merge because it carried
  obsolete Buyer-stack ancestry.
- LineageWeave PR #355 reconstructs the strict consumer contract on current
  protected `main`, including 366-day/200-row/1 MiB bounds and exact response
  media-type validation.
- This Naruon branch implements the provider-side schema, exact service audience,
  route, and fail-closed provider port.
- `backend/services/caldav_service.py` still states that inbound CalDAV import is
  not configured. Therefore the production provider intentionally returns
  `503 calendar_projection_unavailable`; no event observation is fabricated.

Remaining activation work:

```text
real inbound provider adapter
→ normalized occurrence/read model
→ recurrence/timezone/provider revision evidence
→ tenant/source disclosure policy
→ retry and reconciliation receipts
→ immutable provider/consumer conformance fixture
→ LineageWeave fail-closed runtime wiring
```

## 4. Product gaps with highest customer impact

### 4.1 Canonical communication evidence

Issue #1350 remains the primary evidence-workspace gap. Product completion
requires canonical email message/instance/thread identities, duplicate review,
RFC reply evidence, attachment and embedded-media provenance, correction UX,
and action audit. Semantic lineage must not replace provider-observed thread
facts.

### 4.2 Inbound calendar truth

Naruon has CalDAV writeback intent and runner dispatch, but not a production
inbound event feed. A calendar projection endpoint without a normalized event
read model is only a versioned contract. The product must preserve:

- provider/source/occurrence identity;
- recurrence and timezone semantics;
- provider revisions and observation time;
- sync cursor and reconciliation receipts inside Naruon;
- disclosure policy before cross-service projection;
- absence/unavailable state rather than synthetic empty success.

### 4.3 Project intelligence adoption

LineageWeave results can propose related history and project associations. Naruon
must preserve its own authoritative project/task/commitment state and require a
versioned deterministic or human decision before adopting a proposed relation.
The original analysis artifact and evidence references must remain auditable.

### 4.4 Delivery queue and release evidence

A large open-PR queue raises stale-base, repeated-check, reviewer-capacity, and
conflicting-contract risk. Priority should remain:

```text
review current exact head
→ fix actionable findings
→ rerun required checks
→ obtain independent approval
→ merge normally
→ remove superseded PRs
```

No repository-local duplicate scheduler should be added when the central CWL
scheduler already owns review/repair/merge sweeps.

## 5. Database and service constraints

Any future persistence added for external analysis or calendar projection must:

- use descriptive two-or-more-word `snake_case` object names;
- remain in third normal form for authoritative state;
- partition/index tenant/time workloads to avoid hot partitions;
- keep provider credentials outside analytical result tables;
- use append-only decision/audit evidence for accepted/rejected/corrected facts;
- prohibit direct cross-repository SQL and shared ORM models;
- preserve exact source/provider revision and knowledge-cutoff identity.

## 6. Acceptance evidence required before activation

### Calendar provider/consumer

- provider and consumer schemas are byte-for-byte or semantically conformance-
  tested from immutable released artifacts;
- wrong audience, wrong scope, ambiguous signing key, missing OIDC, and browser
  user tokens fail closed;
- invalid windows/cursors and over-limit pages fail before provider work;
- provider unavailable returns explicit 503 and does not affect internal tasks or
  commitments;
- external event observations remain `observed` and never create provider or
  LineageWeave mutations;
- exact-head coverage, docstrings, security checks, and independent approval pass
  in both repositories.

### External lineage consumer

- unauthorized/private evidence appears in no request, cache, log, metric, or
  fixture;
- RFC/provider thread facts remain distinct from inferred semantic relations;
- duplicate delivery creates one logical analysis and projection;
- later-available evidence cannot enter a historical cutoff run;
- LineageWeave outage does not block normal Naruon work;
- accept/correct/reject decisions preserve original artifact identity;
- immutable package/service compatibility tests fail on schema/version drift.

## 7. Current next actions

1. Complete exact-head tests and review for LineageWeave PR #343.
2. Complete exact-head tests and review for LineageWeave PR #355.
3. Complete this Naruon provider-contract PR without claiming inbound data.
4. Merge/release the immutable contracts normally.
5. Stabilize issue #1350 canonical email identity before implementing Naruon
   external lineage admission and result projection.
6. Implement inbound calendar synchronization/read model as a separate Naruon
   slice, then activate provider/consumer wiring only after conformance evidence.

## 8. Product truth

This baseline does **not** claim that Naruon currently sends email evidence to
LineageWeave or that LineageWeave currently receives real Naruon calendar events.
It records the contracts and exact remaining steps needed to make those future
integrations safe, independently deployable, and buyer-visible.
