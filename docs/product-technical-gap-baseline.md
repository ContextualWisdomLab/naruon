# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.5  
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

- `.github#712` is the canonical operations owner for organization GitHub Actions queue starvation. Fresh observation on 2026-09-19 found **512 queued** and **11 in-progress** runs in the central `.github` repository; #1602 exact-head repository workflows are also entirely queued. This is a fail-closed execution-capacity prerequisite, not product GREEN or a reason to rerun unchanged heads. Diagnose and cancel only obsolete generations through the owner path, preserve the sole current-head required evidence, and recover runner assignment before treating hosted acceptance as available.
- `.github#2040@ecc9e1d11149ae44ec4f8389e4ac72a08ba45ba7` has now completed the previously required ordinary/non-force protected-main path-wise reconciliation. Its reconciliation commit preserves the branch-owned scheduler/credential/exact-evidence contracts together with protected-main queue/GHAS/compatibility/retry deltas, repairs the stronger repository-identity boundary, removes the superseded unversioned CodeQL fallback, and keeps the v2 rerun payload within GitHub's top-level property ceiling. Focused verification is locally GREEN (**496 passed**; full **3,404 passed / 28 skipped / 40 subtests passed**), but the current hosted CodeQL, Security, Runtime Quality, Trusted uv, Python Security and Semgrep runs remain queued and qualifying independent current-head approval is still absent. Reconciliation is source-complete evidence, not merge authority.
- `.github#2279@b338d1e246fcd13ed4b61ae63e6d36d4a4129beb` is the current authenticated GitHub API authority owner. Beyond initial-authority validation, fail-closed redirect refusal, corrected transport seams and production-opener synthetic-302 tests, it now owns an executable evidence-lineage invariant: every full G-17 evidence SHA must resolve as a commit and be an ancestor of the exact checked-out head; an unreachable commit-shaped mutation fails closed. Focused static/mechanism review is GREEN, but current Python Security, Runtime Quality, CodeQL, Security and Semgrep runs remain queued.
- `.github#2272@5c71e889a5ec7e4ad0e0d010c222ec521050bb9a` has ordinary-forwarded beyond its earlier Pages-only generation and is now an exact descendant of current #2279 `b338d1e...`. Its effective successor tree therefore carries the current authenticated GitHub API authority lineage plus reusable Pages caller-input shell-boundary CI/origin-hardening deltas. The PR body still describes predecessor `e0b6e70f...`, so consumers use the exact Git graph and current head rather than that stale prose snapshot. Fresh exact-head hosted evidence is queued; source convergence does not make this lane accepted.
- `.github#2269@834d285f90241b4741247408001fd7534ce5a3b0` remains a divergent historical redirect-containment/test-seam owner. Do not close it merely because #2272 now descends from #2279: a fresh complete-succession audit must prove every valid #2269 source/test/doctoring contract is inherited or deliberately superseded before retirement.
- `.github#2275@fc9c5537d9910f0536dab2aaf52888078c8ead64` owns capability-based selection of a credential that can actually read `code-scanning/analyses`; it does not manufacture repository permission. Its current authority now points at #2279 `b338d1e...` as the foundation prerequisite. After the consolidated central security lineage is accepted, this selector must be ordinary-forward/non-force reconciled and reacquire exact-head evidence.
- `.github#2276` separately owns the observed target-repository `403 Resource not accessible by integration` boundary. Acceptance requires an unchanged-target canary that reads both protected-base and exact-head analyses and completes language pairing. A GREEN selector alone does not satisfy this permission boundary.

No Naruon PR may copy these central workflow implementations. Consumers wait fail-closed for released/protected owner evidence and then ordinary-restack onto that contract.

### 3.2 Frontend dependency-security owner

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) is the canonical frontend dependency-security owner at exact head `509be4c1d9b6c7ba239a108656e2382681a85341`. That generation has six repository-local workflows GREEN and exact-head CodeRabbit approval with no unresolved review thread. Later #1718 Trivy evidence used a newer vulnerability database and found protected-base `next`/`sharp` debt that #1623's source already repairs. Therefore the old Security receipt is valid historical evidence for its generation but not proof against the later database generation. After central reconciliation and execution-capacity recovery, reacquire the invalidated current-base/current-database evidence before integration.

