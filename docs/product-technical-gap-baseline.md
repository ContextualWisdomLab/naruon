# Naruon Product and Technical Gap Baseline

**Baseline version:** 0.1  
**Observed on:** 2026-08-20 (Asia/Seoul)  
**Observed protected branch:** `develop@c9bfba2dc2063b82741686a3b3120a66c269ab27`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)

This document defines the evidence-backed boundary between what Naruon currently
ships on protected `develop`, what is present only in open pull requests, what is
still a product-plan aspiration, and what a buyer must be able to complete before
Naruon is described as a generally available commercial product.

Counts, branch SHAs, checks, reviews, and pull-request state are point-in-time
evidence. They must be re-fetched before a merge or release decision.

---

## 1. Executive decision

Naruon is no longer a small prototype. The protected branch already contains a
substantial, security-conscious **customer-owned communication and context
control plane**:

```text
customer-owned mail / calendar / contact / file systems
→ Naruon ingest, thread, search, context, evidence, task, and action control
→ explicit human approval or correction
→ conflict-aware provider writeback through an outbound connector
```

Naruon must **not** become an SMTP server, IMAP mailbox host, public MX provider,
calendar source of truth, or file source of truth. Customer providers remain
authoritative. Naruon owns scoped context, policy, recommendation, intent,
connector command state, retry/reconciliation evidence, and the user-visible
decision/action experience.

The accurate current product classification is:

> **Production-oriented pre-GA communication control plane with substantial
> protected-branch capability, an unconverged 83-PR integration surface, and an
> incomplete buyer-visible release/operations contract.**

The first sellable boundary is **GA-1: Customer-owned Mail, Calendar, Contact,
and File Control Plane**. The complete dense knowledge graph, no-ask
correct-by-exception reasoning, minimal-disclosure bridge, and third-party plugin
platform remain the north-star after GA-1 rather than prerequisites for the
first commercial release.

---

## 2. Evidence hierarchy

When sources disagree, use this order:

1. exact protected-branch code, migrations, tests, runtime contracts, and
   security boundaries;
2. exact protected-branch architecture and operations documents;
3. exact current pull-request code and current-head evidence;
4. open Issues and accepted ADRs;
5. older product plans, README limitations, and historical PR descriptions.

A plan marked `[LIVE]` is not proof if the protected implementation contradicts
it. Conversely, an old README statement that calls a protected implementation
“future work” must be corrected rather than used to hide shipped behavior.

---

## 3. Point-in-time repository snapshot

| Item | Observation |
|---|---|
| Protected branch | `develop@c9bfba2dc2063b82741686a3b3120a66c269ab27` |
| Product/package version | `0.14.4` |
| Open pull requests | **83** |
| Open issues before this baseline program | **59** |
| New completion issue | #1428 |
| Required backend runtime | Python 3.14 exact-head lane |
| Core runtime | Next.js frontend, FastAPI backend, PostgreSQL + pgvector |
| Default data authority | customer-owned mail, CalDAV/CardDAV, and WebDAV providers |
| Default merge posture | strict exact-head checks plus qualifying independent review |

The protected branch requires exact-head backend, frontend, security, CodeQL,
dependency review, Scorecard, OSV, Trivy, Strix, source/evidence coverage,
backend/frontend/combined image validation, and OpenCode review contexts. Pending,
queued, stale, predecessor-head, skipped-required, neutral, author-only,
model-only, or local-only evidence is not passing evidence.

---

## 4. Protected-branch product truth

### 4.1 Shipped communication and workspace surface

Protected `develop` exposes buyer-recognizable product surfaces for:

- Today execution dashboard;
- Mail, thread history, search, reply, and pending-reply work;
- Calendar views, source-backed coordination, and writeback intent;
- Tasks and source-linked ticket work;
- Projects, project graph, and evidence-linked records;
- Context Search and hybrid retrieval;
- AI Hub and provider-neutral AI workflows;
- Data/document ingestion and controlled materialization;
- Security/policy/audit views;
- Settings, identity, provider, and deployment controls.

