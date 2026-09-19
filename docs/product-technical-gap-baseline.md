# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.0  
**Observed on:** 2026-09-19 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

This file is the current product/technical authority overlay. Historical point-in-time inventories and the previous v1.9 ledger are preserved byte-for-byte at `docs/product-technical-gap-history/2026-09-12-baseline-v1.9.md`. Historical evidence remains audit material, but current merge, release, owner, and buyer-readiness decisions must use the live authority below and fresh exact-head repository evidence.

## 1. Evidence hierarchy and release posture

When sources disagree, use this order:

1. exact protected-branch code, migrations, tests, runtime contracts, and security boundaries;
2. exact protected-branch architecture and operations documents;
3. exact current pull-request source and current-head evidence;
4. open Issues and Proposed/Accepted ADRs, with Accepted status requiring landed evidence;
5. archived baseline observations, older plans, README statements, and historical PR descriptions.

Pending, queued, stale, predecessor-head, skipped-required, neutral, author-only, local-only, or model-only evidence is not passing evidence. A protected release requires one exact integrated head, terminal required contexts, zero valid unresolved review findings, qualifying independent post-last-push review, immutable publication identity, SBOM/provenance, reproducibility, rollback evidence, and buyer-visible acceptance where the change affects product behavior.

Current repository shape is **279 open PRs and 75 open Issues**. The three effective rulesets — `CWL Central required workflows`, `Lock default branch`, and `PR` — are active. The latest GitHub Release is `v0.14.4`, published 2026-06-19, and is `immutable=false`; it is historical release evidence, not the target commercial immutable publication contract.

## 2. Current commercial classification

Naruon remains a production-oriented pre-GA communication and context control plane. Customer-owned mail, calendar, contact, and file systems remain source-of-truth systems. Naruon owns scoped context, policy, recommendation and intent state, provider-command/retry/reconciliation evidence, authorization boundaries, and the buyer-visible decision/action experience.

GA-1 remains **Customer-owned Mail, Calendar, Contact, and File Control Plane**. Naruon is not GA merely because individual PRs have green local tests, hosted checks, high coverage, or generated release artifacts. GA requires one protected, immutable product identity that proves the full buyer journey, provider interoperability, recovery/customer-exit behavior, current security evidence, and an operable support contract.

The north-star dense knowledge graph, correct-by-exception inference, minimal-disclosure bridge, optional scientific adapters, and third-party plugin ecosystem remain later product differentiation unless a bounded GA-1 workflow directly depends on them.

## 3. Current owner graph and integration gates

### 3.1 Central CI/security control plane

Protected central truth is `.github/main@64aa08d7fa487deacd41c761c36277ca68cab6c9`.

- `.github#2040@12c3fa6f3623aa5f2979d3d5ee4ed987002a6c0d` is the shared CodeQL/current-head scheduler owner. It is open, Draft and non-mergeable. Exact branch and protected main diverge from merge base `fb17ef556f94f673234aa557254ae52779e9a7b0`, and both changed the shared scheduler. The next branch-moving action is ordinary/non-force **path-wise protected-main reconciliation**, not whole-file adoption or an isolated stale-side regex patch. The resolved scheduler must preserve the v2 CodeQL producer, no-restamp behavior, private-consumer read grants, repository-scoped credential routing, selected-token/workflow-token proof, exact-head stale-run revalidation, current-main queue/coalescing/capacity behavior, and the stronger repository-identity admission invariant.
- `.github#2279@25f83aaee9eb97e423f6ef2467e722035bc2e362` owns authenticated GitHub API initial-authority validation, redirect refusal, and the corrected `_GITHUB_API_OPENER.open` transport test seam. Its current Python Security, CodeQL, Runtime Quality, Semgrep, and Security runs are queued; source repair is not acceptance evidence.
- `.github#2272@4967d66f303bde675080466e359e75c260a91e06` separately owns reusable Pages caller-input shell-boundary regression and its executable CI. It is not a complete successor for the authenticated HTTP boundary unless the #2279/#2269 delta is losslessly inherited.
- `.github#2275@fc9c5537d9910f0536dab2aaf52888078c8ead64` owns capability-based selection of a credential that can actually read `code-scanning/analyses`; it does not manufacture repository permission.
- `.github#2276` separately owns the observed target-repository `403 Resource not accessible by integration` boundary. Acceptance requires an unchanged-target canary that reads both protected-base and exact-head analyses and completes language pairing. A GREEN selector alone does not satisfy this permission boundary.

