# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.11  
**Observed on:** 2026-09-20 (Asia/Seoul)  
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

Current repository shape is **281 open PRs and 75 open Issues**. The three effective rulesets — `CWL Central required workflows`, `Lock default branch`, and `PR` — are active. The latest GitHub Release is `v0.14.4`, published 2026-06-19, and is `immutable=false`; it is historical publication evidence, not the target commercial immutable release.

## 2. Current commercial classification

Naruon remains a production-oriented pre-GA communication and context control plane. Customer-owned mail, calendar, contact, and file systems remain systems of record. Naruon owns scoped context, policy, recommendation and intent state, provider-command/retry/reconciliation evidence, authorization boundaries, and the buyer-visible decision/action experience.

GA-1 remains **Customer-owned Mail, Calendar, Contact, and File Control Plane**. Individual PR GREEN, high coverage, generated artifacts, or local test volume do not constitute GA. GA requires one protected immutable identity proving the buyer journey, provider interoperability, recovery/customer exit, current security evidence, and an operable support contract.

## 3. Current owner graph and integration gates

### 3.1 Central CI/security control plane

Protected central truth is `.github/main@e6334e229581a918e2f22de18733b76fa65d7e71`, the ordinary merge of #2279 exact `d1e4380c15e948aaf104d46aa134fa614058782a`. The URL/redirect authority is therefore protected ancestry now; descendants must consume that landed owner state rather than wait for #2279 as an open prerequisite.

- `.github#712` remains the canonical organization Actions queue-starvation owner. During this observation window the queue had previously contracted as low as 156 queued / 1 in-progress, but the current fresh observation is **376 queued / 0 in-progress**. This remains volatile and is not evidence of stable runner acquisition; zero in-progress alongside a three-digit queue strengthens the current execution-capacity concern. Preserve sole current-head evidence, remove only obsolete/superseded pressure through the owner path, and do not blind-rerun unchanged heads.
- `.github#2279` is **merged**. Protected merge commit `e6334e229581a918e2f22de18733b76fa65d7e71` has parents prior `main@64aa08d7fa487deacd41c761c36277ca68cab6c9` and exact owner head `d1e4380c15e948aaf104d46aa134fa614058782a`. Initial GitHub REST authority validation, no-redirect production openers, bearer non-forwarding, executable G-17 ancestry validation, and owner-qualified foreign Semgrep evidence are now protected central source authority. Do not continue to model #2279 as a pending foundation PR.
- `.github#2040@ecc9e1d11149ae44ec4f8389e4ac72a08ba45ba7` had completed path-wise reconciliation against the previous protected main and locally verified **496 focused passed; 3,404 passed / 28 skipped / 40 subtests**. The #2279 merge moved protected main again. Its PR metadata still records the preceding `base_sha=64aa08d7...`; #2040 therefore needs another ordinary/non-force path-wise adoption of the newly landed central URL/redirect authority before exact-head acceptance. Its previous reconciliation evidence remains source history, not acceptance for the new base.
- `.github#2271@a0e1424de409ec474e7bc6e9f91a9e99b8a0915e` is the CodeQL dispatch repository-identity descendant. It has ordinary two-parent restacked the previously reviewed owner generation onto protected `main@e6334e...`; the tree remains byte-identical to the prior reviewed generation and the protected-main compare is 8 ahead / 0 behind across exactly three owned paths. It is Ready for review, not merge-accepted: fresh Python Security, Semgrep, CodeQL and Security runs remain queued/nonterminal and a qualifying current-head approval is still required.
- `.github#2275@572cfed270ae3b3cd38faca4d97ce028093e5373` is the GHAS analysis-read capability-selector descendant of current #2271 `a0e1424...`. Its ordinary two-parent successor retains the prior selector tree byte-for-byte while recording current #2271 ancestry. It requires the exact `code-scanning/analyses?per_page=1&tool_name=CodeQL` endpoint and reviewed headers; focused stack remains **165 passed**, full local suite **3,378 passed / 28 skipped / 40 subtests**. Fresh CodeQL/Semgrep/Security runs remain queued. Acceptance still requires #2271 acceptance, #2276 real target permission, terminal exact-head checks and qualifying independent approval.
- `.github#2272@cd3b41b8989e096d1ee375d332347c8bb819acf9` has ordinary-forward adopted complete #2279 `d1e4380...` while preserving the Pages caller-input shell boundary and SAST compatibility work. Its exact tree verified **94 focused passed**, **94 passed with `GITHUB_ACTIONS=true`**, and **3,373 passed / 28 skipped / 40 subtests**. Keep Draft until fresh exact-head Pages/security/SAST/CodeQL/runtime evidence and independent review are terminal.
- `.github#2269@834d285f90241b4741247408001fd7534ce5a3b0` remains historical redirect/test-seam lineage. Do not close it until a fresh succession audit proves every valid delta/test/doctoring contract is present in protected `main@e6334e...` or an accepted successor.
- `.github#2276` remains the distinct real target-repository permission/canary boundary for the observed `code-scanning/analyses` 403. Capability selection cannot manufacture installation/repository permission. Acceptance requires an unchanged-target canary reading both protected-base and exact-head analyses and completing language pairing.

