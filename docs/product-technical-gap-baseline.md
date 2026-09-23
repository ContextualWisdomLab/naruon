# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.78  
**Observed on:** 2026-09-23 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

v2.77 remains audit-visible as blob `8f932a5a9a2d9db62901a57d1e73c7a1d9300b83`; older snapshots remain reconstructable from Git history and `docs/product-technical-gap-history/`. Historical snapshots and predecessor workflow/review receipts are audit material, not current merge or release authority.

v2.78 does not claim a new protected product release. It currentizes the live owner graph after two material authority changes: the backend TestClient dependency candidate advanced from the already-verified historical `httpx2/httpcore2 2.12.0` graph to a fresh read-only `2.13.0` resolution path, and Tasks generated provenance branches were ordinary/non-force restacked onto the current canonical browser/touch acceptance owner. Product merge, UI Delivery and commercial Release gates remain fail-closed.

## 1. Evidence hierarchy and commercial release posture

Evidence authority is: exact protected code/migrations/tests/runtime contracts → protected architecture/operations docs → exact current Naruon owner PR source and current-head evidence → live Naruon Issue/Proposed ADR authority → historical snapshots. Pending, queued, cancelled, stale, predecessor-head, skipped-required, source-neutral, author-only, local-only or model-only evidence is not passing evidence.

Protected `develop` is `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required status contexts. Active rulesets, PR/Issue inventory, current owner heads and releases must be re-read before acceptance; volatile queue telemetry is not frozen into this baseline.

A commercial candidate requires one exact protected integrated head with all required contexts terminal GREEN, current security evidence, zero valid unresolved review findings, qualifying independent post-last-push review, owned production/test/edge coverage at the required threshold, buyer-visible runtime acceptance, immutable publication identity, SBOM/provenance, reproducibility and rollback evidence.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL.**

## 2. External canonical-owner boundary

Naruon owns its domain truth, UI behavior, product contracts and migration lineage. Other ContextualWisdomLab canonical repositories are consumed only through their released/versioned contract or documented owner path. Naruon must not source-copy their implementations, query their databases directly, pin mutable external heads as consumer contracts, or reproduce their internal provider/model/group routing.

Relevant optional foundations include `.github` for reusable CI/review/security/release contracts, contextual-orchestrator for LLM capability routing, Keyverse for identity backend, EgressWeave for outbound policy, OriginWeave for browser capability, quarantine-sandbox-runtime for hostile workload isolation, appguardrail for SAST/SARIF and Wardnet for gateway/SOC. If an external owner has no immutable/released consumer contract, Naruon remains fail-closed rather than treating its mutable branch head as a release dependency.

## 3. Product source-owner graph

### 3.1 Backend dependency/security owner

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) is the canonical bounded Starlette TestClient/httpx2 and backend coherent-lock owner. Current exact head is `60caa40c6f2d04e55eb8d92ee67b5cce3d09d6f7`, Draft/open.

The AnyIO 4.14.2 repair remains valid. Effective product source still contains direct `httpx2==2.5.0` and resolved `httpcore2==2.5.0`, so the second owner-introduced Security RED remains live.

Historical resolver artifact `10724734967` for direct/resolved 2.12.0 was successfully generated and independently SHA-256 verified. It is retained as reproducibility evidence but is **superseded as the final candidate**: upstream `pydantic/httpx2` published v2.13.0 on 2026-09-14 after v2.12.0, adding TLS verification CLI repair and safer abandoned async-stream cleanup; live Dependabot #1749/#1751 independently expose `httpx2/httpcore2 2.13.0` as the current repository update generation.

Exact `60caa40c...` removes the stale source-writing 2.12.0 adoption helper and replaces it with a read-only `httpx2==2.13.0` resolver inside the already registered Application CI workflow. Current Application CI `35828382074` contains backend Python 3.14, frontend and resolver job `107075084720` (`resolve httpx2 2.13.0 candidate`). The resolver has `contents: read`, does not persist checkout credentials, uses Python 3.14 with pinned `uv==0.10.0`, performs workspace-only resolution, requires generated `httpx2==2.13.0` and `httpcore2==2.13.0`, records binary diff/SHA-256 and uploads exact manifest/hash/uv-lock evidence. It has no commit or push path.

The previous queued 2.12.0 source writer is fail-closed by the owner-branch advance and its own exact remote-head guard. Do not promote the stale artifact merely because it had already passed hash verification.

Required order: current 2.13 resolver GREEN → exact artifact recovery/hash verification → coherent four-file dependency adoption plus matching TestClient contract/CHANGELOG/doctoring → remove every temporary resolver/source-fix workflow from the product candidate → helper-free `uv lock --check`, frozen sync, warnings-as-errors TestClient regression and Ruff → fresh Security/Trivy, CodeQL, all required contexts and independent post-last-push review → normal protected integration.

### 3.2 Frontend dependency/security owner

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the canonical frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`, Draft/open. Its reviewed scope pins Next.js/eslint-config-next 16.3.4 and resolved Sharp 0.35.4 with structural manifest/lock regressions. Its current-database Security evidence has no owned Next.js/Sharp finding; remaining repository-wide findings are inherited backend debt.