The product already distinguishes simulated local send from real delivery,
preserves `In-Reply-To` and `References`, scopes email/provider records by owner
and organization, keeps opaque public identifiers separate from sequential
surrogates, and applies deny-first RBAC/ABAC policies.

### 4.2 Source-of-truth and writeback sovereignty

Protected `develop` already enforces important commercial boundaries:

- customer mail, calendars, contacts, and files remain durable provider truth;
- browser input selects an opaque source reference but cannot assert ownership,
  region, credential, or capability;
- writeback is intent-only unless the user explicitly requests provider
  execution;
- provider execution re-reads server-authoritative source records;
- CalDAV and WebDAV updates preserve ETag/If-Match conflict semantics;
- private-network provider access uses an outbound-only connector rather than
  inbound firewall holes or public mail hosting;
- provider credentials and command payloads are excluded from browser and
  aggregate observability surfaces.

### 4.3 Durable writeback retry is implemented

The current protected source-of-truth document records behavior that the root
README still describes as future work:

- scoped `provider_writeback_retry_items` rows;
- encrypted retry command payloads;
- retry dispatch with retry enqueue disabled for the nested attempt;
- exponential backoff;
- `succeeded`, rescheduled retry, and `failed_exhausted` outcomes;
- persisted connector signal events for dispatch, timeout, transport, and
  adapter outcomes;
- organization-admin aggregate queue-depth reads without exposing payload,
  credential, runner, source, or retry identities.

This is a material product-truth correction. The remaining gap is not “create a
retry queue.” It is **finish connector packaging, identity/enrollment, complete
protocol coverage, dead-letter/reconciliation operations, and buyer-visible
support evidence**.

### 4.4 AI and scientific boundary

Naruon has grounded content segments, hybrid search, named/versioned KG
extractor seams, deterministic fallback, contextual-orchestrator routing, and
batch-embedding integration boundaries. It does **not** have a protected live
Structural Topic Model endpoint or fitted topic artifact. Deterministic keyword
metadata must not be marketed as STM or temporal event psychometrics.

TEPP may be consumed only through a separately accepted, immutable, versioned
scientific artifact/API with preprocessing, vocabulary, covariates, posterior
uncertainty, diagnostics, provenance, and abstention. Naruon owns identity,
authorization, adapter envelopes, and disclosure policy; TEPP owns the
scientific payload.

---

## 5. Product-truth and release-truth inconsistencies

| Inconsistency | Current evidence | Buyer risk | Required correction |
|---|---|---|---|
| README says durable retry/audit remains future work | protected operations document describes encrypted retry rows, retry worker, backoff, exhaustion, and aggregate visibility | buyers and contributors cannot tell what is shipped | merge a customer/operator README based on protected truth; keep unsupported behavior explicitly limited |
| Release architecture says first candidate should be `v0.1.0` | `VERSION` and backend package are `0.14.4` | release procedure may publish or validate the wrong identity | replace historical hypothesis with current release-train policy and immutable release manifest |
| Product plan marks typed Person/Event/Commitment/Plugin concepts as new/planned | current code search does not prove authoritative `graph_persons`, `graph_events`, `graph_commitments`, or `plugin_registrations` stores | UI/marketing can imply dense-KG/product-platform completion that does not exist | keep north-star language, implement typed domains through bounded PRs, and gate claims on protected code |
| 83 open PRs contain many overlapping, stacked, micro, dependency, governance, and broad integration changes | current GitHub inventory | predecessor evidence, writer collision, stale branches, and integration starvation | establish a release train, classify every PR, close duplicates, merge parent-first, and use one writer per authority cluster |
| Required independent review exists but the current human reviewer path is unresolved | #1371 | green automation cannot produce a lawful protected merge | resolve reviewer governance without weakening rulesets or self-approval |
| Connector is described through a self-hosted-runner analogy | protected code has protocol adapters and retry behavior but no complete released connector lifecycle | operators may deploy test infrastructure as production relay | deliver signed installable connector artifacts, enrollment/rotation, source health, fleet SLO, and runbooks |