No Naruon PR copies central workflow source. Naruon records owner identities, waits fail-closed for accepted/released contracts, then ordinary-restacks its own consumers.

### 3.2 Frontend dependency-security owner

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains canonical at exact `509be4c1d9b6c7ba239a108656e2382681a85341`. Its six-workflow GREEN generation and exact-head approval are historical evidence for that generation only. Later vulnerability-database evidence observed protected-base `next`/`sharp` debt already repaired by #1623 source, so Security must be reacquired against the then-current base/database after central execution capacity and workflow authority settle. Its live PR-state has been corrected to treat #2279 as landed and #2040 as re-diverged rather than waiting on the old central graph.

### 3.3 Backend dependency-security and TestClient lock owner

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) is the direct Starlette TestClient/httpx2 foundation at exact `52dfc863d1a5d6e4e80b6366f719dd09f2aa6172`. It pins `httpx2==2.5.0`, removes only the matching Starlette fallback-warning suppression, and proves TestClient runtime selection under warnings-as-errors. Its exact generation has Application CI, Security, Semgrep and Bandit success, while CodeQL remains a fail-closed central-control failure, Docker is queued, and qualifying independent approval is absent.

[#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) is the dependent broad backend-Python dependency lane at exact `d096a5c235d2c1d8b5a5751cdd4e2c8cbba17c21`, stacked on #1565 and currently Draft/non-mergeable. Its current source updates `aiosmtplib 5.1.2 → 5.1.3` but does not regenerate `backend/uv.lock` and, if taken wholesale, drops #1565's direct `httpx2` contract. This is a repair finding, not a reason to discard the branch.

The `aiosmtplib 5.1.3` delta is security-material and must survive reconciliation. Upstream v5.1.3 explicitly follows CVE-2026-53533 / GHSA-v3q9-hj7j-63hq by rejecting whitespace or angle brackets outside a quoted local part in SMTP address commands so caller-controlled input cannot smuggle extra ESMTP parameters; `sendmail` validates all addresses before command emission. The same release hardens `HELO`/`EHLO` hostname input, command/response synchronization, connection-lock cleanup and related lifecycle behavior. #1565's current base manifest still pins `aiosmtplib==5.1.2`, so this is a real current-source security Gap rather than a decorative version refresh.

The minimum valid successor preserves both owners' contracts: keep #1565's direct reviewed `httpx2` pin and warnings-as-errors TestClient behavior, preserve `aiosmtplib==5.1.3`, regenerate `pyproject.toml`, plain requirements, hash-locked requirements and `uv.lock` as one coherent graph, add focused hostile SMTP address/hostname and relevant connection-lifecycle regression evidence, and reacquire exact-head backend/API/migration/security checks plus independent review. Do not create a second dependency writer unless #1685 explicitly delegates or loses this security slice.

### 3.3.1 LLM provider error-confidentiality owner

[#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) is the bounded LLM provider error-confidentiality repair at exact `9d9d5e0b4bde3febb7cef0e925e493c4fc16cd04`, currently Draft/open/mergeable with an effective three-file delta. Its generated first head `41644c0d51801547a4b408e23f7cad029c989c0d` correctly removed provider exception text from raised `LLMServiceError` but replaced direct log interpolation with `logger.error(..., exc_info=True)`, which still rendered provider-controlled exception text and traceback into the log sink.

The ordinary-forward production repair records only fixed event text plus bounded `operation` and exception-class metadata, logs no exception string/traceback, and raises fixed `LLMServiceError` messages `from None`. A hostile-canary regression covers extraction, translation, standard OpenAI-compatible drafting and Ollama native drafting; it asserts the exact generic service message, absence of provider text in rendered logs, suppressed cause rendering, absence of `exc_info`, bounded metadata, and applicable client cleanup. The generated task-specific `.jules/sentinel.md` guidance was removed after the source fix and the file is byte-for-byte restored to protected-base blob `9208f58b118f11d0983c3a62df96916ec61a3384`.

After the stronger reviewed `7e8321bb...` generation, generated commit `1da2457c0e8cfa71a620515a93611b97d4aad200` arrived as an ordinary child. It left production source and the four-path regression intact but partially rolled back doctoring by deleting the review-finding verification, explicit four-path evidence, generated-writer cleanup record and exact repair lineage. Ordinary-forward `9d9d5e0...` retains that intervening commit in ancestry and restores the stronger TRACEABILITY record without product-source churn. Predecessor receipts do not transfer.

The first CodeRabbit review correctly required four-path regression coverage but incorrectly required traceback-aware `exc_info`; the valid coverage request was implemented and the unsafe logging recommendation was rejected with OWASP-based doctoring. The old thread is resolved/outdated. Exact `9d9d5e0...` Application CI, Security, Semgrep, Bandit, CodeQL and Docker runs are currently queued, and no qualifying independent post-last-push approval exists. No local PASS is claimed because the current automation execution environment cannot run the repository test stack. Keep Draft until exact-head hosted acceptance is real.

### 3.4 Workspace and migration lineage

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the canonical workspace-registry/historical migration owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`, with one authoritative line:

`0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`

No downstream feature may create a parallel Alembic head from protected `develop`; descendants adopt the then-current canonical migration head.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains correctly retargeted to #1503 for opaque-ID backfill entropy. An intervening Sentinel commit `103a52c9fad2081cf6ff6d10d8e9c73bea7395e4` retained a valid prompt-template assertion but deleted the dedicated 42-line entropy regression and 33-line doctoring/TRACEABILITY record. Ordinary children `f501b09af6086de4e9a79ac77488622eb67fcd63` and exact current `2ac48fb7e591827804ba8e7e911f211b0c134ddf` restore those artifacts byte-for-byte while retaining the intervening commit in ancestry. The effective delta remains five files: the historical migration, bootstrap generation, bootstrap expectations, focused regression, and doctoring. #1727 stays Draft; it is mechanically mergeable but **ahead 6 / behind 37** relative to #1503's shared protected merge base, and exact `2ac48fb...` currently has no workflow runs or formal reviews/threads. No predecessor receipt transfers.

### 3.5 Generated provenance lanes

Generated branches that rediscover an owned delta are provenance, not new owners. Current examples include #1724, #1728 and #1730. Their ordinary/non-force reconciliations reduce effective delta to the canonical owner tree or protected tree, and their checks/reviews do not transfer to actual owners.

Repeated source re-entry after zero-delta reconciliation or deletion of owner tests/doctoring remains a control-plane Gap. #1727's `103a52c9...` regression is one current example: a generated writer kept one narrow assertion while removing broader executable coverage and traceability. #1733 demonstrates both forms of the failure: the initial generated security guidance recommended `exc_info=True`, which would have retained provider-controlled exception text in another sink, and a later generated child `1da2457...` partially rolled back the stronger owner doctoring after the source/test repair already existed. Generated writers should perform semantic owner-overlap and threat-boundary verification before source mutation, and task-specific self-modifying guidance should be removed once the durable source/test/doctoring fix exists. Source-neutral `trigger CI` commits are not acceptance evidence.

### 3.6 Auditable data-hygiene owner

[#1418](https://github.com/ContextualWisdomLab/naruon/pull/1418) remains canonical at exact `87a94a4c2b78f12a61ec699dee9ce081ea3d8578`. Its delimiter repair is locally RED→GREEN, including 11 focused URL tests and 1,830 backend tests / 33 skipped with warnings-as-errors, but current hosted checks and qualifying post-last-push approval remain absent. ADR-0008 remains Proposed and #1590 remains open until protected-tree succession proves complete inheritance.

### 3.7 OpenSSF governance evidence owner

Issue [#1178](https://github.com/ContextualWisdomLab/naruon/issues/1178) and PR [#1732](https://github.com/ContextualWisdomLab/naruon/pull/1732) own the bounded OpenSSF Best Practices evidence lane. #1732 exact `a8e83d6701e4195e984d2e72de29b056cae55268` repairs the private vulnerability-reporting URL and adds a truthful enrollment packet, but remains Draft.

OpenSSF Best Practices Passing is for FLOSS projects and requires every MUST/MUST NOT criterion, including `floss_license`, to be satisfied. Naruon's current proprietary license is therefore a **legal/business eligibility blocker** to Passing unless an authorized copyright-holder/legal/business licensing decision changes that boundary. Engineering must not fabricate a project id, badge, waiver, or remediation date. This lane is governance evidence, not a reason to weaken product gates or a mandatory release dependency unless the business explicitly chooses OpenSSF Passing as a release criterion.

The current effective change-control contract must also be represented accurately: ruleset `17214772` requires one approving review, stale-review dismissal, last-push approval and resolved threads; inherited `18156473` requires one approving review, stale-review dismissal and resolved threads but currently has `require_last_push_approval=false`. The integrated contract still requires last-push approval because `17214772` is active.

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
| P0 | Release-train convergence | 281 open PRs; many stacked/provenance/dependency/governance lanes; protected head unchanged | canonical owner inventory, parent-first protected integration, no orphaned valid delta, one immutable RC source SHA |
| P0 | Actions execution capacity | `.github#712` remains open; current snapshot is 376 queued / 0 in-progress after earlier contraction to 156/1; runner acquisition remains volatile | owner health separates current/obsolete runs; obsolete pressure removed without cancelling sole current-head evidence; required lanes receive runner assignment and settle terminally |
| P0 | Central CI/security acceptance | protected main includes #2279 at `e6334e...`; #2040 needs current-main readoption; descendant stack is #2271 `a0e1424...` → #2275 `572cfed...`; Pages #2272 `cd3b41...` has adopted #2279; #2269 succession and #2276 permission remain incomplete | #2040 current-main reconciliation, descendant terminal hosted checks/current-head review, verified #2269 succession, real unchanged-target GHAS canary |
| P0 | Dependency-security freshness | frontend #1623 needs current vulnerability-DB revalidation; backend #1565→#1685 must preserve `httpx2` and the `aiosmtplib 5.1.3` SMTP-injection hardening while rebuilding one lock/hash graph | current-base vulnerability scans + coherent backend manifest/uv/hash locks + hostile SMTP/TestClient regressions + exact-head CI/security/review |
| P0 | LLM provider error confidentiality | #1733 exact `9d9d5e0...` preserves the four-path secret-canary repair and restores TRACEABILITY after generated child `1da2457...` partially rolled the doctoring back; hosted exact-head evidence and independent approval are pending | current-head Application CI/security/Semgrep/Bandit/CodeQL/Docker terminal success + zero valid review findings + qualifying post-last-push approval |
| P0 | Workspace/migration convergence | #1503 source repairs owner-binding RED but is not protected-integrated; #1727 entropy child repaired a generated test/doctoring deletion and remains Draft | one Alembic head, real PostgreSQL fresh + historical upgrade, exact-head CI/security/review, ordinary descendant adoption |
| P0 | LLM governance contradiction | protected AGENTS still advertises direct provider/model routing; #1548/#1549 own repair | #1549 normal integration after released CO identity + current-base exact-head checks/review |
| P0 | Immutable LLM contract | CO protected main exists but releases are `[]` | immutable owner release, consumer version/digest pin, schema/E2E/model behavior/security/SBOM/provenance |
| P0 | Product/release truth | latest Naruon Release `v0.14.4` is mutable and predates current protected head | code-current docs, version/CHANGELOG, immutable publication, SBOM/provenance/reproducibility/rollback |
| P0 | Connector/provider operability | protocol/writeback/retry foundations exist; full released connector lifecycle remains incomplete | signed installable artifact, enrollment/rotation, capability health, idempotent reconciliation, support evidence |
| P0 | Recovery/customer exit | historical baseline records partial backup/object/portability work, not one buyer round trip | restore/PITR and tenant export→clean-import rehearsal preserving provenance/authorization |
| P1 | Auditable data hygiene | #1418 locally GREEN; hosted checks/current-head approval pending | terminal exact-head checks/review, normal protected integration, verified #1590 succession |
| P1 | UI localization | #1731 is architecture Gap only; current surfaces still embed Korean product copy | versioned 8-locale DB resource/API/cache/publish + Storybook/browser/a11y acceptance |
| P1 | OIDC pending UX | #1729 jsdom repair exists but hosted/browser/multilingual evidence incomplete | terminal exact-head checks/review + browser/AT/responsive evidence + released locale resource consumption |
| P1 | Generated-writer owner lock | generated source re-entry has deleted executable evidence (#1727), recommended an unsafe log-sink substitute, and later rolled back owner TRACEABILITY (#1733) | semantic owner/threat-boundary detection, durable source/test/doctoring transfer, and terminal/read-only generated guidance after repair |
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

1. continue `.github#712` execution-capacity repair without blind unchanged-head reruns; the queue remains volatile and currently has no in-progress run in the fresh snapshot;
2. ordinary/non-force reconcile #2040 onto protected `main@e6334e...`, preserving both its scheduler contracts and the now-landed #2279 URL/redirect authority, then reacquire exact-head hosted evidence and qualifying independent review;
3. terminalize/review current-main-restacked #2271 `a0e1424...` → #2275 `572cfed...`, and terminalize/review Pages #2272 `cd3b41...` separately;
4. complete #2269 succession audit and #2276 unchanged-target analysis-read canary before claiming central CodeQL/GHAS acceptance;
5. revalidate and normally integrate frontend dependency-security #1623 against the then-current protected ancestry and vulnerability database;
6. integrate #1565's warning-free Starlette/httpx2 foundation, then ordinary/non-force reconcile #1685 so the combined dependency graph preserves both direct `httpx2` and `aiosmtplib==5.1.3`; regenerate plain/hash/uv locks and run focused SMTP hostile-input/lifecycle plus backend/API/security evidence;
7. terminalize and independently review #1733 exact `9d9d5e0...`, preserving fixed-message/bounded-metadata error confidentiality, four-path hostile-canary evidence and the restored TRACEABILITY record; no traceback/provider-text logging or generated doctoring rollback may return;
8. integrate #1694 → #1691 and direct-code prerequisites, then #1503 with one healthy migration head and real PostgreSQL fresh/historical evidence; ordinary-adopt #1727's bounded entropy delta on the then-current owner tree and reacquire evidence;
9. ordinary-restack downstream workspace/Reply-SLA/migration consumers and reacquire invalidated exact-head evidence;
10. after CO publishes an immutable API/client/schema release, finish canonical #1549 governance integration without mutable-owner binding;
11. create one #1731 localization implementation owner from the then-current migration head, publish/test the eight-locale screen-resource contract, then ordinary-adapt #1729;
12. only after an exact integrated protected candidate exists, update version/CHANGELOG and publish an immutable release/package/OCI identity with SBOM, provenance, reproducibility, rollback, and buyer-visible acceptance evidence.

OpenSSF #1178/#1732 proceeds as a separate governance/legal lane. It does not enter the release-critical causal chain unless an authorized business decision explicitly makes a Passing badge a release criterion.

No force push, destructive rebase, self-approval, admin bypass, source-neutral wake commit, synthetic success, stale check/review transfer, duplicate owner, mutable sibling dependency, whole-file conflict overwrite, or gate weakening is part of this path.

## 10. Standards and traceability additions

Phillips, A., & Davis, M. (2009). *Tags for identifying languages* (BCP 47; RFC 5646). RFC Editor. https://doi.org/10.17487/RFC5646

Fielding, R., Nottingham, M., & Reschke, J. (2022). *HTTP semantics* (RFC 9110). RFC Editor. https://doi.org/10.17487/RFC9110

World Wide Web Consortium. (2024). *Web Content Accessibility Guidelines (WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

Open Source Security Foundation. (n.d.). *OpenSSF Best Practices Badge criteria: Passing*. https://www.bestpractices.dev/en/criteria?details=true&rationale=true

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation: UUID functions*. PostgreSQL Documentation. https://www.postgresql.org/docs/current/functions-uuid.html

PyCQA. (2026). *B608: hardcoded_sql_expressions*. Bandit documentation. https://bandit.readthedocs.io/en/latest/plugins/b608_hardcoded_sql_expressions.html

Cole, J. (2026, September 8). *aiosmtplib v5.1.3* [Software release]. GitHub. https://github.com/cole/aiosmtplib/releases/tag/v5.1.3

OWASP Foundation. (n.d.). *Logging cheat sheet*. OWASP Cheat Sheet Series. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

OWASP Foundation. (n.d.). *Microservices security cheat sheet*. OWASP Cheat Sheet Series. https://cheatsheetseries.owasp.org/cheatsheets/Microservices_Security_Cheat_Sheet.html

The archived v1.9 baseline retains the broader protocol, observability, provenance, storage, supply-chain, and UI research bibliography. New implementations must bind cited standards to exact code/API/test evidence rather than cite them decoratively.

## 11. Claim boundary

This baseline is a product and technical decision record, not a certification, market valuation, or assertion that Naruon is already GA. Coverage percentages, PR volume, local test counts, model reviews, and documentation volume are supporting evidence only. Commercial completion requires the end-to-end buyer journey on the exact released identity, with current security, interoperability, recovery, authorization, provenance, operations, and support evidence.