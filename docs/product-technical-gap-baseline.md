# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.88  
**Observed on:** 2026-09-24 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

v2.87 remains audit-visible as blob `1eb9b18a7bcddb61c74e321a3759c787d6061391`. Older snapshots remain reconstructable from Git history and `docs/product-technical-gap-history/`. Historical snapshots and predecessor workflow/review receipts are audit material, not current merge or release authority.

v2.88 records two current owner transitions. First, Search owner [#1603](https://github.com/ContextualWisdomLab/naruon/pull/1603) one-shot repair run `35873031852` completed **SUCCESS** and emitted helper-free exact `d65a34773540147f568fab7aeeaf28835071ede2`. Fresh compare from canonical parent #1623 is ahead 17 / behind 0 with exactly the five Search-owned files; `dashboard-branding.spec.ts` now uses the current `판단 보조 빠른 실행` / `판단 보조 빠른 실행 메뉴` accessible names and exact `맥락 검색` locators. That closes the source-contract finding, not acceptance: the exact helper-free head currently has no normal hosted workflow generation. Dependent [#1760](https://github.com/ContextualWisdomLab/naruon/pull/1760) therefore has a self-removing ordinary/non-force restack staged at `34f21dc101d2ae5d5683c4c698545685c3bf1f5f`; run `35905102850` is nonterminal and final scope must return to exactly its three detail-tab files. Second, Projects #1764's first guarded restack `35873253807` remains a terminal transition RED caused by an over-constrained conflict-set guard; current causal-repair staging `af0adc1c440b160d747f7901b2b76f591ede9b32` and rerun `35904029197` remain nonterminal. Product merge, UI Delivery, Localization Delivery and commercial Release remain fail-closed.

## 1. Evidence hierarchy and commercial release posture

Evidence authority is: exact protected code/migrations/tests/runtime contracts → protected architecture/operations docs → exact current Naruon owner PR source and current-head evidence → live Naruon Issue/Proposed ADR authority → historical snapshots. Pending, queued, cancelled, stale, predecessor-head, skipped-required, source-neutral, author-only, local-only or model-only evidence is not passing evidence.

Protected `develop` remains `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required status contexts. Active rulesets, PR/Issue inventory, current owner heads and releases must be re-read before acceptance; volatile queue telemetry is not frozen into this baseline.

A commercial candidate requires one exact protected integrated head with all required contexts terminal GREEN, current security evidence, zero valid unresolved review findings, qualifying independent post-last-push review, owned production/test/edge coverage at the required threshold, buyer-visible runtime acceptance, immutable publication identity, SBOM/provenance, reproducibility and rollback evidence.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL. Localization Delivery: FAIL.**

## 2. External canonical-owner boundary

Naruon owns its domain truth, UI behavior, product contracts and migration lineage. Other ContextualWisdomLab repositories are consumed only through released/versioned contracts or documented owner paths. Naruon must not source-copy their implementations, query their databases directly, pin mutable external heads as consumer contracts, or reproduce their internal provider/model/group routing.

Relevant optional foundations include `.github` for reusable CI/review/security/release contracts, contextual-orchestrator for LLM capability routing, Keyverse for identity backend, EgressWeave for outbound policy, OriginWeave for browser capability, quarantine-sandbox-runtime for hostile workload isolation, appguardrail for SAST/SARIF and Wardnet for gateway/SOC. If an external owner has no immutable released consumer contract, Naruon remains fail-closed instead of treating a mutable branch head as a release dependency.

Contextual-orchestrator protected `main` is an owner head, not a released Naruon consumer contract: current GitHub Release inventory is empty. Root `AGENTS.md` still contains provider-specific GitHub Models/Strix guidance; that is a governance Gap against the target CO-mediated `orchestrator/free` boundary, but Naruon must not rewrite consumer source against mutable CO source before an immutable owner release exists.

## 3. Product source-owner graph

### 3.1 Backend dependency/security owner

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) is the canonical bounded Starlette TestClient/httpx2 and backend coherent-lock owner. Current adoption staging is `4c5872ac29435f25034cd978a47e8cdcb185813a`, Draft/open. Effective product source still carries direct `httpx2==2.5.0` and resolved `httpcore2==2.5.0`, so Security RED remains live until an ordinary helper-free child adopts the verified graph.

Coherent resolver exact `d166c9208b275ab88895e7711d999c4729a81025` completed Application CI `35844541085` successfully. Resolver job `107127399920`, backend Python 3.14 `107127400083` and frontend `107127400104` were SUCCESS. Artifact `10748790356` was independently checked against GitHub archive digest `sha256:5355320323967e3cd58bdd8f05d1914c63d68790f28bf28b47bfba7fe019942b` and its internal manifest.

The verified artifact contains one coherent five-file graph:

- `backend/requirements.txt` — `87f603d06eb05fa234163003a2feda98f024b80751cc9eb919aedb261136482f`;
- `backend/pyproject.toml` — `faab5edd236153c28a321e431dc1a6d5f99bcaa64f26f21c60222a1db2057365`;
- `backend/requirements-hashes.txt` — `551f6aa4a6a8f1efb7f6259dc63777c40c09b2f520dea217575b94b12178f7d5`;
- `backend/requirements-agent.txt` — `761ceb9f7042ffa9538c5a596ad113a3ee59f27381c4a44d34df82338e5b913a`;
- `backend/uv.lock` — `fa28138f637a2c2baddd528893cfb04be2d9064afcadd538fb7fa5000be7f82b`.

It carries direct `httpx2==2.13.0`, resolved `httpcore2==2.13.0`, the Emscripten-only `httpx2-jsfetch==1.0` branch and identical `httpx2/httpcore2` hash records in core and optional-agent locks. No 2.5.0 TestClient record remains in those generated files. `genai-prices==0.0.71` declares `httpx2>=2.0`, so 2.13.0 remains inside that consumer contract.

Current `4c5872ac...` is temporary one-shot adoption staging, not final product source. Application CI `35860514971` remains nonterminal; Bandit, Semgrep and Docker are GREEN, while Security/CodeQL and helper-free adoption are incomplete. Required order is helper-free five-file adoption → prove no temporary resolver/adopter and no residual 2.5.0 → normal exact-head frozen/core+agent/TestClient/Ruff GREEN → current Security/Trivy, CodeQL and all protected contexts → zero valid findings/threads → independent post-last-push review → protected integration. No stale 2.12 promotion, four-file-only adoption, hand-edited generated locks, source-neutral wake commit or scanner suppression is acceptable.

### 3.2 Frontend dependency/security owner

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) exact `509be4c1d9b6c7ba239a108656e2382681a85341` remains the canonical frontend dependency-security owner, Draft/open. Its bounded scope pins Next.js/eslint-config-next 16.3.4 and Sharp 0.35.4 with structural manifest/lock regressions. After #1565 integrates normally, #1623 must ordinary/non-force adopt accepted backend ancestry and reacquire repository-wide current-database Security without copying #1565 lock data.

[#1752](https://github.com/ContextualWisdomLab/naruon/pull/1752) exact `0b2b4386ac8a2da621602eeaa235bcff4d3b02d4` remains the Dependabot grouping/manifest-scan policy owner. Its historical Security RED belongs to an old dependency graph and must be reacquired after #1565→#1623 integration; this lane must not absorb dependency repair.

### 3.3 Migration/workspace and repository-CI ancestry

[#1694](https://github.com/ContextualWisdomLab/naruon/pull/1694) exact `10f046ee5ea004ec9236d59d3ccfeab3e1a417be` owns bounded fresh-Alembic compatibility. Historical PostgreSQL bootstrap evidence is diagnostic rather than final after dependency ancestry moves.

[#1691](https://github.com/ContextualWisdomLab/naruon/pull/1691) exact `4bf3efd95b8c5002c281a4b47f93e78fc63730de` owns Naruon-local stacked-PR validation and browser-evidence execution. Application CI `35850922236` is terminal **FAILURE**. Backend checked out the exact PR head, installed core plus Noema-agent dependencies and passed Ruff, then failed the canonical database migration step. Frontend passed dependencies, unit tests, lint, build, Chromium and full-product smoke, then reached real `pnpm run test:e2e` and failed product/E2E acceptance. Evidence upload succeeded.

Artifact provenance itself is verified: `10753295906` is `playwright-browser-evidence-4bf3efd95b8c5002c281a4b47f93e78fc63730de-1`, tied to the exact PR head, with GitHub digest `sha256:2d067723be88e1c589febdda36da3a1576487504bf82cbb7cd7d33f6f41dc1df`. The former synthetic-merge-SHA defect is closed; browser/product acceptance is not.

Product/E2E failures are routed to canonical owners: Search #1603→#1760, Projects #1352→only a valid bounded #1764 refinement, and mail/dashboard-flow #1766. #1691 must consume accepted owner repairs rather than copy them or exclude failing specs.

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) exact `9151c75568c582c8147cfee6757cd00a9b4d60b7` remains the canonical workspace registry/document migration owner. Canonical lineage is `0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`; `workspace_id` is authenticated context, not ownership evidence.

Required order is accepted #1565 → combined-security #1623 → final fresh-bootstrap #1694 → canonical product/E2E owners settle → #1691 ordinary-adopts accepted prerequisites/repairs and reacquires exact-head stacked/database/browser/security/review evidence → #1503 ordinary/non-force restack onto one accepted Alembic head.

### 3.4 Utility tools

[#1718](https://github.com/ContextualWisdomLab/naruon/pull/1718) exact `7fb5b9b2578f3a12ac757e1e1b9c5d490722bfd9` is canonical `hash_generator` + `json_formatter` owner. Strict JSON rejects scalar/nested `NaN`, `Infinity` and `-Infinity`, preserves valid formatting and enforces the 100,000-character ceiling.

[#1758](https://github.com/ContextualWisdomLab/naruon/pull/1758) exact `634b2ad34db3d05aa4e00bc2aac0b3a6bcd3709f` preserves password-generator intent on top of #1718. Generated [#1763](https://github.com/ContextualWisdomLab/naruon/pull/1763) exact `4c05ee7c8651068b6240534ea977d2bbb69b0f94` duplicates #1718 hash/JSON and overlaps #1758 password semantics under a different registry/minimum-length/symbol contract. It remains Draft, retargeted onto #1758, until ordinary reconciliation proves a unique password delta or verified zero-delta provenance.

### 3.5 Generated provenance containment and guarded reconciliation

[#1738](https://github.com/ContextualWisdomLab/naruon/pull/1738) generated changes were ordinary-forward corrected to `58e5eae4b5b643861005dd848f3daaf08d32691d`, preserving history while restoring the protected tree; fresh compare is ahead-only with zero changed files. [#1725](https://github.com/ContextualWisdomLab/naruon/pull/1725) was similarly ordinary-forward corrected to `b5690bf885f74fb3f7cd45caf7dfbd6fd27539a6`; exception confidentiality remains with #1612/#1698/#1700 and dependency/security with #1565/#1623.

Generated [#1764](https://github.com/ContextualWisdomLab/naruon/pull/1764) was created directly from `develop` for Projects evidence-review busy feedback although #1352 already owns `aria-busy={correctionSubmitting}` and the loading-vs-save concurrency contract. It is Draft and retargeted to #1352. First staging `9780e2380790fee4ff6d33c70b133d41d6daa71c` ran restack `35873253807`, which completed **FAILURE** in ordinary-adopt before any child commit. The helper incorrectly required the unresolved merge set to equal four paths including `.jules/palette.md`, although #1352 does not change that path. Current staging `af0adc1c440b160d747f7901b2b76f591ede9b32` repairs only that guard: a failed merge must yield a non-empty unresolved set entirely contained in the three canonical Projects overlap files; unexpected conflicts still fail closed. Canonical `.jules` restoration, final exact three-file scope, helper self-removal, remote-head equality and non-force push remain required. Run `35904029197` is nonterminal. Intended final #1352-relative scope remains exactly `ProjectsLayout.tsx`, `ProjectsLayout.accessibility.test.tsx`, and `page.test.tsx`.

Generated [#1765](https://github.com/ContextualWisdomLab/naruon/pull/1765) remains Draft and retargeted onto canonical exception-redaction owner #1612 exact `3da3ae8e60e1bb049f59ae86bfe82db12b7e3cc7`. Temporary staging `5a204f644523bb45a27d421565c42256259e4f73` intends to ordinary-adopt #1612, remove duplicate email/Sentinel ownership and retain only `backend/api/search.py` plus `backend/tests/test_search_exception_redaction_contract.py`, consuming canonical `redacted_exception_info`. The helper is not product scope or transferable evidence.

Zero-delta provenance lanes remain Draft and are not independent merge candidates. Generated dependent refinements remain Draft until ordinary/non-force reconciliation proves their unique delta against the canonical owner. Old receipts do not transfer.

## 4. Material UI owner graph and Delivery Gate

UI acceptance is not inferred from source shape. Material UI requires normal/loading/empty/error/permission/responsive/interaction states, keyboard/focus/touch/accessibility evidence, appropriate screenshots/E2E and exact-head current evidence. shadcn/ui source usage is not Storybook acceptance. Repository-local browser execution is owned by #1691 rather than copied into each UI owner.

### 4.1 Tasks

Canonical Tasks owner [#1463](https://github.com/ContextualWisdomLab/naruon/pull/1463) exact `dd0a2cb55ea1c849a2962a246f6d91bd6ee798e8` owns create/execute active-action identity while preserving mutual exclusion. Browser source holds WebDAV requests open, proves per-action `aria-busy`/spinner/copy identity and distinct request bodies, covers settlement, desktop screenshots and a 390×844 touch/overflow path. Historical Application CI `35815976601` on predecessor `146a3441...` did not run `test:e2e`, so it is not owner-specific browser acceptance. **Tasks Delivery: FAIL** pending accepted #1691 ancestry, inspected current Playwright artifacts, applicable security/code/AT evidence and independent review.

### 4.2 Search

[#1603](https://github.com/ContextualWisdomLab/naruon/pull/1603) exact `d65a34773540147f568fab7aeeaf28835071ede2` is now the helper-free canonical Search owner. One-shot source repair run `35873031852` completed **SUCCESS**. Fresh compare from #1623 is ahead 17 / behind 0 with exactly five Search-owned files: `full-product-ui-smoke.mjs`, `search/page.test.tsx`, `SearchLayout.test.tsx`, `SearchLayout.tsx`, and `dashboard-branding.spec.ts`. Fresh source confirms the shared E2E now uses `판단 보조 빠른 실행`, `판단 보조 빠른 실행 메뉴`, and exact `맥락 검색` accessible-name contracts. The temporary owner-repair workflow is no longer effective source. No normal hosted workflow generation is currently registered on exact `d65a3477...`, so source repair is not exact-head browser/security acceptance.

Bounded refinement [#1760](https://github.com/ContextualWisdomLab/naruon/pull/1760) predecessor `3aaeb30f80048cf3690e924176ee85ba6fc80537` owns shared Button tab semantics and Playwright keyboard/focus/touch acceptance: tab/panel ARIA linkage, wraparound, roving focus, a touch-capable 390×844 context, real `tap()`, minimum 24×24 CSS-pixel targets and overflow checks. Current transition staging `34f21dc101d2ae5d5683c4c698545685c3bf1f5f` uses a branch-scoped self-removing ordinary merge onto parent `d65a3477...`; run `35905102850` is nonterminal. It fails on unresolved conflicts, requires the final parent-relative diff to be exactly `SearchLayout.tsx`, `SearchLayout.test.tsx`, and `search-detail-tabs.spec.ts`, checks remote-head equality and pushes normally without force. The helper is not product scope.

**Search Delivery: FAIL** until #1760 emits a helper-free three-file child on repaired #1603 and the accepted ancestry reacquires exact-head hosted/browser artifacts, applicable AT evidence and independent review.

### 4.3 OIDC settings

[#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) exact `0065a7f4059823ec28573050e6cce9ec381b42d6` remains the bounded OIDC pending-state owner with deferred-promise regression and Playwright keyboard/touch pending/error recovery. **OIDC Delivery: FAIL** while reconciled #1691 ancestry, exact-head required/browser evidence, AT, multilingual resource consumption and independent review remain incomplete.

### 4.4 Projects

[#1352](https://github.com/ContextualWisdomLab/naruon/pull/1352) exact `1b8497f33e1977ce7b963640b63f107510621973` remains the canonical Projects async/busy-state and smoke-supplier owner. It scopes evidence-review `aria-busy` to `correctionSubmitting`, preserves `evidenceLoading` as a disabled prerequisite rather than busy identity, and owns the signed-session/task-timestamp/`/api/projects/candidates` fixture repair exposed by #1691 browser RED.

Generated #1764 remains only a dependent visual refinement. The first guarded restack RED has a bounded causal workflow repair at `af0adc1c...`; run `35904029197` is nonterminal and no helper-free three-file child exists. The unique candidate remains Loader2 feedback while `correctionSubmitting` is true, with pending/settled spinner regression. **Projects Delivery: FAIL** until bounded helper-free ancestry and current browser/touch/AT/review evidence exist.

### 4.5 Mail/dashboard flow

[#1766](https://github.com/ContextualWisdomLab/naruon/pull/1766) exact `705984a381e5ea999c17bae508d35e1bf820c31b` is the bounded one-file regression successor for `frontend/tests/e2e/dashboard-flows.spec.ts`. It restores actual action-item labels, current `답장 초안 생성`, exact `답장 초안` textbox semantics and current `메일 맥락 검색`/context-search action without changing production source or fixture. Its hosted Application CI/Security/Semgrep/Bandit/CodeQL/Docker generation is nonterminal and no qualifying independent post-last-push approval exists. **Mail/dashboard-flow Delivery: FAIL** until real Playwright execution through accepted #1691 ancestry is GREEN and applicable required/security/code/review evidence is current.

## 5. UI Localization Catalog

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) is the single buyer-visible UI Localization Catalog Gap. [#1740](https://github.com/ContextualWisdomLab/naruon/pull/1740) exact `a2ed58691b8cb98abae9ee9acb51a2e4b4877cf9` owns only pure-domain locale/selection/validation policy for KO/EN/JA/ZH/VI/ES/DE/FR; it does not own persistence, HTTP publication, cache/runtime or Storybook UI.

UI translation authority remains separate from ontology/concept labels. Ubiquitous Language is `screen_key`, `message_key`, `locale_code`, immutable `translation_revision`, immutable deployable `resource_version` and screen/locale/version-bound `translation_receipt`.

Persistence must be normalized and versioned rather than one JSON mega-row. Publishing one `resource_version` is the aggregate transaction boundary; all eight release locales must be complete for each active included message and placeholder-schema mismatch fails publication. Read API remains screen-scoped with immutable version/ETag identity and browser cache identity `(screen_key, locale_code, resource_version)`. Do not fetch the whole catalog at login, create per-key waterfalls or mix ontology labels into the UI catalog.

Persistence must descend from final accepted #1503 ancestry. UI acceptance covers all eight locales in Storybook plus real browser normal/loading/empty/error/permission states; keyboard/focus/screen-reader/touch; CJK wrapping/font fallback; Vietnamese diacritics; DE/FR/ES text expansion; mobile/intermediate widths; no locale hydration flash; screenshots tied to exact resource version/head. Repository-local execution comes through accepted #1691 or a verified successor, not per-UI workflow copies.

**Localization Delivery: FAIL.** A DB/API-only implementation is not Delivery PASS.

## 6. DDD, data, performance and operability guardrails

Naruon bounded contexts keep Subdomain/Context Map/Ubiquitous Language and Aggregate/Entity/VO/Domain Service/Repository/Event/Invariant aligned across ADR, code, API, DB and tests. Aggregates use the smallest viable transaction. External/legacy integration uses ACLs; Shared Kernel remains minimal.

Database changes remain normalized to at least 3NF unless a measured exception is documented, avoid hot partition/lock amplification, use item-level idempotency/UPSERT where appropriate and preserve one canonical migration ancestry. Purpose-bound PII handling, anonymization boundaries and CSAP/SOC 2 evidence readiness remain required.

Applicable buyer-facing web/API paths require realistic async k6/E2E measurement with p95 ≤20 ms. If exceeded, profile query/I/O/render/runtime/language/framework before optimization; do not pass by shrinking samples, omitting measured work or unrealistic cache warm-up. Browser acceptance must inspect bundle/heap/DOM/hydration/main-thread/GC when frontend cost is material.

Owned production docstrings/rustdoc, tests and edge-case coverage remain 100% targets. Security/performance runtime and quantitative cores are Rust-first where applicable; Python boundaries require explicit justification and removal conditions. Deprecation warnings are defects to repair, not suppress.

## 7. LLM and agent boundary

All Naruon LLM work consumes a **released** contextual-orchestrator API/client/schema through an Agent boundary. Provider keys, provider/model/group selection, fallback economics and omni-modal routing remain contextual-orchestrator authority. Model-backed GitHub workflows use released central reusable workflow contracts and `orchestrator/free`; Naruon does not hard-code provider groups or copy orchestration internals.

If contextual-orchestrator lacks an immutable released consumer contract, Naruon stays fail-closed for that dependency rather than consuming mutable owner source. Timeout semantics distinguish user cancellation, provider termination and administrative timeout; elapsed wall time alone must not truncate reasoning/stream/tool execution.

## 8. Completion conditions

This baseline is complete only when all of the following are true on one current protected ancestry:

1. #1565 ordinary-adopts the verified five-file backend graph, removes temporary resolver/adopter code and reaches helper-free exact-head required/security/code GREEN plus independent review.
2. #1623 ordinary-adopts accepted backend ancestry and reaches repository-wide current-database Security GREEN.
3. #1694/#1691/#1503 converge onto one accepted migration/CI ancestry with fresh PostgreSQL, exact-head Playwright browser evidence and exact-head security/review evidence; current #1691 Application CI RED must be repaired through canonical migration and product/E2E owners, not by suppressing tests.
4. Material UI owners, including helper-free #1603→restacked #1760 Search, #1352→valid #1764 Projects, #1766 mail/dashboard flow, Tasks and OIDC, reach exact-head terminal acceptance without receipt transfer or duplicate generated ownership.
5. Security/generated reconciliation owners such as #1612→valid #1765 settle on bounded canonical scopes with current exact-head evidence.
6. #1731/#1740 are followed by canonical normalized localization persistence/API/cache/publication and eight-locale Storybook/browser/a11y acceptance.
7. Required external capabilities are consumed only through immutable released/versioned owner contracts.
8. The exact integrated protected head has version/CHANGELOG/tag/package or canonical immutable publication, SBOM/provenance, reproducibility and rollback evidence.

Until then: **Merge/Release Gate = FAIL; UI Delivery Gate = FAIL; Localization Delivery = FAIL.**