No Naruon PR may copy these central workflow implementations. Consumers wait fail-closed for released/protected owner evidence and then ordinary-restack onto that contract.

### 3.2 Frontend dependency-security owner

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) is the canonical frontend dependency-security owner at exact head `509be4c1d9b6c7ba239a108656e2382681a85341`. That generation has six repository-local workflows GREEN and exact-head CodeRabbit approval with no unresolved review thread. Later #1718 Trivy evidence used a newer vulnerability database and found protected-base `next`/`sharp` debt that #1623's source already repairs. Therefore the old Security receipt is valid historical evidence for its generation but not proof against the later database generation. After central reconciliation and protected-base movement, reacquire the invalidated current-base/current-database evidence before integration.

### 3.3 Workspace and migration lineage

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the canonical workspace-registry / historical document-migration owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`, stacked on #1565. Its authoritative migration line is:

`0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`

The source repairs the known ownership RED, but final PostgreSQL fresh/historical execution and CI/security/review evidence remain blocked on the normal prerequisite line. No downstream feature may create a parallel Alembic head from protected `develop`; descendants must adopt the then-current canonical protected migration head.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) is correctly stacked on #1503 for opaque-ID backfill entropy and remains Draft. The repair changes only missing UID generation to PostgreSQL `gen_random_uuid()` while preserving public identifier shape. It does not rotate existing identifiers or treat opacity as authorization.

### 3.4 Generated provenance lanes

Generated branches that rediscover an owned delta are provenance, not new owners. Current examples include #1724, #1728 and #1730. They are zero-effective-delta or canonical-tree descendants after ordinary/non-force reconciliation. Their checks and reviews do not transfer to the actual owner.

The recurrence itself is a control-plane Gap: once a generated branch is reconciled to provenance, its writer should become terminal/read-only or new generated work should perform semantic owner-overlap detection and route to the canonical owner before product source is rewritten. Source-neutral `trigger CI` commits are not acceptance evidence.

## 4. UI, localization, and OIDC interaction state

[#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) is the bounded OIDC pending-feedback owner at exact head `85e312360c6342f9bb02b6a6004b2a69599bd4e6`. An intervening generated rewrite removed the rendered regression and doctoring; ordinary child `85e312...` restored the reviewed tree without force-push. The effective delta is exactly `SettingsLayout.tsx`, the rendered pending-feedback test, and its doctoring record.

The rendered jsdom contract proves per-action pending state, native duplicate-click prevention, `aria-busy`, spinner/visible pending copy, success cleanup, rejected-logout cleanup, and error surfacing. Exact-current Application CI, Bandit, Docker, Security, Semgrep, and CodeQL runs are still queued. Real-browser keyboard/focus/touch/assistive-technology, responsive screenshots, and qualifying independent current-head review are absent.

Canonical localization Gap is [#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731). It owns a product-local **UI Localization Catalog** for KO/EN/JA/ZH/VI/ES/DE/FR with these invariants:

- stable `(screen_key, message_key)` product identity; display text is not identity;
- normalized PostgreSQL message definitions, immutable translation revisions, immutable published resource versions, and version bindings;
- publication fails if any active message lacks one of the eight required locales or violates placeholder schema;
- screen-scoped read/cache API with resource version and ETag; no whole-product browser catalog and no heavy browser i18n runtime as a prerequisite;
- UI translation authority remains separate from ontology/concept-label authority;
- browser/runtime credentials are read-only; publication is a short operator/content-governance transaction after drafting/review work;
- locale-specific Storybook and real-browser acceptance covers CJK line breaking/font fallback, Vietnamese diacritics, DE/FR/ES text expansion, responsive layouts, keyboard/focus/touch/a11y, and no hydration locale flash.

#1731 must not create a parallel migration line. Its implementation owner is created only after #1503's canonical migration ancestry is protected or completely succeeded, then it adopts the current migration head. #1729 consumes the released screen resource only after that owner exists.

**Current UI Delivery Gate for #1729: FAIL.** Intent is PASS; functional completeness and resilience are PARTIAL; multilingual content and buyer-visible exact-head evidence are FAIL. No completion claim is permitted yet.

## 5. LLM and cross-repository contract boundary

All Naruon model-backed production work consumes the released `contextual-orchestrator` API/client/schema through an Agent boundary. Actions request `orchestrator/free` through the gateway token only; they do not hard-code provider/model/group or paid fallback.

Current `contextual-orchestrator` protected main is `afad3e90caac73d5b94eb68f70953b5589a01008`, but its GitHub Releases inventory is empty. Therefore protected `main` is not a released consumer identity. Naruon must keep any production path that requires an immutable CO API/client/schema release fail-closed until the owner publishes one and the consumer pins that released identity. No source copy or mutable-head dependency is accepted.

## 6. Buyer-visible P0/P1 Gap baseline

| Priority | Gap | Current boundary | Completion evidence |
| --- | --- | --- | --- |
| P0 | Release-train convergence | 279 open PRs; many stacked/provenance/dependency/governance lanes; protected head unchanged | canonical owner inventory, parent-first protected integration, no orphaned valid delta, one immutable RC source SHA |
| P0 | Central CI/security acceptance | central scheduler and authenticated HTTP/GHAS permission lanes remain Draft/queued | reconciled protected-main exact head, terminal central checks, independent review, real cross-repository canary |
| P0 | Dependency-security freshness | #1623 generation GREEN, later Trivy DB sees protected-base debt | revalidate canonical fixed source against then-current base and vulnerability database after central integration |
| P0 | Workspace/migration convergence | #1503 source repairs owner-binding RED but is not protected-integrated | one Alembic head, real PostgreSQL fresh + historical upgrade, exact-head CI/security/review |
| P0 | Immutable LLM contract | CO protected main exists but releases are `[]` | immutable owner release, consumer version/digest pin, schema/E2E/model behavior/security/SBOM/provenance |
| P0 | Product/release truth | latest Naruon Release `v0.14.4` is mutable and predates current protected head | code-current docs, version/CHANGELOG, immutable publication, SBOM/provenance/reproducibility/rollback |
| P0 | Connector/provider operability | protocol/writeback/retry foundations exist; full released connector lifecycle remains incomplete | signed installable artifact, enrollment/rotation, capability health, idempotent reconciliation, support evidence |
| P0 | Recovery/customer exit | historical baseline records partial backup/object/portability work, not one buyer round trip | restore/PITR and tenant export→clean-import rehearsal preserving provenance/authorization |
| P1 | UI localization | #1731 is architecture Gap only; current surfaces still embed Korean product copy | versioned 8-locale DB resource/API/cache/publish contract + locale Storybook/browser/a11y acceptance |
| P1 | OIDC pending UX | #1729 rendered jsdom repair exists but hosted/browser/multilingual evidence is incomplete | exact-head terminal checks/review + browser/AT/responsive evidence + released locale resource consumption |
| P1 | Generated-writer owner lock | repeated generated source re-entry after zero-delta reconciliation | semantic owner-overlap detection and writer-terminal/read-only control with regression evidence |
| P1 | Typed context/scientific differentiation | generic context/search/extractor foundations exist; no protected live STM/TEPP claim | released typed/scientific owner contract with uncertainty/provenance/abstention; no lexical-as-psychometrics marketing |

Rows from the archived v1.9 baseline remain useful historical evidence for connector lifecycle, object storage, recovery, provider scheduling, evidence identity, plugin lifecycle, accessibility, and release-train history. They are not silently converted into present-tense claims. Any still-open gap is tracked through its live Issue/PR owner and must be re-fetched before action.

## 7. Performance, data, and DDD acceptance

- DDD Subdomain/Bounded Context/Context Map and Aggregate/Entity/Value Object/Domain Service/Repository/Event/Invariant naming must match ADR, code, API, DB, and tests.
- Aggregates keep transactions minimal. No LLM/network/long computation occurs inside an explicit database transaction. Cross-service SQL is forbidden.
- New persistence uses normalized schemas, descriptive multi-word `snake_case`, explicit ownership/tenant keys, idempotent item-level UPSERT where appropriate, and read/write separation or partitioning only from measured contention.
- Applicable buyer web/API paths target realistic p95 ≤20 ms. Evidence must use real query/I/O/render/runtime conditions; no sample shrink, measurement exclusion, or unrealistic cache warm-up.
- Performance/security/data-science hot paths are Rust-first where justified by profiling and contract constraints; Python remains a documented boundary when no practical Rust replacement exists.
- Deprecation and warning output is a defect to root-cause, fix, or explicitly track; warnings are not normal release noise.

## 8. UI quality contract

Material UI is not complete without normal/loading/empty/error/permission states, responsive composition, keyboard/focus/touch/a11y evidence, and exact-head screenshots/E2E where the surface is buyer-visible. Storybook source-component provenance and Storybook rendered behavior are separate evidence.

Delivery Gate:

- **Intent:** every visual/copy decision maps to a buyer task or product state.
- **Functional completeness:** displayed interactions work and preserve error/recovery semantics.
- **Content:** no template filler, unsupported statistics, fake customer/security/performance claims, or generic CTA copy.
- **Resilience:** mobile/intermediate widths, keyboard focus, loading/empty/error/permission states, and long/localized text do not break the task.
- **Evidence:** assertions are tied to current source/resource identity and reproducible browser/test receipts.
- **Distinctiveness:** product information architecture and interaction model remain recognizable without relying on generic AI gradients/cards/glass effects.

If one required axis fails, the material UI is not complete.

## 9. Release gate and next causal order

Current **Merge/Release Gate: FAIL**.

The current causal order is:

1. converge the central authenticated-HTTP / Pages / GHAS capability and permission lanes without losing valid owner deltas;
2. perform #2040 ordinary/non-force protected-main path-wise reconciliation and acquire fresh exact-head central GREEN + qualifying independent review;
3. prove the unchanged external authenticated dispatch/GHAS canary;
4. revalidate and normally integrate #1623 against the then-current protected base and vulnerability database;
5. integrate the Alembic/CI prerequisite line (#1694 → #1691 and direct code prerequisite) and then #1503 with one healthy migration head and real PostgreSQL fresh/historical evidence;
6. ordinary-restack downstream workspace/Reply-SLA/migration consumers and reacquire invalidated exact-head evidence;
7. create one #1731 localization implementation owner from the then-current canonical migration head, publish/test the 8-locale screen-resource contract, then ordinary-adapt #1729;
8. only after an exact integrated protected candidate exists, update version/CHANGELOG and produce immutable release/package/OCI publication with SBOM, provenance, reproducibility, rollback, and buyer-visible acceptance evidence.

No force push, destructive rebase, self-approval, admin bypass, source-neutral wake commit, synthetic success, stale check/review transfer, duplicate owner, mutable sibling dependency, whole-file conflict overwrite, or gate weakening is part of this path.

## 10. Standards and traceability additions

Current localization and accessibility work maps at minimum to:

Phillips, A., & Davis, M. (2009). *Tags for identifying languages* (BCP 47; RFC 5646). RFC Editor. https://doi.org/10.17487/RFC5646

Fielding, R., Nottingham, M., & Reschke, J. (2022). *HTTP semantics* (RFC 9110). RFC Editor. https://doi.org/10.17487/RFC9110

World Wide Web Consortium. (2024). *Web Content Accessibility Guidelines (WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

The archived v1.9 baseline retains the broader protocol, observability, provenance, storage, supply-chain, and UI research bibliography. A new implementation must still bind the cited standard to exact code/API/test evidence rather than cite it decoratively.

## 11. Claim boundary

This baseline is a product and technical decision record, not a certification, market valuation, or assertion that Naruon is already GA. Coverage percentages, PR volume, local test counts, model reviews, and documentation volume are supporting evidence only. Commercial completion requires the end-to-end buyer journey on the exact released identity, with current security, interoperability, recovery, authorization, provenance, operations, and support evidence.