---

## 6. Current pull-request surface

The current open PR count is too large to treat as one releasable integration
unit. This baseline does not claim that every one of the 83 PRs has been
line-by-line approved. It records the product-significant active lanes observed
and defines the inventory that must be completed before GA.

### 6.1 Product-significant active lanes

| PR | Lane | Baseline judgment |
|---:|---|---|
| #1364 | scoped S3 document-object backend | high-leverage GA durability lane; Draft until real PostgreSQL + S3 lifecycle, backfill, cleanup, failure, and exact-head evidence are complete |
| #1417 | shared PostgreSQL-backed email-send throttle | necessary multi-replica safety; keep isolated and merge only with current-head concurrency/security evidence |
| #1416 | provider-backed CalDAV create writeback | relevant to GA scheduling execution; preserve create vs update precondition distinction and integrate into the broader #978 contract |
| #1353 | HWP/HWPX deterministic recognition boundary | useful Korean enterprise document admission; does not complete parsing/conversion/search semantics |
| #1397 | inline-media admission/tracking-pixel classification | valid evidence-protection slice; remain Draft until the #1350 stack and independent review are coherent |
| #1419 | common image metadata | bounded local evidence extraction; no OCR/VLM claim |
| #1418 | auditable URL/contact hygiene | deterministic tool/evidence lane; ensure contact redaction is not represented as complete anonymization |
| #1317 | broad macOS/local-AI/runtime/governance integration | valuable evidence but unusually broad; must be decomposed or reconciled carefully because many active PRs overlap its surfaces |
| #1392 | customer/operator README rewrite | directly addresses product-truth debt and has reported exact-head checks; still requires independent current-head approval |
| #1300 | fail closed on unsafe global tool mutations | correct safety posture until durable tenant-scoped plugin/tool registry exists; links directly to #976 |
| #1264 | EgressWeave integration | correctly dependency-blocked on an immutable released EgressWeave package and hash lock; mutable VCS dependency is forbidden |
| #1390 / #1391 | 56- and 78-package dependency groups | excessive blast radius, including major runtime and OpenAI client changes; split by compatibility/authority and rehearse migrations before merge |
| #1426 / #1414 | review-governance gate refresh | metadata-only governance repair; must not dismiss review, weaken rulesets, or turn stale aggregate state into false success |
| #1241, #1320, #1408, #1410, #1411, #1421, #1422 | accessibility micro-lanes | useful but numerous; consolidate non-overlapping UI fixes into bounded component-level trains to reduce 17-check amplification |
| #1424, #1412, #1401 | micro performance lanes | require real benchmark or stable complexity contract; do not let automated micro-PRs displace GA integration work |

### 6.2 Required complete inventory

Before a release candidate is cut, create a machine-readable and human-reviewed
inventory for **all** current open PRs with:

```text
pr_number
head_sha
base_ref_and_sha
draft_state
mergeability
changed_authority_cluster
stack_parent
stack_children
current_review_state
unresolved_threads
required_check_summary
product_lane
disposition
next_action
```

Allowed dispositions:

- direct GA-1 slice;
- ordered stacked child;
- dependency-blocked;
- governance-blocked;
- duplicate/superseded;
- experimental/north-star;
- unsafe or unrelated and to be closed.

The inventory must be regenerated after every parent merge or branch movement.
It must not embed provider credentials, customer data, review-body secrets, or
large copied PR bodies.

### 6.3 Queue convergence rules

1. One active writer owns each overlapping file/authority cluster.
2. A stacked child is not promoted before its parent reaches protected
   `develop` and the child is revalidated on the new exact base.
