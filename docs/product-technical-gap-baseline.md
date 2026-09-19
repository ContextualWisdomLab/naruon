# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.6  
**Observed on:** 2026-09-19 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

This file is the current product/technical authority overlay. Historical point-in-time inventories and the previous v1.9 ledger remain preserved byte-for-byte at `docs/product-technical-gap-history/2026-09-12-baseline-v1.9.md`; intervening v2.x generations remain reconstructable from Git history. Historical evidence is audit material, not current merge or release authority.

## 1. Evidence hierarchy and release posture

When sources disagree, use this order:

1. exact protected-branch code, migrations, tests, runtime contracts, and security boundaries;
2. exact protected-branch architecture and operations documents;
3. exact current pull-request source and current-head evidence;
4. open Issues and Proposed/Accepted ADRs, with Accepted status requiring landed evidence;
5. archived baseline observations, older plans, README statements, and historical PR descriptions.

Pending, queued, stale, predecessor-head, skipped-required, neutral, author-only, local-only, or model-only evidence is not passing evidence. A protected release requires one exact integrated head, terminal required contexts, zero valid unresolved review findings, qualifying independent post-last-push review, immutable publication identity, SBOM/provenance, reproducibility, rollback evidence, and buyer-visible acceptance where behavior changes.

Current repository shape is **279 open PRs and 75 open Issues**. The three effective rulesets — `CWL Central required workflows`, `Lock default branch`, and `PR` — are active. The latest GitHub Release is `v0.14.4`, published 2026-06-19, and is `immutable=false`; it is historical publication evidence, not the target commercial immutable release.

## 2. Current commercial classification

Naruon remains a production-oriented pre-GA communication and context control plane. Customer-owned mail, calendar, contact, and file systems remain systems of record. Naruon owns scoped context, policy, recommendation and intent state, provider-command/retry/reconciliation evidence, authorization boundaries, and the buyer-visible decision/action experience.

GA-1 remains **Customer-owned Mail, Calendar, Contact, and File Control Plane**. Individual PR GREEN, high coverage, generated artifacts, or local test volume do not constitute GA. GA requires one protected immutable identity proving the buyer journey, provider interoperability, recovery/customer exit, current security evidence, and an operable support contract.

## 3. Current owner graph and integration gates

### 3.1 Central CI/security control plane

Protected central truth remains `.github/main@64aa08d7fa487deacd41c761c36277ca68cab6c9`.

- `.github#712` remains the canonical organization Actions queue-starvation owner. Fresh observation now shows **531 queued / 4 in-progress** runs in the central `.github` repository. This is worse queue pressure than v2.5's 512/11 snapshot and remains a fail-closed execution-capacity prerequisite. Preserve the sole current-head evidence, remove only obsolete/superseded pressure through the owner path, and do not blind-rerun unchanged heads.
- `.github#2040@ecc9e1d11149ae44ec4f8389e4ac72a08ba45ba7` has completed ordinary/non-force path-wise protected-main reconciliation. Its reconciled source repairs repository identity, removes the superseded unversioned CodeQL fallback, preserves the v2 producer/credential/no-restamp contracts and current-main queue/GHAS behavior, and verified locally at **496 focused passed; 3,404 passed / 28 skipped / 40 subtests**. Hosted exact-head checks and qualifying independent current-head approval remain prerequisites; source reconciliation is not merge authority.
- `.github#2279@d1e4380c15e948aaf104d46aa134fa614058782a` is now the current authenticated GitHub API authority. It ordinary-forwarded beyond the v2.5 `b338d1e...` generation, retaining initial-authority validation, no-redirect production openers, bearer non-forwarding, executable G-17 ancestry validation, and now owner-qualifying the foreign Semgrep evidence reference. It is Ready for review, not merge-authoritative; its current Python Security/CodeQL/Security/Semgrep/Runtime Quality generation is still pending/queued and independent current-head review remains required.
- `.github#2271@8aff1a6a581613709c01747fe68c1f7523fe84da` is the current CodeQL dispatch repository-identity descendant of #2279 `d1e4380...`. Its ordinary two-parent reconciliation preserves the latest #2279 authority and the dispatch admission/stderr contract. Focused reconciliation is locally GREEN, but hosted current-head evidence and independent approval must be reacquired.
- `.github#2275@f54aeb6f5c6b30534ee2f12e040208e098957b4b` is now the current GHAS analysis-read capability-selector descendant of #2271/#2279. It hardens the executable selector test so success requires the exact `code-scanning/analyses?per_page=1&tool_name=CodeQL` endpoint and reviewed headers; focused stack is **165 passed**, full local suite **3,378 passed / 28 skipped / 40 subtests**. It remains Draft/Proposed until its foundation is accepted, hosted evidence is terminal, independent approval is current, and #2276 proves real target permission.
- `.github#2272@5c71e889a5ec7e4ad0e0d010c222ec521050bb9a` still preserves the Pages caller-input shell boundary and the earlier #2279 `b338d1e...` security lineage, with 93 focused tests in both normal and `GITHUB_ACTIONS=true` modes and a full 3,372-passed local run. It is **no longer the current #2279 successor** because #2279 advanced to `d1e4380...`. Keep it Draft and ordinary/non-force adopt the current foundation before any acceptance claim; its predecessor receipts do not transfer.
- `.github#2269@834d285f90241b4741247408001fd7534ce5a3b0` remains a divergent historical redirect/test-seam lane. Do not close it until a fresh succession audit proves every valid delta/test/doctoring contract is inherited or intentionally superseded.
- `.github#2276` remains the distinct real target-repository permission/canary boundary for the observed `code-scanning/analyses` 403. Capability selection cannot manufacture installation/repository permission. Acceptance requires an unchanged-target canary reading both protected-base and exact-head analyses and completing language pairing.

