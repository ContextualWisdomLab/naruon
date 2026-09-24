# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.96  
**Observed on:** 2026-09-24 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

v2.95 remains audit-visible as blob `8bd1c3d8a057b4b8eea4f94880e4c3e0302bb632`; v2.94 as `e4643a58abf613bba9a2bec90964ad7d9b908ae8`; v2.93 as `c72cc29a647ffca6ffcd891755a9abc6c2a17553`; v2.92 as `40b6875cc84f58cf340df4215af2b62e6db19944`; v2.91 as `9fe2b4930c27cdb089e32105840ce194e2fa5e7c`; v2.88 as `1c708286ddcd3c8ab543043aac428889b4f53c4f`. Attempted v2.89, v2.90 and the first v2.91 workflow currentizers remain transition-failure provenance only. The durable ledger is maintained by ordinary commits on the sole Gap-writer branch; self-modifying currentizers are not accepted as completion evidence.

## 1. Evidence hierarchy and commercial release posture

Evidence authority is exact protected code/migrations/tests/runtime contracts → protected architecture/operations docs → exact current Naruon owner PR source and current-head evidence → live Naruon Issue/Proposed ADR authority → historical snapshots. Pending, queued, cancelled, stale, predecessor-head, source-neutral, author-only, local-only or model-only evidence is not passing evidence.