3. Predecessor-head checks and reviews never transfer.
4. Dependency changes that cross runtime majors are separated from unrelated
   feature work.
5. Historical one-shot, repair, finalizer, and self-modifying workflow identities
   are handled through #1324; do not add another write-capable cleanup workflow.
6. Independent approval remains mandatory; #1371 is resolved by establishing a
   legitimate reviewer path, not by weakening protection.
7. A micro-optimization requires measured evidence or a stable tested complexity
   invariant, not only an assertion that `Map` is faster than array lookup.
8. A PR that claims to close an umbrella issue must prove the full umbrella
   acceptance journey, not one narrow slice.

---

## 7. Buyer-visible Gap matrix

### P0 — Release and integration control

| Gap | Buyer problem | Protected/current evidence | Existing work | Completion evidence |
|---|---|---|---|---|
| Release-train convergence | no buyer can assess a product with 83 unconverged PRs | strict gates exist but queue topology is fragmented | #1428, #1371, #1324 | all PRs classified; duplicates closed; parent-first integration; one immutable RC SHA |
| Product/release truth | documentation conflicts with protected behavior/version | retry is shipped; release doc says `v0.1.0`; version is `0.14.4` | #1392, this PR | README, architecture, version, changelog, release manifest, and operator guide agree |
| Independent review path | automation cannot lawfully self-approve | effective rulesets require independent post-last-push approval | #1371 | verified reviewer route and normal protected merge without bypass |

### P0 — Connector and provider action

| Gap | Buyer problem | Protected/current evidence | Existing work | Completion evidence |
|---|---|---|---|---|
| Installable connector | adapters in source are not an operable product | outbound-only architecture and several adapters exist | #998 | signed packages/OCI, enrollment, rotation, upgrade/rollback, supported matrix |
| Source lifecycle | configuration does not equal observed provider capability | source IDs, eligibility, consent, and revisions exist in slices | #998, #978 | create/rotate/disable/delete, capability discovery, health, stale-capability invalidation |
| Durable reconciliation | retry exhaustion alone does not tell the buyer what happened remotely | retry/backoff/exhaustion and signal events exist | #998 | idempotent command, late-success reconciliation, dead-letter action, buyer receipt |
| Shared send safety | process-local throttles fail with multiple replicas | PR proposes PostgreSQL-backed atomic bucket | #1379, #1417 | concurrency/expiry/isolation/DB-unavailable tests and protected integration |

### P0 — Data durability, portability, and customer exit

| Gap | Buyer problem | Protected/current evidence | Existing work | Completion evidence |
|---|---|---|---|---|
| Binary object lifecycle | large/deferred document bytes cannot remain an inline database strategy | S3-compatible implementation is Draft | #1076, #1364 | upload/read/recognize/retain/delete/backfill/orphan round trip with real integration |
| Disaster recovery | a release is not enterprise-ready without restore evidence | HA evaluation exists; production WAL/PITR policy remains incomplete | #1428 | WAL archive/PITR, failover fencing, backup and clean restore rehearsal |
| Tenant export/reimport | customers need exit and migration without losing provenance | no single demonstrated full tenant round trip | #1428 | export → clean instance import preserving source, opaque IDs, history, evidence, policy |
| Retention/legal hold/disposition | deletion and evidence preservation conflict unless modeled | partial security/key/retention work exists across repository history | #1428, #1364 | purpose-scoped retention, legal hold, verified disposition, object/DB reconciliation |

### P0 — Evidence-based AI and document intelligence