### 3.3 Workspace and migration lineage

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the canonical workspace-registry / historical document-migration owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`, stacked on #1565. Its authoritative migration line is:

`0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`

The source repairs the known ownership RED, but final PostgreSQL fresh/historical execution and CI/security/review evidence remain blocked on the normal prerequisite line. No downstream feature may create a parallel Alembic head from protected `develop`; descendants must adopt the then-current canonical protected migration head.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) is correctly stacked on #1503 for opaque-ID backfill entropy and remains Draft. The repair changes only missing UID generation to PostgreSQL `gen_random_uuid()` while preserving public identifier shape. It does not rotate existing identifiers or treat opacity as authorization.

### 3.4 Generated provenance lanes

Generated branches that rediscover an owned delta are provenance, not new owners. Current examples include #1724, #1728 and #1730. They are zero-effective-delta or canonical-tree descendants after ordinary/non-force reconciliation. Their checks and reviews do not transfer to the actual owner.

The recurrence itself is a control-plane Gap: once a generated branch is reconciled to provenance, its writer should become terminal/read-only or new generated work should perform semantic owner-overlap detection and route to the canonical owner before product source is rewritten. Source-neutral `trigger CI` commits are not acceptance evidence.

### 3.5 Auditable data-hygiene owner

[#1418](https://github.com/ContextualWisdomLab/naruon/pull/1418) is the canonical URL/contact data-hygiene owner at exact head `87a94a4c2b78f12a61ec699dee9ce081ea3d8578` and tree `f17cc6848752749ca965af1a7ca9d3f422c4b4d7`. On predecessor `a4a4da69...`, a RED regression proved that adjacent Markdown links were merged into one malformed URL candidate and that a typographic closing quote remained inside the candidate. The exact-head repair separates those delimiters while preserving IPv6 and balanced punctuation contracts; the focused URL suite is 11 passed and the full backend is 1,830 passed / 33 skipped with warnings as errors. Ruff, compileall and diff checks also pass.

This remains Draft source evidence, not integrated product acceptance. ADR-0008 is correctly Proposed while unlanded. Exact-head Application CI `35433208478`, Bandit `35433208495`, Docker `35433208617`, Security `35433208474`, Semgrep `35433208453` and CodeQL `35433208463` were queued at the latest poll; zero unresolved review threads and local GREEN do not substitute for terminal hosted checks or a qualifying post-last-push independent approval. #1590 remains open until protected-tree succession proves its valid URL delta is fully inherited.

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

Current `contextual-orchestrator` protected main is `5665b0ad1e07ffb5e9f8c59e44b6b2a785298013`, but its GitHub Releases inventory is empty. Therefore protected `main` is not a released consumer identity. Naruon must keep any production path that requires an immutable CO API/client/schema release fail-closed until the owner publishes one and the consumer pins that released identity. No source copy or mutable-head dependency is accepted.

## 6. Buyer-visible P0/P1 Gap baseline

| Priority | Gap | Current boundary | Completion evidence |
| --- | --- | --- | --- |
| P0 | Release-train convergence | 279 open PRs; many stacked/provenance/dependency/governance lanes; protected head unchanged | canonical owner inventory, parent-first protected integration, no orphaned valid delta, one immutable RC source SHA |
| P0 | Actions execution capacity | `.github#712` remains open; fresh central snapshot has 512 queued / 11 in-progress runs and current #1602 evidence lanes are queued | owner health report distinguishes current vs obsolete runs, obsolete pressure is removed without cancelling the sole current-head evidence, and required current-head lanes receive runner assignment and settle terminally |
| P0 | Central CI/security acceptance | #2040 source reconciliation is complete; #2272 now descends from current #2279, but consolidated exact-head hosted evidence, #2269 succession audit, GHAS selector/permission and independent review remain incomplete | terminal consolidated central checks, verified complete succession, qualifying independent review, real cross-repository GHAS canary |
| P0 | Dependency-security freshness | #1623 generation GREEN, later Trivy DB sees protected-base debt | revalidate canonical fixed source against then-current base and vulnerability database after central integration |
| P0 | Workspace/migration convergence | #1503 source repairs owner-binding RED but is not protected-integrated | one Alembic head, real PostgreSQL fresh + historical upgrade, exact-head CI/security/review |
| P0 | Immutable LLM contract | CO protected main exists but releases are `[]` | immutable owner release, consumer version/digest pin, schema/E2E/model behavior/security/SBOM/provenance |
| P0 | Product/release truth | latest Naruon Release `v0.14.4` is mutable and predates current protected head | code-current docs, version/CHANGELOG, immutable publication, SBOM/provenance/reproducibility/rollback |
| P0 | Connector/provider operability | protocol/writeback/retry foundations exist; full released connector lifecycle remains incomplete | signed installable artifact, enrollment/rotation, capability health, idempotent reconciliation, support evidence |
| P0 | Recovery/customer exit | historical baseline records partial backup/object/portability work, not one buyer round trip | restore/PITR and tenant export→clean-import rehearsal preserving provenance/authorization |
| P1 | Auditable data hygiene | #1418 delimiter repair is exact-tree GREEN locally; hosted checks and current-head approval are pending | terminal exact-head checks/review, normal protected integration, then verified #1590 succession |
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

1. recover current-head Actions execution capacity through `.github#712`, cancelling only obsolete/superseded pressure and preserving fail-closed current-head required evidence; do not blind-rerun or create source-neutral wake commits;
2. terminalize and independently review the reconciled #2040 exact head and the current #2279→#2272 consolidated security/Pages lineage; audit #2269 for verified complete succession before any retirement;
3. reconcile and validate #2275 on the accepted foundation, then prove #2276's unchanged external authenticated dispatch/GHAS canary with real target analysis-read permission;
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