Protected `develop` remains `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required status contexts. Commercial acceptance requires one exact integrated protected head with all required contexts terminal GREEN, current security evidence, zero valid unresolved review findings, qualifying independent post-last-push review, real buyer-visible runtime acceptance, immutable publication identity, SBOM/provenance, reproducibility and rollback evidence.

Naruon latest GitHub Release is `v0.14.4` and is not immutable. Therefore it is not current commercial release authority.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL. Localization Delivery: FAIL.**

## 2. External canonical-owner boundary

Naruon owns its domain truth, UI behavior, product contracts and migration lineage. Other ContextualWisdomLab repositories are consumed only through released/versioned contracts or explicit owner paths. Naruon does not source-copy their implementations, query their databases directly or treat mutable external heads as consumer contracts.

Relevant optional foundations include `.github` for reusable CI/review/security/release contracts; contextual-orchestrator for LLM capability routing; Keyverse for identity; EgressWeave for outbound policy; OriginWeave for browser capability; quarantine-sandbox-runtime for hostile-workload isolation; appguardrail for SAST/SARIF; Wardnet for gateway/SOC; and the other canonical CWL owners defined by repository policy.

Contextual-orchestrator protected `main` is currently `5665b0ad1e07ffb5e9f8c59e44b6b2a785298013`. It is an owner head, not a released Naruon contract. Its GitHub Release inventory remains exactly empty, so Naruon stays fail-closed rather than consuming mutable CO source.

### 2.1 LLM governance source drift and released-owner handoff

Protected Naruon governance is still inconsistent with the current CWL LLM boundary. Protected `AGENTS.md` describes central Strix in provider/model-specific terms, including direct GitHub Models selection, named fallback models, manual Vertex modes and direct OpenAI modes. Protected `ARCHITECTURE.md` contains direct OpenAI-compatible provider/fallback language that can be read as product authority outside a released contextual-orchestrator contract. Those statements are live source defects; this ledger does not supersede them.

[#1549](https://github.com/ContextualWisdomLab/naruon/pull/1549) exact `9e47f25e256f52f13df267e0383bc3b036ac6f9e` remains the sole Naruon LLM-governance repair owner. Its effective six-file delta is `AGENTS.md`, `ARCHITECTURE.md`, `CLAUDE.md`, `backend/tests/test_agent_llm_authority_docs.py`, `backend/tests/test_release_governance.py`, and `opencode.jsonc`. The repaired contract requires model-backed Actions to request only logical `orchestrator/free` through the gateway credential, leaves provider/model/group discovery and fallback to contextual-orchestrator, forbids mutable owner source as a consumer contract, and distinguishes user cancellation/provider termination/explicit administrative limits from elapsed-time truncation.

#1549 is source-current for the intended repair but not delivery authority. It is stacked, has no qualifying exact-head repository admission or post-last-push approval, and contextual-orchestrator has no immutable GitHub Release carrying the required API/client/schema/provenance. Required order is immutable CO publication → legitimate stacked-PR admission through #1691 or accepted successor → #1549 exact-head checks/review → normal protected integration. Naruon must not copy `.github` or contextual-orchestrator source, pin a provider/model, or bind to CO `main` while waiting.

## 3. Product source-owner graph

### 3.1 Backend dependency/security owner

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the canonical Starlette TestClient/httpx2 and coherent backend-lock owner. Resolver exact `d166c9208b275ab88895e7711d999c4729a81025` produced the coherent five-file `httpx2/httpcore2==2.13.0` candidate. Artifact `10748790356` was re-downloaded again on 2026-09-24 and its SHA-256 values still match the accepted bytes:

- `backend/requirements.txt`: `87f603d06eb05fa234163003a2feda98f024b80751cc9eb919aedb261136482f`
- `backend/pyproject.toml`: `faab5edd236153c28a321e431dc1a6d5f99bcaa64f26f21c60222a1db2057365`
- `backend/requirements-hashes.txt`: `551f6aa4a6a8f1efb7f6259dc63777c40c09b2f520dea217575b94b12178f7d5`
- `backend/requirements-agent.txt`: `761ceb9f7042ffa9538c5a596ad113a3ee59f27381c4a44d34df82338e5b913a`
- `backend/uv.lock`: `fa28138f637a2c2baddd528893cfb04be2d9064afcadd538fb7fa5000be7f82b`

That candidate resolves AnyIO `4.14.2`. Effective protected/product source still carries the vulnerable predecessor state. #1767 Security run `35925494018` is terminal FAILURE in `trivy-fs` with inherited AnyIO findings `CVE-2026-63374`, `CVE-2026-63349`, and `CVE-2026-64847`; this is backend dependency Security RED, not a NetworkGraph defect.

The product-adoption transition has had two distinct automation defects. Run `35939616799` failed after the base-aware rewrite. Diagnostic run `35957638723` is also terminal FAILURE: remote-head equality, staged-path verification and local commit all succeeded, then `Push repair non-force` failed before branch update. The old helper tried to remove itself and rewrite `.github/workflows/app-ci.yml` in the same Actions-authenticated push. That workflow-file self-mutation was the remaining transition defect and is not a product dependency failure.

Ordinary-forward repair exact `4e5f8609f627c7d1bd24bf148fa11682ae67e503` restores `app-ci.yml` to the protected blob, removes the old self-mutating helper, and adds only `temporary-httpx2-product-adopter.yml`. The replacement adopter never stages workflow files. It verifies frozen artifact `10748790356`, applies the five lock/manifest files plus focused regression, CHANGELOG and doctoring documentation, proves `uv lock --check`, hash-locked core+agent installation, warnings-as-errors focused pytest and Ruff, then stages exactly eight non-workflow product/doc paths and performs an ordinary non-force push. Run `35977315662` is queued/nonterminal at this observation. No helper-free 2.13.0 product child exists yet, so Security remains RED and predecessor receipts do not transfer.

### 3.2 Frontend dependency/security owner

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) exact `509be4c1d9b6c7ba239a108656e2382681a85341` remains the canonical frontend dependency-security owner. It carries the reviewed frontend dependency floor (`next`/`eslint-config-next` `16.3.4`, resolved `sharp` `0.35.4`) and has a bounded current-database frontend PASS.

The same #1767 Security run `35925494018` reported inherited Next.js findings `CVE-2026-75604`, `GHSA-2xp9-vwfh-vxw4` and Sharp `GHSA-rgj7-g3m4-5g8c` on the protected dependency state. Intervening #1767 commit `f111866d1f28e1dc52fc770834af08048003032a` attempted to repair dependency manifests/locks directly in the NetworkGraph lane. That was a canonical-owner violation, not an accepted dependency successor. #1767 ordinary-forward repair `157894a526165005e686f81c1f7b7a14c39f1973` preserves the history while restoring those dependency files to the owner-neutral blobs.

#1623 ordinary-adopts accepted backend ancestry only after #1565 settles and must reacquire repository-wide dependency/security evidence on that resulting exact head. [#1752](https://github.com/ContextualWisdomLab/naruon/pull/1752) remains the Dependabot grouping/manifest-scan policy owner and must not absorb dependency repair.

### 3.3 Migration/workspace and repository CI/browser owner

[#1694](https://github.com/ContextualWisdomLab/naruon/pull/1694) exact `10f046ee5ea004ec9236d59d3ccfeab3e1a417be` remains the sole fresh-Alembic compatibility owner for the `email_records` / legacy `emails` bootstrap defect exposed by #1691.

[#1691](https://github.com/ContextualWisdomLab/naruon/pull/1691) last helper-free CI/browser-owner source is `4bf3efd95b8c5002c281a4b47f93e78fc63730de`. Historical Application CI `35850922236` proved exact Playwright artifact provenance but failed clean PostgreSQL migration and integrated browser acceptance.

The repeated `/api/data/quality-surface/evidence-snapshot` 404 is a verified shared Playwright fixture defect rather than a missing backend route. Protected backend source exposes the route, `DataLayout` requests it, and full-product smoke already carries the server-shaped `data_quality_evidence_snapshot.v1` fixture. Shared `mockDashboardApi` omitted the route and allowed mocked requests to fall through to 404.

The first bounded fixture staging `966a4e1e0c1ee93b677ac36333e8e7c7b7070336` did not reach the product repair. Run `35956903492` is terminal FAILURE at `Set up Node.js`: the workflow requested setup-node `cache: pnpm` before the later `corepack enable pnpm`, so Actions failed during package-manager cache bootstrap. This is workflow bootstrap RED, not evidence that the Data route/fixture repair is wrong.

Ordinary-forward repair exact `6b59cf471f91223c57d6a58fa02c6d6581d4b4e1` removes that helper and adds `temporary-data-fixture-product-adopter.yml`. The replacement setup-node step does not request pnpm cache before pnpm exists; Corepack is enabled afterward. It applies only `frontend/tests/e2e/helpers.ts` plus `frontend/src/lib/data-evidence-snapshot-e2e-fixture.test.ts`, verifies focused Vitest and ESLint, enforces remote-head equality and exact two-path staging, then performs an ordinary product-only non-force push. It does not self-delete or push workflow-file mutations. Run `35977617777` is queued/nonterminal at this observation, so the fixture repair remains staged rather than accepted.

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the canonical workspace registry/document migration owner. Required ancestry remains accepted #1565 → #1623 → #1694 clean bootstrap → canonical product repairs → #1691 integrated browser acceptance → #1503 ordinary restack.

### 3.4 Utility tools

[#1718](https://github.com/ContextualWisdomLab/naruon/pull/1718) exact `7fb5b9b2578f3a12ac757e1e1b9c5d490722bfd9` remains the sole hash-generator and strict JSON-format owner. #1718→#1758 and #1758→#1763 are not actual canonical ancestry despite metadata retargets.

#1758 preserves password-generator intent only. Its generated Python primitive permitting length 4..128 is not accepted as a generic authentication contract until the bounded context distinguishes single-factor password, MFA password, activation/testing secret or another use case, Keyverse remains the identity backend, and the security-runtime Rust-first owner boundary is resolved. Weaker duplicate JSON source must not be adopted. #1763 can settle only after real canonical ancestry exists and a unique bounded delta or verified zero-delta provenance is established.

### 3.5 Generated provenance and canonical descendant repairs

Generated/provenance lanes do not bypass canonical owners. #1738 and #1725 remain ordinary-forward zero-delta corrections.

Search detail-tabs #1760 is helper-free at `6da4f4ddee65e80524546dc25b370f2568ab59ba`, a real descendant of helper-free #1603 `d65a34773540147f568fab7aeeaf28835071ede2`, with exactly three Search detail-tab files as the parent-relative delta.

Projects #1764 is helper-free at `1f462b65fed368bf1db36b9fbdf364cf5e37483b`, a real descendant of #1352 `1b8497f33e1977ce7b963640b63f107510621973`, with exactly three Projects files.

Search exception-redaction #1765 is helper-free at `821d193d807ae952c4b2e96206008107e624177c`, a real descendant of canonical #1612 `3da3ae8e60e1bb049f59ae86bfe82db12b7e3cc7`. Intervening commit `67b45d53873aac92d3f7cc5a477d0f53ae44cf57` broadened the effective delta and reintroduced raw exception-string logging. Ordinary-forward repair restored the canonical tree while preserving history. Fresh #1612→current comparison is ahead 8 / behind 0 with exactly `backend/api/search.py` and `backend/tests/test_search_exception_redaction_contract.py` as effective delta. Search consumes canonical `redacted_exception_info(e)` and raises fixed public HTTP details `from None`.

These are source-topology PASS results, not Delivery PASS. Current `app-ci.yml` filters normal pull-request execution to bases `develop`, `master`, and `release/**`, so valid stacked children can lack normal exact-head hosted Application CI. #1691 owns correction of that repository-CI topology; child branches do not copy CI workflow source or predecessor receipts.

## 4. Material UI owner graph and Delivery Gate

Material UI acceptance requires normal/loading/empty/error/permission/responsive/interaction states, keyboard/focus/touch/accessibility evidence, current screenshots/E2E where applicable, and exact-head current evidence. shadcn/ui source use is not Storybook acceptance.

### 4.1 Tasks

[#1463](https://github.com/ContextualWisdomLab/naruon/pull/1463) remains the sole Tasks active-action owner. Its bounded corrective owner `dd0a2cb55ea1c849a2962a246f6d91bd6ee798e8` uses tree `11929d7e8675d9240e132efb495a62b31f616009` and limits the effective product delta to five Tasks-owned files: `frontend/src/app/tasks/page.test.tsx`, `frontend/src/components/TasksLayout.knowledge-intent-pending.test.tsx`, `frontend/src/components/TasksLayout.test.tsx`, `frontend/src/components/TasksLayout.tsx`, and `frontend/tests/e2e/tasks-pending-action.spec.ts`.

A later generated sequence `c85459c072b7546eaedbdc981c515b2797d556e5` → `6d50011e...` → `f4a5f5b34277c827abf6137be9876adbb8742620` crossed dependency and Gap ownership, altered the Tasks source/evidence set, deleted `frontend/tests/e2e/tasks-pending-action.spec.ts`, and removed **Strix Security Scan** from `.github/workflows/pr-governance.yml` to unblock CI. Scanner availability is evidence state, not authorization to weaken a required governance dependency; this was a verified gate-weakening finding.

No history was rewritten. Ordinary-forward repair `f9346385b9d4affa57215d2c676e722a2b99d0eb` uses the live drift head as parent while restoring the exact bounded tree `11929d7e8675d9240e132efb495a62b31f616009`. Fresh `dd0a2cb5...→f9346385...` is ahead 4 / behind 0 with zero effective files. All current review threads are resolved/outdated, but there is no qualifying independent post-last-push approval.

#1735 exact `1b0bace3a882c176f6f6b67636b0fb8d9a8dc978` and #1759 exact `33f553f47451fe6247168dd2aa335bdf62790e4e` are ordinary non-force provenance descendants of current #1463 with zero changed files. They are not independent product owners and their receipts do not transfer.

Exact-current #1463 Application CI, Security, CodeQL, Bandit, Semgrep and Docker generations remain nonterminal at this observation. The bounded source/unit/browser contract is restored, but hosted browser/security/AT evidence and independent review remain incomplete. **Tasks UI Delivery: FAIL.**

### 4.2 Search

[#1603](https://github.com/ContextualWisdomLab/naruon/pull/1603) exact `d65a34773540147f568fab7aeeaf28835071ede2` is the helper-free canonical Search owner. [#1760](https://github.com/ContextualWisdomLab/naruon/pull/1760) exact `6da4f4ddee65e80524546dc25b370f2568ab59ba` is its real three-file detail-tab descendant. Source topology is PASS. Search Delivery remains FAIL because the stacked exact child lacks normal hosted browser/security evidence and qualifying independent post-last-push review.

Search exception-redaction is separately #1612→#1765 exact `821d193d807ae952c4b2e96206008107e624177c`. Source/security topology is PASS after repairing the intervening broad regression; protected hosted/review acceptance remains FAIL because the stacked exact child has no normal GitHub Actions generation and no qualifying independent post-last-push review.

### 4.3 OIDC settings

[#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) exact `c3e2e8ebb8a227feaff2586b2f6fb0a2aac1435b` remains the bounded OIDC pending-state owner. Generated evidence deletion was repaired ordinary-forward, restoring the prior product/rendered-regression/Playwright/doctoring tree without rewriting history. Source/evidence restoration is PASS. Delivery remains FAIL because predecessor receipts do not transfer and exact-current required/browser evidence plus independent review are incomplete.

### 4.4 Projects

[#1352](https://github.com/ContextualWisdomLab/naruon/pull/1352) remains the Projects async/busy-state owner. [#1764](https://github.com/ContextualWisdomLab/naruon/pull/1764) exact `1f462b65fed368bf1db36b9fbdf364cf5e37483b` is its real helper-free three-file descendant. Source topology is PASS; Projects Delivery remains FAIL until exact-child browser/touch/AT/security/review evidence exists.

### 4.5 Mail/dashboard flow

[#1766](https://github.com/ContextualWisdomLab/naruon/pull/1766) exact `705984a381e5ea999c17bae508d35e1bf820c31b` remains the bounded one-file mail/dashboard-flow regression successor. Source/build/smoke evidence is GREEN, but real integrated `pnpm run test:e2e` acceptance through accepted #1691 ancestry is absent. Delivery remains FAIL.

### 4.6 Network graph

[#1767](https://github.com/ContextualWisdomLab/naruon/pull/1767) current exact `157894a526165005e686f81c1f7b7a14c39f1973` retains only the bounded `React.memo` optimization and parent-update render-body regression as its effective product/test delta. Historical exact `209a0fc2...` had Application CI `35925494000` GREEN and its focused CodeRabbit parent-update thread resolved, but Security `35925494018` failed on six inherited dependency findings.

Intervening commit `f111866d1f28e1dc52fc770834af08048003032a` crossed owner boundaries by modifying backend and frontend dependency files inside the NetworkGraph lane. Ordinary-forward repair `157894a...` preserves that history while restoring `backend/uv.lock`, `frontend/package.json`, and `frontend/pnpm-lock.yaml` to the previous owner-neutral blobs. `209a0fc2...`→`157894a...` is ahead 2 / behind 0 with zero effective file delta, and the repaired tree is `e41e825b0675d7d80c56e9756031c8994570cdb0` again.

Fresh exact-current Application CI `35965793616`, Bandit `35965793743`, Semgrep `35965793668`, and Docker `35965794291` are terminal GREEN. Security `35965793843` and CodeQL `35965793657` remain queued/nonterminal at this observation. Predecessor receipts do not transfer, and terminal success on the four settled workflows is not sufficient to claim protected acceptance. The historical formal `CHANGES_REQUESTED` review remains non-approval. No representative large-graph profiler/browser/k6 measurement exists, so no p95/main-thread performance claim is accepted. Delivery remains FAIL.

## 5. UI Localization Catalog

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single buyer-visible UI Localization Catalog Gap. [#1740](https://github.com/ContextualWisdomLab/naruon/pull/1740) exact `a2ed58691b8cb98abae9ee9acb51a2e4b4877cf9` owns only pure-domain locale/selection/validation policy for KO/EN/JA/ZH/VI/ES/DE/FR; it does not own persistence, HTTP publication, cache/runtime, Storybook UI or LLM translation.

The target contract is a normalized/versioned DB resource with `screen_key`, `message_key`, `locale_code` and immutable `resource_version`; screen-scoped API/cache only; complete publication; and a separate ontology-label ledger. Persistence descends from accepted #1503 ancestry. UI acceptance covers all eight locales in Storybook and real browser normal/loading/empty/error/permission states, keyboard/focus/screen-reader/touch, CJK wrapping/font fallback, Vietnamese diacritics, DE/FR/ES expansion, mobile/intermediate widths and no locale hydration flash.

Repository-local browser execution comes through accepted #1691. Current #1691 Data fixture repair is staged/nonterminal and clean PostgreSQL remains #1694-owned. **Localization Delivery: FAIL.**

## 6. DDD, data, performance and operability guardrails

Naruon bounded contexts keep Subdomain/Context Map/Ubiquitous Language and Aggregate/Entity/VO/Domain Service/Repository/Event/Invariant aligned across ADR, code, API, DB and tests. Aggregates use the smallest viable transaction; external/legacy integration uses ACLs; Shared Kernel remains minimal.

Database changes remain normalized to at least 3NF unless a measured exception is documented, avoid hot partition/lock amplification, use item-level idempotency/UPSERT where appropriate and preserve one canonical migration ancestry. Purpose-bound PII handling, anonymization boundaries and CSAP/SOC 2 evidence readiness remain required.

Owned production docstrings/rustdoc, tests and edge-case coverage target 100%. Security/runtime and mathematical/data-science hot paths are Rust-first; Python is limited to justified boundaries with removal criteria. Deprecation warnings are defects, not accepted noise.

Applicable web/API buyer paths use async execution and realistic k6/E2E. A p95≤20 ms claim is accepted only from defined buyer-path measurements; smoke timings, one-off first-load observations and warm-cache shortcuts are not performance acceptance. Frontend bundle/heap/DOM/hydration/main-thread/GC bottlenecks require measured profiling before stack changes.

## 7. LLM and agent boundary

Naruon LLM work consumes only released contextual-orchestrator API/client/schema through an Agent boundary. Provider/model/group hard-coding is not product authority. GitHub model-backed workflows request only `orchestrator/free` through the gateway credential; capability absence fails closed and is repaired in the contextual-orchestrator owner. Mutable contextual-orchestrator `main` is not a consumer release.

The current protected guidance does not yet meet that contract. #1549 is the sole Naruon repair lane and already carries the provider-neutral source/test delta, but it cannot be treated as protected authority before immutable CO publication, legitimate exact-head hosted admission, independent review and normal integration. Until then, protected provider-specific AGENTS/ARCHITECTURE wording remains a commercial governance blocker rather than documentation noise.

Model timeout defaults do not truncate reasoning/streaming/tool use by elapsed time alone; user cancellation, provider termination and an explicit audited administrative timeout are distinct. Structured chat preserves responses/completions schema contracts; embedding preserves semantic unit, source position and provenance.

## 8. Current release blockers

Current commercial blockers are: helper-free #1565 2.13.0/AnyIO-fixed product adoption and fresh resulting security evidence; #1623 accepted frontend dependency-security ancestry and combined repository-wide Security; #1694 fresh PostgreSQL bootstrap on accepted ancestry; #1691 stacked-PR trigger plus integrated real-browser evidence including the Data evidence-snapshot fixture; exact-current #1463 Tasks hosted browser/security/AT evidence and independent review after the gate-weakening repair; downstream #1503 migration ancestry; protected integration of #1549 after an immutable contextual-orchestrator API/client/schema release; full eight-locale persistence/publication/browser acceptance; central required security/review contexts; representative performance evidence where claimed; and one immutable Naruon release with SBOM/provenance/reproducibility/rollback.

The #1565 and #1691 temporary adopters are transition mechanisms only. They must not become permanent product workflows. If they produce verified product commits, the temporary workflow must be removed by a subsequent ordinary non-force commit before exact-head acceptance evidence is evaluated. If they fail, the failure is RCA input rather than permission to weaken branch/security gates.