| Gap | Buyer problem | Protected/current evidence | Existing work | Completion evidence |
|---|---|---|---|---|
| Canonical evidence identity | OCR/media/attachment/model slices can disagree about the same source | source segments and several deterministic admission slices exist | #1350, #1353, #1397, #1419 | one source identity/provenance chain across email, thread, document, attachment, media, model result |
| Judgment explanation | model output without evidence/calibration is not defensible | grounded extractor seam exists; wider evidence pipeline incomplete | #1350 | evidence IDs, claim support, abstention, correction, verifier result, prompt/model/version receipt |
| Provider-neutral route | raw provider coupling spreads credentials and failure behavior | contextual-orchestrator boundary exists; EgressWeave integration is blocked on release | #1262, #1264 | released hash-locked adapter, route/fallback evidence, no raw secret in products |
| Scientific claim discipline | keyword labels can be mistaken for topic/event measurement | architecture explicitly says no live STM | TEPP dependency path | accepted immutable TEPP artifact/API or explicit feature absence; no lexical-as-STM claim |

### P1 — Typed context and scheduling differentiation

| Gap | Buyer problem | Protected/current evidence | Existing work | Completion evidence |
|---|---|---|---|---|
| Typed Person/Event/Commitment graph | generic string graph cannot safely drive high-stakes action | planning spec marks types as new/planned | #977, #978, #1000 | normalized temporal/multi-membership identities, evidence/confidence/correction on every inferred edge |
| Status-weighted scheduling | calendar CRUD does not prevent harmful double booking | CalDAV source/writeback/retry foundation exists | #978, #988, #989, #990, #1416 | confirmed/tentative/desired + organizer/attendee + recurrence/free-busy/resource end-to-end |
| Minimal-disclosure bridge | personal context can influence work availability without exposing private reason | policy substrate exists; product bridge is planned | #979, #991 | consented consequence-only propagation, revocation, audit, regression tests |
| Correct-by-exception inference | asking users to reconstruct context defeats the product mission | extractor/search foundations exist; dense-KG resolution remains incomplete | #977, #992, #1001 | one recommendation, evidence/calibration, hold/override, correction learning, no silent irreversible action |

### P1 — Platform and ecosystem

| Gap | Buyer problem | Protected/current evidence | Existing work | Completion evidence |
|---|---|---|---|---|
| Plugin lifecycle | internal extension seams do not create an enterprise platform | extractor/parser seams exist; durable custom tool mutation fails closed | #976, #1300 | signed manifest/release, tenant grant, sandbox, compatibility, upgrade/rollback/uninstall |
| Stable cross-repository contracts | copying sibling code creates a distributed monolith | several adapters are planned or dependency-blocked | #976, #1262, #1350 | released SDK/API/event/OCI contracts pinned by version/digest; no direct sibling SQL |
| Buyer administration | operators need source, connector, policy, health, retention, and support controls | settings/security surfaces exist but not one completed admin lifecycle | #998, #1428 | role-specific admin console with next-action explanations and audited high-risk changes |

---

## 8. GA-1 product definition

GA-1 is complete only when a buyer can perform the following journey on one
released, immutable product version:

```text
install or access Naruon
→ authenticate through the supported enterprise identity boundary
→ install and enroll a signed outbound connector
→ register customer-owned mail/calendar/contact/file sources
→ verify observed source capabilities and health
→ synchronize source records with provenance
→ receive a source-cited judgment or action recommendation
→ inspect evidence, confidence, authorization, privacy, and provider impact
→ approve, hold, or correct the recommendation
→ execute an idempotent provider action with current revision protection
→ observe success, retry, conflict, exhaustion, or reconciliation evidence
→ restore, export, or migrate the tenant without losing provenance
```

Naruon is not GA if the demonstration substitutes mocked provider success,
process-local state, local-only credentials, predecessor-head checks, synthetic
review approval, hidden manual database edits, or an unreleased sibling branch.

---

## 9. Delivery sequence

### Wave 0 — Product truth and queue convergence

1. Merge this baseline after exact-head documentation checks and independent
   review.
2. Keep #1428 as the single completion gate.
3. Generate the complete 83-PR inventory and classify every PR.
4. Resolve #1371 without weakening protection.
5. Merge/close governance and stale-workflow lanes through normal protected
   integration.
6. Correct README/release/version contradictions.

