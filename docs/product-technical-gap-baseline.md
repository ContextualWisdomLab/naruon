# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.81  
**Observed on:** 2026-09-23 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

v2.80 remains audit-visible as blob `639befd20c28cf80ab779fd57f0781cbc47051bb`; v2.79 remains audit-visible as blob `c6dce4bbaffc2662b090972838cfec1e41e32a56`; v2.78 remains audit-visible as blob `dc77bf49739027c89562806c8034dfa70575882d`; v2.77 remains audit-visible as blob `8f932a5a9a2d9db62901a57d1e73c7a1d9300b83`. Older snapshots remain reconstructable from Git history and `docs/product-technical-gap-history/`. Historical snapshots and predecessor workflow/review receipts are audit material, not current merge or release authority.

v2.81 does not claim a new protected product release. It makes the source ledger current with two verified live findings that v2.80 only described in PR metadata: the backend dependency owner now requires a coherent **five-file** 2.13.0 graph because the optional Noema-agent lock participates in the same `--require-hashes` installation, and the repository-local browser owner has reproduced real Playwright failures while also proving that plain `github.sha` on `pull_request` produced synthetic-merge rather than exact-head evidence. Product merge, UI Delivery, Localization Delivery and commercial Release gates remain fail-closed.

## 1. Evidence hierarchy and commercial release posture

Evidence authority is: exact protected code/migrations/tests/runtime contracts → protected architecture/operations docs → exact current Naruon owner PR source and current-head evidence → live Naruon Issue/Proposed ADR authority → historical snapshots. Pending, queued, cancelled, stale, predecessor-head, skipped-required, source-neutral, author-only, local-only or model-only evidence is not passing evidence.

Protected `develop` is `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required status contexts. Active rulesets, PR/Issue inventory, current owner heads and releases must be re-read before acceptance; volatile queue telemetry is not frozen into this baseline.

A commercial candidate requires one exact protected integrated head with all required contexts terminal GREEN, current security evidence, zero valid unresolved review findings, qualifying independent post-last-push review, owned production/test/edge coverage at the required threshold, buyer-visible runtime acceptance, immutable publication identity, SBOM/provenance, reproducibility and rollback evidence.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL. Localization Delivery: FAIL.**

## 2. External canonical-owner boundary

Naruon owns its domain truth, UI behavior, product contracts and migration lineage. Other ContextualWisdomLab canonical repositories are consumed only through released/versioned contracts or documented owner paths. Naruon must not source-copy their implementations, query their databases directly, pin mutable external heads as consumer contracts, or reproduce their internal provider/model/group routing.

Relevant optional foundations include `.github` for reusable CI/review/security/release contracts, contextual-orchestrator for LLM capability routing, Keyverse for identity backend, EgressWeave for outbound policy, OriginWeave for browser capability, quarantine-sandbox-runtime for hostile workload isolation, appguardrail for SAST/SARIF and Wardnet for gateway/SOC. If an external owner has no immutable/released consumer contract, Naruon remains fail-closed rather than treating its mutable branch head as a release dependency.

## 3. Product source-owner graph

### 3.1 Backend dependency/security owner

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) is the canonical bounded Starlette TestClient/httpx2 and backend coherent-lock owner. Current exact head is `d166c9208b275ab88895e7711d999c4729a81025`, Draft/open.

The AnyIO 4.14.2 repair remains valid. Effective product source still contains direct `httpx2==2.5.0` and resolved `httpcore2==2.5.0`, so the owner-introduced Security RED remains live.

Historical resolver artifact `10724734967` for 2.12.0 remains reproducibility evidence only. Previous 2.13.0 resolver exact `60caa40c6f2d04e55eb8d92ee67b5cce3d09d6f7` completed Application CI `35828382074` successfully; backend, frontend and resolver job `107075084720` were GREEN. Artifact `10741272245` was recovered and independently SHA-256 verified for `backend/requirements.txt`, `backend/pyproject.toml`, `backend/requirements-hashes.txt` and `backend/uv.lock`, and its generated graph contains direct `httpx2==2.13.0`, resolved `httpcore2==2.13.0` and the Emscripten-only `httpx2-jsfetch==1.0` branch.

That four-file artifact is **not** a coherent CI dependency graph. Application CI installs `backend/requirements-hashes.txt` and `backend/requirements-agent.txt` together under `--require-hashes`, while the optional Noema-agent lock still pins `httpx2==2.5.0` and `httpcore2==2.5.0`. Upstream `genai-prices==0.0.71` declares `httpx2>=2.0`, so the defect is missing coherent lock regeneration/evidence, not an incompatibility with 2.13.0.

Current exact `d166c920...` therefore keeps the resolver read-only and expands the evidence boundary to **five dependency files**. It derives optional-agent `httpx2/httpcore2` records from the generated core hash records, rejects residual 2.5.0, performs one combined `pip --dry-run --ignore-installed --require-hashes` over core plus optional-agent locks, and includes `requirements-agent.txt` in the binary diff, SHA-256 manifest and resolver artifact. The workflow keeps `contents: read`, non-persistent checkout credentials, pinned Python 3.14/`uv==0.10.0`, no repository write permission and no commit/push path.

Current Application CI `35844541085` is registered for `d166c920...` but is nonterminal. Product bytes have not been adopted. Required order is: five-file resolver GREEN → recover and independently hash-verify all five generated dependency files → ordinary/non-force coherent adoption plus matching TestClient structural contract/CHANGELOG/doctoring → remove temporary resolver/source-fix logic → helper-free `uv lock --check`, frozen core+agent install, warnings-as-errors TestClient regression and Ruff → fresh Security/Trivy, CodeQL, all required contexts, zero valid findings/threads and qualifying independent post-last-push review → normal protected integration.

No stale 2.12 artifact promotion, four-file-only adoption, hand-edited lock/hash text or scanner suppression is acceptable.

### 3.2 Frontend dependency/security owner

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the canonical frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`, Draft/open. Its reviewed scope pins Next.js/eslint-config-next 16.3.4 and resolved Sharp 0.35.4 with structural manifest/lock regressions. Its current-database Security evidence has no owned Next.js/Sharp finding; remaining repository-wide findings are inherited backend debt.