No Naruon PR copies central workflow source. Naruon records owner identities, waits fail-closed for accepted/released contracts, then ordinary-restacks its own consumers.

### 3.2 Frontend dependency-security owner

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains canonical at exact `509be4c1d9b6c7ba239a108656e2382681a85341`. Its six-workflow GREEN generation and exact-head approval are historical evidence for that generation only. Later vulnerability-database evidence observed protected-base `next`/`sharp` debt already repaired by #1623 source, so Security must be reacquired against the then-current base/database after central execution capacity and workflow authority settle.

### 3.3 Workspace and migration lineage

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the canonical workspace-registry/historical migration owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`, with one authoritative line:

`0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`

No downstream feature may create a parallel Alembic head from protected `develop`; descendants adopt the then-current canonical migration head. [#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains correctly stacked on #1503 for opaque-ID backfill entropy and stays Draft.

### 3.4 Generated provenance lanes

Generated branches that rediscover an owned delta are provenance, not new owners. Current examples include #1724, #1728 and #1730. Their ordinary/non-force reconciliations reduce effective delta to the canonical owner tree or protected tree, and their checks/reviews do not transfer to actual owners.

Repeated source re-entry after zero-delta reconciliation remains a control-plane Gap. Generated writers should perform semantic owner-overlap detection before source mutation and become terminal/read-only after provenance reconciliation. Source-neutral `trigger CI` commits are not acceptance evidence.

### 3.5 Auditable data-hygiene owner

[#1418](https://github.com/ContextualWisdomLab/naruon/pull/1418) remains canonical at exact `87a94a4c2b78f12a61ec699dee9ce081ea3d8578`. Its delimiter repair is locally RED→GREEN, including 11 focused URL tests and 1,830 backend tests / 33 skipped with warnings-as-errors, but current hosted checks and qualifying post-last-push approval remain absent. ADR-0008 remains Proposed and #1590 remains open until protected-tree succession proves complete inheritance.

## 4. UI, localization, and OIDC interaction state

[#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) remains the bounded OIDC pending-feedback owner at exact `85e312360c6342f9bb02b6a6004b2a69599bd4e6`. Its effective delta is `SettingsLayout.tsx`, the rendered pending-feedback regression, and doctoring. jsdom proves per-action pending state, duplicate-click prevention, `aria-busy`, visible pending copy, success cleanup, rejected-logout cleanup and error surfacing. Real-browser keyboard/focus/touch/AT, responsive screenshots, multilingual resource consumption, terminal exact-head hosted evidence and qualifying independent review remain absent.

Canonical localization Gap [#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) owns the product-local **UI Localization Catalog** for KO/EN/JA/ZH/VI/ES/DE/FR: stable `(screen_key, message_key)` identity, normalized DB revisions, immutable published resource versions, placeholder validation, screen-scoped ETag/version reads, UI-copy/ontology-label separation, read-only runtime credentials, and locale-specific Storybook/browser/a11y acceptance. It must begin from the then-current canonical #1503 migration ancestry rather than create a parallel DB head.

**UI Delivery Gate for #1729: FAIL.** Intent is PASS; functional completeness/resilience are PARTIAL; multilingual delivery and buyer-visible exact-head evidence are FAIL.

## 5. LLM and cross-repository contract boundary

Protected `develop` still carries a live governance contradiction: `AGENTS.md` describes central Strix as directly selecting GitHub Models, named fallbacks, Vertex and direct OpenAI modes, while the canonical CWL contract requires all model-backed Actions to request only logical `orchestrator/free` through the gateway and assigns provider/model/group discovery/fallback to contextual-orchestrator.

This defect already has one canonical Naruon owner. Issue [#1548](https://github.com/ContextualWisdomLab/naruon/issues/1548) and PR [#1549](https://github.com/ContextualWisdomLab/naruon/pull/1549) own the governance repair; #1549 remains Draft at exact `9e47f25e256f52f13df267e0383bc3b036ac6f9e` with an effective six-file docs/test/config delta. Do not open a second AGENTS/CLAUDE/ARCHITECTURE LLM-governance writer.

The intended released-owner boundary is unchanged:

- Naruon product/domain truth, authorization, tools and context stay local;
- model-backed Actions request `orchestrator/free` only and do not select provider/model/group or paid fallback;
- contextual-orchestrator owns provider discovery, capability/price/latency/availability/accuracy routing and fallback;
- production consumption requires an immutable released CO API/client/schema identity and otherwise fails closed.

Current contextual-orchestrator protected main is `5665b0ad1e07ffb5e9f8c59e44b6b2a785298013`, but GitHub Releases remains exactly `[]`. Therefore neither that moving protected SHA nor another unpublished owner commit is a production consumer identity. #1549 must refresh its owner-head narrative but must not bind product behavior to mutable main.

## 6. Buyer-visible P0/P1 Gap baseline

| Priority | Gap | Current boundary | Completion evidence |
| --- | --- | --- | --- |
| P0 | Release-train convergence | 279 open PRs; many stacked/provenance/dependency/governance lanes; protected head unchanged | canonical owner inventory, parent-first protected integration, no orphaned valid delta, one immutable RC source SHA |
| P0 | Actions execution capacity | `.github#712` remains open; fresh central snapshot is 531 queued / 4 in-progress and current #1602 evidence lanes are queued | owner health separates current/obsolete runs; obsolete pressure removed without cancelling sole current-head evidence; required lanes receive runner assignment and settle terminally |
| P0 | Central CI/security acceptance | #2040 reconciled; current security/GHAS stack is #2279 `d1e4380...` → #2271 `8aff1a...` → #2275 `f54aeb...`; Pages #2272 still trails the previous #2279 generation; #2269 succession and #2276 permission remain incomplete | terminal hosted checks, current-head independent review, Pages foundation reconciliation, verified succession, real unchanged-target GHAS canary |
| P0 | Dependency-security freshness | #1623 generation GREEN, later Trivy DB sees protected-base debt | revalidate fixed source against then-current base and vulnerability database |
| P0 | Workspace/migration convergence | #1503 source repairs owner-binding RED but is not protected-integrated | one Alembic head, real PostgreSQL fresh + historical upgrade, exact-head CI/security/review |
| P0 | LLM governance contradiction | protected AGENTS still advertises direct provider/model routing; #1548/#1549 own repair | #1549 normal integration after released CO identity + current-base exact-head checks/review |
| P0 | Immutable LLM contract | CO protected main exists but releases are `[]` | immutable owner release, consumer version/digest pin, schema/E2E/model behavior/security/SBOM/provenance |
| P0 | Product/release truth | latest Naruon Release `v0.14.4` is mutable and predates current protected head | code-current docs, version/CHANGELOG, immutable publication, SBOM/provenance/reproducibility/rollback |
| P0 | Connector/provider operability | protocol/writeback/retry foundations exist; full released connector lifecycle remains incomplete | signed installable artifact, enrollment/rotation, capability health, idempotent reconciliation, support evidence |
| P0 | Recovery/customer exit | historical baseline records partial backup/object/portability work, not one buyer round trip | restore/PITR and tenant export→clean-import rehearsal preserving provenance/authorization |
| P1 | Auditable data hygiene | #1418 locally GREEN; hosted checks/current-head approval pending | terminal exact-head checks/review, normal protected integration, verified #1590 succession |
| P1 | UI localization | #1731 is architecture Gap only; current surfaces still embed Korean product copy | versioned 8-locale DB resource/API/cache/publish + Storybook/browser/a11y acceptance |
| P1 | OIDC pending UX | #1729 jsdom repair exists but hosted/browser/multilingual evidence incomplete | terminal exact-head checks/review + browser/AT/responsive evidence + released locale resource consumption |
| P1 | Generated-writer owner lock | repeated generated source re-entry after zero-delta reconciliation | semantic owner-overlap detection and writer-terminal/read-only control with regression evidence |
| P1 | Typed context/scientific differentiation | generic context/search/extractor foundations exist; no protected live STM/TEPP claim | released typed/scientific owner contract with uncertainty/provenance/abstention; no lexical-as-psychometrics marketing |