### Wave 1 — GA-1 runtime and operations

1. Finish #998 connector artifact, enrollment, capability, fleet, retry, and
   reconciliation lifecycle.
2. Integrate shared send throttling (#1379/#1417).
3. Finish binary object lifecycle (#1076/#1364).
4. Complete PostgreSQL WAL/PITR/failover/restore evidence.
5. Complete OIDC/SCIM/tenant administration and privacy-safe OpenTelemetry/SLO.
6. Publish independent backend, frontend, connector, and compatibility artifacts.

### Wave 2 — Buyer differentiation

1. Implement typed temporal/multi-membership Person/Event/Commitment graph.
2. Complete status-weighted scheduling (#978/#988/#989/#990).
3. Complete evidence-based mail/document/media resolution (#1350).
4. Add tenant export/reimport and customer-exit evidence.
5. Run the full buyer journey and failure/restore variants.

### Wave 3 — North-star platform

1. Minimal-disclosure privacy bridge (#979/#991).
2. Dense-KG correct-by-exception resolution (#977/#992/#1001).
3. Signed plugin platform (#976) with one real independently released CWL
   plugin.
4. Optional TEPP and other ecosystem adapters through accepted immutable
   contracts.

---

## 10. Release and quality gate

### Product correctness

- real IMAP/SMTP and DAV interoperability fixtures;
- duplicate/replay, late response, partial failure, provider conflict, connector
  restart, network partition, and source-capability-change tests;
- recurrence, timezone, DST, organizer/attendee, free/busy, and resource
  scheduling tests;
- full tenant export/reimport and backup/restore rehearsals;
- buyer-visible provenance completeness and unsupported-claim rate gates;
- no silent confirmed-commitment break;
- no private reason crossing a context boundary without explicit authorized
  disclosure.

### Code and documentation

- production statement coverage 100% for owned production code;
- production branch coverage 100%;
- public API/module/class/function docstrings 100%;
- frontend component, interaction, action-edge, design-token, accessibility, and
  i18n tests;
- no documentation that represents planned behavior as shipped or shipped
  behavior as future work;
- ADR, PRD, TRD, architecture, data model, runbook, and standard traceability
  updated with each release-relevant decision.

### Database

- normalized ownership and provider mappings;
- descriptive two-or-more-word `snake_case` object names;
- no direct cross-service SQL;
- bitemporal/effective-dated facts where provider state, membership, consent,
  policy, or source mapping changes over time;
- tenant enforcement and hot-partition/load evidence;
- clean install, N-1 upgrade, expand/backfill/contract, rollback, and restore.

### Security and supply chain

- OAuth/OIDC threat controls aligned with the current OAuth 2.0 Security BCP;
- signed connector and release artifacts;
- digest-pinned OCI images;
- SPDX 3.0.1 SBOM;
- SLSA 1.2 provenance;
- dependency/license/vulnerability evidence;
- secret, prompt, message, event, contact, and file-content exclusion from
  ordinary telemetry;
- no mutable VCS dependency in production;
- no self-modifying or broad-token workflow used to compensate for product code.

### Operations

- liveness, startup, readiness, and drain semantics per independently deployable
  component;
- OpenTelemetry trace, metric, and log acceptance;
- low-cardinality label contract;
- SLO, error budget, burn-rate alert, dashboard, on-call, incident, and support
  bundle;
- connector offline/backpressure and safe rolling upgrade;
- backup/PITR/failover/restore and customer-exit runbooks;
- versioned support, deprecation, compatibility, and security-fix policy.

### Protected integration

- one exact current head and one exact protected base;
- all live required contexts terminal-success;
- zero actionable unresolved review threads;
- qualifying independent non-author post-last-push approval;
- no bypass, self-approval, force push, dummy commit, empty requeue, or stale
  predecessor evidence;
- immutable release source SHA and artifact digests recorded in release evidence.

---

## 11. Issues established or strengthened by this baseline

| Issue | Purpose |
|---:|---|
| [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428) | new umbrella: GA scope, release train, and buyer-visible acceptance |
| [#976](https://github.com/ContextualWisdomLab/naruon/issues/976) | strengthened: signed plugin SDK, registry, permissions, compatibility, sandbox, lifecycle |
| [#978](https://github.com/ContextualWisdomLab/naruon/issues/978) | strengthened: typed Event/Commitment model, iTIP/CalDAV scheduling, free/busy/resource, conflict and privacy contract |
| [#998](https://github.com/ContextualWisdomLab/naruon/issues/998) | strengthened: installable connector, enrollment/identity, protocol capability, reconciliation, OpenTelemetry/SLO |

Existing linked implementation and blocker issues remain authoritative for their
bounded scopes, including #1022, #1076, #1229, #1262, #1324, #1350, #1371, and
#1379.

---

## 12. Standards and research traceability

The following standards are not decorative references. They define protocol,
security, accessibility, observability, or supply-chain acceptance tests in the
issues above.

### APA 7th references

Crispin, M. (2003). *Internet Message Access Protocol—Version 4rev1* (RFC
3501). RFC Editor. https://doi.org/10.17487/RFC3501

Daboo, C. (2010). *iCalendar transport-independent interoperability protocol
(iTIP)* (RFC 5546). RFC Editor. https://doi.org/10.17487/RFC5546

Daboo, C. (2011). *vCard extensions to WebDAV (CardDAV)* (RFC 6352). RFC
Editor. https://doi.org/10.17487/RFC6352

Daboo, C., Desruisseaux, B., & Dusseault, L. M. (2007). *Calendaring extensions
to WebDAV (CalDAV)* (RFC 4791). RFC Editor. https://doi.org/10.17487/RFC4791

Daboo, C., & Desruisseaux, B. (2012). *Scheduling extensions to CalDAV* (RFC
6638). RFC Editor. https://doi.org/10.17487/RFC6638

Daboo, C., & Quillaud, A. (2012). *Collection synchronization for Web
Distributed Authoring and Versioning (WebDAV)* (RFC 6578). RFC Editor.
https://doi.org/10.17487/RFC6578

Gellens, R., & Klensin, J. (2011). *Message submission for mail* (RFC 6409).
RFC Editor. https://doi.org/10.17487/RFC6409

Jenkins, N., & Newman, C. (2019). *The JSON Meta Application Protocol (JMAP)
for Mail* (RFC 8621). RFC Editor. https://doi.org/10.17487/RFC8621

Lodderstedt, T., Bradley, J., Labunets, A., & Fett, D. (2025). *Best current
practice for OAuth 2.0 security* (BCP 240; RFC 9700). RFC Editor.
https://doi.org/10.17487/RFC9700

Melnikov, A., & Leiba, B. (2021). *Internet Message Access Protocol (IMAP)
version 4rev2* (RFC 9051). RFC Editor. https://doi.org/10.17487/RFC9051

OpenSSF. (2026). *Supply-chain Levels for Software Artifacts specification,
version 1.2*. https://slsa.dev/spec/v1.2/

OpenTelemetry Authors. (2026). *OpenTelemetry specification, version 1.59.0*.
https://opentelemetry.io/docs/specs/otel/

SPDX Workgroup. (2024). *SPDX specification, version 3.0.1*.
https://spdx.github.io/spdx-spec/

World Wide Web Consortium. (2024). *Web Content Accessibility Guidelines
(WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

---

## 13. Claim boundary

This baseline is a product and technical decision record, not a certification,
security attestation, market valuation, or claim that Naruon is already GA.

The existence of 100% coverage gates, many PRs, or detailed documentation does
not itself demonstrate commercial completeness. GA is demonstrated only by the
end-to-end buyer journey, current exact-head protected integration, released
artifacts, provider interoperability, recovery/customer-exit evidence, and
operational support contract defined here.