#1623 must not copy #1565 lock data. After #1565 integrates normally, #1623 ordinary/non-force adopts the accepted backend delta without changing its reviewed frontend contract and reacquires repository-wide current-database Security on the combined exact head.

[#1752](https://github.com/ContextualWisdomLab/naruon/pull/1752) exact `0b2b4386ac8a2da621602eeaa235bcff4d3b02d4` remains the sole Naruon Dependabot grouping/manifest-scan policy owner. It bounds wildcard groups to patch updates, keeps `aiosmtplib` independent and excludes dedicated backend/connector manifests from the root pip scan. Its historical Security RED belongs to the old dependency graph and must be reacquired after accepted #1565→#1623 integration; the policy lane must not absorb dependency repair.

### 3.3 Migration/workspace and repository-CI ancestry

[#1694](https://github.com/ContextualWisdomLab/naruon/pull/1694) exact `10f046ee5ea004ec9236d59d3ccfeab3e1a417be` owns the bounded fresh-Alembic compatibility repair. Its historical PostgreSQL bootstrap evidence is useful but not final acceptance after dependency ancestry moves.

[#1691](https://github.com/ContextualWisdomLab/naruon/pull/1691) exact `f985a00030028c9989637b3fafffac07d95e2de2` owns only Naruon-local stacked-PR validation. It must consume released central CI contracts rather than copy central workflow source. Historical failures are diagnostic; after accepted dependency/bootstrap prerequisites it must ordinary-adopt them and acquire a fresh exact-head generation.

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) exact `9151c75568c582c8147cfee6757cd00a9b4d60b7` remains the canonical workspace registry/document migration owner. `workspace_id` is an opaque authenticated claim, never ownership evidence. Canonical migration lineage remains `0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`.

Do not restack #1503 merely to chase a moving prerequisite branch. Required order is accepted #1565 → combined-security #1623 → final fresh-bootstrap #1694 → fresh stacked-CI #1691 → ordinary/non-force #1503 restack onto one accepted Alembic head with fresh PostgreSQL migration/security/review evidence.

### 3.4 Utility tools

[#1718](https://github.com/ContextualWisdomLab/naruon/pull/1718) exact `7fb5b9b2578f3a12ac757e1e1b9c5d490722bfd9` is the canonical `hash_generator` + `json_formatter` owner. The strict-JSON repair rejects scalar/nested `NaN`, `Infinity` and `-Infinity`, preserves existing valid formatting and enforces the 100,000-character ceiling. Current-head independent review is approved; Application CI, Bandit, Semgrep and Docker are GREEN. Security is inherited dependency RED and CodeQL settlement remains incomplete.

[#1758](https://github.com/ContextualWisdomLab/naruon/pull/1758) exact `634b2ad34db3d05aa4e00bc2aac0b3a6bcd3709f` remains Draft mixed-owner provenance. Preserve its unique password-generator intent, but remove its duplicate `json_formatter` only after accepted #1718/dependency ancestry is available. It is not a second JSON owner.

## 4. Material UI owner graph and Delivery Gate

UI acceptance is not inferred from source shape. Material UI requires normal/loading/empty/error/permission/responsive/interaction states, keyboard/focus/touch/accessibility evidence, appropriate screenshots/E2E and exact-head current evidence. shadcn/ui source usage is not Storybook acceptance.

### 4.1 Tasks

Canonical Tasks owner [#1463](https://github.com/ContextualWisdomLab/naruon/pull/1463) is exact `146a34411392e2b2bdf48d27cca0576275d5272e`, tree `11929d7e8675d9240e132efb495a62b31f616009`. It owns create/execute active-action identity while preserving mutual exclusion. Browser acceptance source holds WebDAV requests open, proves per-action `aria-busy`/spinner/copy identity and distinct request bodies, covers settlement, desktop screenshots and a 390×844 touch/overflow path.

Generated provenance [#1735](https://github.com/ContextualWisdomLab/naruon/pull/1735) was ordinary/non-force restacked to exact `0a46d13fcd8e88b616eedb2b944070ac45203872`; fresh compare to #1463 is ahead 6 / behind 0 / zero effective files. Generated provenance [#1759](https://github.com/ContextualWisdomLab/naruon/pull/1759) was likewise restacked to `32f41fc5674ea212431d9203f6bb30a0d4002520`; compare is ahead 5 / behind 0 / zero effective files. Neither is a second product owner and neither may transfer its receipts to #1463.

**Tasks Delivery: FAIL** until canonical exact-head hosted/browser evidence is terminal, AT evidence is present, valid review findings are zero and an independent post-last-push approval exists.

### 4.2 Search

[#1603](https://github.com/ContextualWisdomLab/naruon/pull/1603) exact `af2efcef6a6dfeedbd13a69865b5a8fdd7f1fd10` remains canonical Search owner. Bounded refinement [#1760](https://github.com/ContextualWisdomLab/naruon/pull/1760) exact `32e296c6e6c2b76291d22d1d27c6ae12d53fd7ac` adds shared Button tab semantics and real-browser keyboard/focus acceptance for Left/Right/Home/End/Up, wraparound, unhandled-key stability, active panel linkage, desktop screenshot and mobile-width overflow.

**Search Delivery: FAIL** pending terminal exact-head hosted/browser evidence, touch-specific/AT acceptance and independent review.

### 4.3 OIDC settings

[#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) exact `0065a7f4059823ec28573050e6cce9ec381b42d6` is the bounded OIDC pending-state owner. It keeps the production pending-state repair, rendered deferred-promise regression, Playwright logout pending/error acceptance and doctoring. Browser source covers desktop keyboard activation, tablet/mobile touch, one held DELETE, native disabled plus `aria-busy`/spinner identity, responsive overflow/screenshots and 503 recovery preserving signed-in state.

**OIDC Delivery: FAIL** while exact-head required/browser evidence, AT, multilingual resource consumption and independent review remain incomplete.

## 5. UI Localization Catalog

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) is the single buyer-visible UI Localization Catalog Gap. [#1740](https://github.com/ContextualWisdomLab/naruon/pull/1740) exact `a2ed58691b8cb98abae9ee9acb51a2e4b4877cf9` owns only pure-domain locale/selection/validation policy for KO/EN/JA/ZH/VI/ES/DE/FR; it does not own persistence, HTTP publication, cache/runtime or Storybook UI.

UI translation authority remains separate from ontology/concept labels. Ubiquitous Language is `screen_key`, `message_key`, `locale_code`, immutable `translation_revision`, immutable deployable `resource_version` and screen/locale/version-bound `translation_receipt`.

Persistence must be normalized, versioned and complete rather than one JSON mega-row. Publishing one `resource_version` is the aggregate transaction boundary; missing translation or placeholder mismatch fails publication. Read API is screen-scoped with immutable version/ETag identity; browser cache key is `(screen_key, locale_code, resource_version)`. Do not fetch a whole catalog at login or create per-key waterfalls.

Persistence must descend from the final accepted #1503 migration ancestry; no parallel Alembic head. Required UI acceptance covers all eight locales in Storybook plus real browser for normal/loading/empty/error/permission states, keyboard/focus/screen-reader/touch, CJK wrapping/font fallback, Vietnamese diacritics, DE/FR/ES text expansion, mobile/intermediate widths and no locale hydration flash.

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

1. #1565 resolves and adopts the current safe backend graph coherently, removes temporary resolver/source-fix workflow code and reaches exact-head GREEN plus independent review.
2. #1623 ordinary-adopts accepted backend ancestry and reaches repository-wide current-database Security GREEN.
3. #1694/#1691/#1503 converge onto one accepted migration/CI ancestry with fresh PostgreSQL and exact-head evidence.
4. Utility and material UI owners reach their own exact-head terminal acceptance without receipt transfer.
5. #1731/#1740 are followed by canonical normalized localization persistence/API/cache/publication and eight-locale Storybook/browser/a11y acceptance.
6. Required external capabilities are consumed only through immutable released/versioned owner contracts.
7. The exact integrated protected head has version/CHANGELOG/tag/package or canonical immutable publication, SBOM/provenance, reproducibility and rollback evidence.

Until then: **Merge/Release Gate = FAIL; UI Delivery Gate = FAIL; Localization Delivery = FAIL.**