## 7. Performance, data, and DDD acceptance

- DDD Subdomain/Bounded Context/Context Map and Aggregate/Entity/Value Object/Domain Service/Repository/Event/Invariant naming must match ADR, code, API, DB and tests.
- Aggregates keep transactions minimal. No LLM/network/long computation occurs inside an explicit database transaction. Cross-service SQL is forbidden.
- New persistence uses normalized schemas, descriptive multi-word `snake_case`, explicit ownership/tenant keys, and idempotent item-level UPSERT where appropriate.
- Applicable buyer web/API paths target realistic p95 ≤20 ms. Evidence uses real query/I/O/render/runtime conditions; no sample shrink, measurement exclusion, or unrealistic cache warm-up.
- Performance/security/data-science hot paths are Rust-first where profiling and contract constraints justify it; Python remains a documented boundary only when no practical Rust replacement exists.
- Deprecation and warning output is a defect to root-cause, fix, or explicitly track.

## 8. UI quality contract

Material UI is incomplete without normal/loading/empty/error/permission states, responsive composition, keyboard/focus/touch/a11y evidence, and exact-head screenshot/E2E where buyer-visible. Storybook source-component provenance and rendered Storybook behavior are separate evidence.

Delivery Gate:

- **Intent:** every visual/copy decision maps to a buyer task or product state.
- **Functional completeness:** displayed interactions work and preserve error/recovery semantics.
- **Content:** no template filler, unsupported statistics, fake customer/security/performance claims, or generic CTA copy.
- **Resilience:** mobile/intermediate widths, keyboard focus, loading/empty/error/permission states, and long/localized text do not break the task.
- **Evidence:** assertions bind to current source/resource identity and reproducible browser/test receipts.
- **Distinctiveness:** information architecture and interaction model remain recognizable without generic AI visual defaults.