#1623 must not copy #1565 lock data. After #1565 integrates normally, #1623 ordinary/non-force adopts the accepted backend delta without changing its reviewed frontend contract and reacquires repository-wide current-database Security on the combined exact head.

[#1752](https://github.com/ContextualWisdomLab/naruon/pull/1752) exact `0b2b4386ac8a2da621602eeaa235bcff4d3b02d4` remains the sole Naruon Dependabot grouping/manifest-scan policy owner. It bounds wildcard groups to patch updates, keeps `aiosmtplib` independent and excludes dedicated backend/connector manifests from the root pip scan. Its historical Security RED belongs to the old dependency graph and must be reacquired after accepted #1565→#1623 integration; the policy lane must not absorb dependency repair.

### 3.3 Migration/workspace and repository-CI ancestry

[#1694](https://github.com/ContextualWisdomLab/naruon/pull/1694) exact `10f046ee5ea004ec9236d59d3ccfeab3e1a417be` owns the bounded fresh-Alembic compatibility repair. Historical PostgreSQL bootstrap evidence remains diagnostic rather than final acceptance after dependency ancestry moves.

[#1691](https://github.com/ContextualWisdomLab/naruon/pull/1691) exact `4bf3efd95b8c5002c281a4b47f93e78fc63730de` owns Naruon-local stacked-PR validation and browser-evidence execution. Its first browser-execution generation at predecessor `7970f7e56bf96140a28b69e762b8d33509036408` completed Application CI `35833386660` with **FAILURE**, which is useful reality evidence rather than a reason to weaken the gate.

Backend installed core and Noema-agent dependencies and passed Ruff before canonical database migration failed. Frontend passed unit tests, lint, build, Chromium installation and full-product smoke, then failed at `pnpm run test:e2e`. The `if: always()` upload succeeded as artifact `10744123151`; trace/screenshot inspection exposed real current-contract drift: stale `AI 빠른 실행` versus protected `판단 보조 빠른 실행`, missing `/api/projects/candidates` fixture causing the Projects source-load error state, an ambiguous non-exact `맥락 검색` locator, and stale mail-flow assertions such as `2개 실행 항목` / `메일 검색`. Those are product/E2E owner findings; #1691 must not exclude the specs or weaken the assertions.

The same receipt exposed an owner-local provenance defect. Artifact identity used synthetic merge SHA `b63342a9...` rather than exact PR head `7970f7e5...` because `pull_request` plain `github.sha` and default checkout target the synthetic merge ref. Reality-RED `9b27f0ca29d3e64860114047e1e148856afe628e` captures that contract. Exact current `4bf3efd9...` now checks out `${{ github.event.pull_request.head.sha || github.sha }}` in backend and frontend and uses the same expression in Playwright artifact identity, while retaining non-persistent credentials, actual `pnpm run test:e2e -- --reporter=line,html`, pinned `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`, `if: always()` and both Playwright report/test-result paths.

Current exact-head runs for `4bf3efd9...` are registered but nonterminal; no predecessor browser receipt is promoted to exact-head GREEN. #1691 must still consume released central CI contracts rather than copy central workflow source. After accepted dependency/bootstrap prerequisites it must ordinary-adopt them and reacquire stacked-trigger/database/browser/security/review evidence on one unchanged exact head.

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) exact `9151c75568c582c8147cfee6757cd00a9b4d60b7` remains the canonical workspace registry/document migration owner. `workspace_id` is an opaque authenticated claim, never ownership evidence. Canonical migration lineage remains `0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`.

Do not restack #1503 merely to chase a moving prerequisite branch. Required order is accepted #1565 → combined-security #1623 → final fresh-bootstrap #1694 → fresh exact-head stacked/browser-CI #1691 → ordinary/non-force #1503 restack onto one accepted Alembic head with fresh PostgreSQL migration/security/review evidence.

### 3.4 Utility tools

[#1718](https://github.com/ContextualWisdomLab/naruon/pull/1718) exact `7fb5b9b2578f3a12ac757e1e1b9c5d490722bfd9` is the canonical `hash_generator` + `json_formatter` owner. The strict-JSON repair rejects scalar/nested `NaN`, `Infinity` and `-Infinity`, preserves valid formatting and enforces the 100,000-character ceiling. Current-head independent review is approved; Application CI, Bandit, Semgrep and Docker are GREEN. Security is inherited dependency RED and CodeQL settlement remains incomplete.

[#1758](https://github.com/ContextualWisdomLab/naruon/pull/1758) exact `634b2ad34db3d05aa4e00bc2aac0b3a6bcd3709f` remains the canonical password-intent successor stacked on #1718; duplicate JSON ownership must disappear only after accepted ancestry is available.

Generated [#1763](https://github.com/ContextualWisdomLab/naruon/pull/1763) exact `4c05ee7c8651068b6240534ea977d2bbb69b0f94` is not a new three-tool owner. It duplicates #1718 hash/JSON and overlaps #1758 password intent with a different registry identity/minimum-length/symbol contract. It has been retargeted to the #1758 branch and kept Draft. After accepted #1718→#1758 ancestry, ordinary/non-force reconciliation must prove whether any unique password delta remains; otherwise it may only become verified zero-delta provenance. No generated coverage claim is accepted as production/test/edge evidence.

## 4. Material UI owner graph and Delivery Gate

UI acceptance is not inferred from source shape. Material UI requires normal/loading/empty/error/permission/responsive/interaction states, keyboard/focus/touch/accessibility evidence, appropriate screenshots/E2E and exact-head current evidence. shadcn/ui source usage is not Storybook acceptance.

Repository-local browser execution is owned by #1691 rather than copied into each UI owner. An E2E source file, installed browser binary or passing `full:smoke` is not browser acceptance unless the owner-specific Playwright path actually ran on the exact head and its artifacts are inspectable.

### 4.1 Tasks

Canonical Tasks owner [#1463](https://github.com/ContextualWisdomLab/naruon/pull/1463) is exact `146a34411392e2b2bdf48d27cca0576275d5272e`, tree `11929d7e8675d9240e132efb495a62b31f616009`. It owns create/execute active-action identity while preserving mutual exclusion. Browser acceptance source holds WebDAV requests open, proves per-action `aria-busy`/spinner/copy identity and distinct request bodies, covers settlement, desktop screenshots and a 390×844 touch/overflow path.

Application CI `35815976601` is terminal SUCCESS on this exact Tasks head; Bandit `35815976662`, Semgrep `35815976582` and Docker `35815976808` are also SUCCESS. However, that frontend job ran unit/lint/build and `pnpm run full:smoke` after installing Chromium; it did **not** invoke `pnpm run test:e2e`, so `tasks-pending-action.spec.ts` was not executed by that receipt. Security and CodeQL remain incomplete. This is the reproduced CI acceptance defect now owned by #1691.

Generated #1735 and #1759 remain zero-effective-delta Draft provenance over the canonical Tasks owner and may not transfer receipts.

**Tasks Delivery: FAIL** until accepted exact-head #1691 browser-execution ancestry exists and the canonical unchanged Tasks head has inspectable exact-head Playwright artifacts, applicable terminal security/code evidence, AT evidence, zero valid review findings and an independent post-last-push approval.

### 4.2 Search

[#1603](https://github.com/ContextualWisdomLab/naruon/pull/1603) exact `af2efcef6a6dfeedbd13a69865b5a8fdd7f1fd10` remains canonical Search owner. Bounded refinement [#1760](https://github.com/ContextualWisdomLab/naruon/pull/1760) exact `3aaeb30f80048cf3690e924176ee85ba6fc80537` adds shared Button tab semantics plus real-browser keyboard/focus acceptance for Left/Right/Home/End/Up, wraparound, unhandled-key stability and active panel linkage. Its Playwright acceptance also uses a touch-capable 390×844 context with `tap()`, verifies `aria-controls`/`aria-labelledby` pairing, enforces at least 24×24 CSS-pixel targets, guards horizontal overflow and records a touch-mobile screenshot path.

The first real #1691 browser run also exposed a stale Search E2E locator: non-exact `맥락 검색` matches multiple accessible headings. The Search/E2E owner path must repair the locator against the current accessible contract; the CI owner must not suppress or exclude the test.

**Search Delivery: FAIL** pending accepted exact-head #1691 ancestry, terminal hosted/browser execution and inspected artifacts, assistive-technology acceptance and qualifying independent post-last-push review.

### 4.3 OIDC settings

[#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) exact `0065a7f4059823ec28573050e6cce9ec381b42d6` is the bounded OIDC pending-state owner. It keeps the production pending-state repair, rendered deferred-promise regression, Playwright logout pending/error acceptance and doctoring. Browser source covers desktop keyboard activation, tablet/mobile touch, one held DELETE, native disabled plus `aria-busy`/spinner identity, responsive overflow/screenshots and 503 recovery preserving signed-in state.

**OIDC Delivery: FAIL** while accepted exact-head #1691 browser-execution ancestry, exact-head required/browser evidence, AT, multilingual resource consumption and independent review remain incomplete.

## 5. UI Localization Catalog

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) is the single buyer-visible UI Localization Catalog Gap. [#1740](https://github.com/ContextualWisdomLab/naruon/pull/1740) exact `a2ed58691b8cb98abae9ee9acb51a2e4b4877cf9` owns only pure-domain locale/selection/validation policy for KO/EN/JA/ZH/VI/ES/DE/FR; it does not own persistence, HTTP publication, cache/runtime or Storybook UI.

UI translation authority remains separate from ontology/concept labels. Ubiquitous Language is `screen_key`, `message_key`, `locale_code`, immutable `translation_revision`, immutable deployable `resource_version` and screen/locale/version-bound `translation_receipt`.

Persistence must be normalized, versioned and complete rather than one JSON mega-row. Publishing one `resource_version` is the aggregate transaction boundary; missing translation or placeholder mismatch fails publication. Read API is screen-scoped with immutable version/ETag identity; browser cache key is `(screen_key, locale_code, resource_version)`. Do not fetch the whole catalog at login or create per-key waterfalls.

Persistence must descend from the final accepted #1503 migration ancestry; no parallel Alembic head. Required UI acceptance covers all eight locales in Storybook plus real browser for normal/loading/empty/error/permission states, keyboard/focus/screen-reader/touch, CJK wrapping/font fallback, Vietnamese diacritics, DE/FR/ES text expansion, mobile/intermediate widths and no locale hydration flash. Repository-local browser execution must come through accepted exact-head #1691 ancestry or a verified successor rather than per-UI workflow copies.

**Localization Delivery: FAIL.** A DB/API-only implementation is not Delivery PASS.

## 6. DDD, data, performance and operability guardrails

Naruon bounded contexts must keep Subdomain/Context Map/Ubiquitous Language and Aggregate/Entity/VO/Domain Service/Repository/Event/Invariant aligned across ADR, code, API, DB and tests. Aggregates use the smallest viable transaction. External/legacy integration uses ACLs; Shared Kernel remains minimal.

Database changes remain normalized to at least 3NF unless a measured exception is documented, avoid hot partition/lock amplification, use item-level idempotency/UPSERT where appropriate and preserve one canonical migration ancestry. Purpose-bound PII handling, anonymization boundaries and CSAP/SOC 2 evidence readiness remain required.

Applicable buyer-facing web/API paths require realistic async k6/E2E measurement with p95 ≤20 ms. If exceeded, profile query/I/O/render/runtime/language/framework before optimization; do not pass by shrinking samples, omitting measured work or unrealistic cache warm-up. Browser acceptance must also inspect bundle/heap/DOM/hydration/main-thread/GC when frontend cost is material.

Owned production docstrings/rustdoc, tests and edge-case coverage remain 100% targets. Security/performance runtime and quantitative cores are Rust-first where applicable; Python boundaries require explicit justification and removal conditions. Deprecation warnings are defects to repair, not suppress.

## 7. LLM and agent boundary

All Naruon LLM work consumes a **released** contextual-orchestrator API/client/schema through an Agent boundary. Provider keys, provider/model/group selection, fallback economics and omni-modal routing remain contextual-orchestrator authority. Model-backed GitHub workflows use released central reusable workflow contracts and `orchestrator/free`; Naruon does not hard-code provider groups or copy orchestration internals.

If contextual-orchestrator lacks an immutable released consumer contract, Naruon stays fail-closed for that dependency rather than consuming mutable owner source. Timeout semantics must distinguish user cancellation, provider termination and administrative timeout; elapsed wall time alone must not truncate reasoning/stream/tool execution.

## 8. Completion conditions

This baseline is complete only when all of the following are true on one current protected ancestry:

1. #1565 resolves and adopts the current safe **five-file** backend graph coherently, removes temporary resolver/source-fix workflow code and reaches exact-head GREEN plus independent review.
2. #1623 ordinary-adopts accepted backend ancestry and reaches repository-wide current-database Security GREEN.
3. #1694/#1691/#1503 converge onto one accepted migration/CI ancestry with fresh PostgreSQL, exact-head Playwright browser evidence and exact-head security/review evidence.
4. Utility and material UI owners reach their own exact-head terminal acceptance without receipt transfer or duplicate generated ownership.
5. #1731/#1740 are followed by canonical normalized localization persistence/API/cache/publication and eight-locale Storybook/browser/a11y acceptance.
6. Required external capabilities are consumed only through immutable released/versioned owner contracts.
7. The exact integrated protected head has version/CHANGELOG/tag/package or canonical immutable publication, SBOM/provenance, reproducibility and rollback evidence.

Until then: **Merge/Release Gate = FAIL; UI Delivery Gate = FAIL; Localization Delivery = FAIL.**