If one required axis fails, material UI is not complete.

## 9. Release gate and next causal order

Current **Merge/Release Gate: FAIL**.

Current causal order:

1. recover current-head Actions execution capacity through `.github#712`, removing only obsolete/superseded pressure and preserving current-head required evidence;
2. terminalize and independently review #2040 and current #2279; then validate descendants #2271 → #2275 while separately ordinary-forwarding Pages #2272 onto the accepted current foundation;
3. complete #2269 succession audit and #2276 unchanged-target analysis-read canary before claiming central CodeQL/GHAS acceptance;
4. revalidate and normally integrate #1623 against then-current protected ancestry and vulnerability database;
5. integrate #1694 → #1691 and direct-code prerequisites, then #1503 with one healthy migration head and real PostgreSQL fresh/historical evidence;
6. ordinary-restack downstream workspace/Reply-SLA/migration consumers and reacquire invalidated exact-head evidence;
7. after CO publishes an immutable API/client/schema release, finish canonical #1549 governance integration without mutable-owner binding;
8. create one #1731 localization implementation owner from the then-current migration head, publish/test the eight-locale screen-resource contract, then ordinary-adapt #1729;
9. only after an exact integrated protected candidate exists, update version/CHANGELOG and publish an immutable release/package/OCI identity with SBOM, provenance, reproducibility, rollback, and buyer-visible acceptance evidence.

No force push, destructive rebase, self-approval, admin bypass, source-neutral wake commit, synthetic success, stale check/review transfer, duplicate owner, mutable sibling dependency, whole-file conflict overwrite, or gate weakening is part of this path.

## 10. Standards and traceability additions

Phillips, A., & Davis, M. (2009). *Tags for identifying languages* (BCP 47; RFC 5646). RFC Editor. https://doi.org/10.17487/RFC5646

Fielding, R., Nottingham, M., & Reschke, J. (2022). *HTTP semantics* (RFC 9110). RFC Editor. https://doi.org/10.17487/RFC9110

World Wide Web Consortium. (2024). *Web Content Accessibility Guidelines (WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

The archived v1.9 baseline retains the broader protocol, observability, provenance, storage, supply-chain, and UI research bibliography. New implementations must bind cited standards to exact code/API/test evidence rather than cite them decoratively.

## 11. Claim boundary

This baseline is a product and technical decision record, not a certification, market valuation, or assertion that Naruon is already GA. Coverage percentages, PR volume, local test counts, model reviews, and documentation volume are supporting evidence only. Commercial completion requires the end-to-end buyer journey on the exact released identity, with current security, interoperability, recovery, authorization, provenance, operations, and support evidence.