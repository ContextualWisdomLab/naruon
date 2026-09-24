# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.94  
**Observed on:** 2026-09-24 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

v2.93 remains audit-visible as blob `c72cc29a647ffca6ffcd891755a9abc6c2a17553`; v2.92 remains audit-visible as blob `40b6875cc84f58cf340df4215af2b62e6db19944`; v2.91 remains audit-visible as blob `9fe2b4930c27cdb089e32105840ce194e2fa5e7c`; v2.88 remains audit-visible as blob `1c708286ddcd3c8ab543043aac428889b4f53c4f`. The attempted v2.89, v2.90 and first v2.91 workflow currentizers are audit-visible transition failures and did not create a durable baseline. The failed temporary currentizer has been removed; current revisions are ordinary documentation commits on the sole Gap-writer branch.

## 1. Evidence hierarchy and commercial release posture

Evidence authority is exact protected code/migrations/tests/runtime contracts → protected architecture/operations docs → exact current Naruon owner PR source and current-head evidence → live Naruon Issue/Proposed ADR authority → historical snapshots. Pending, queued, cancelled, stale, predecessor-head, source-neutral, author-only, local-only or model-only evidence is not passing evidence.

Protected `develop` is `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required status contexts. Commercial acceptance requires one exact integrated protected head with all required contexts terminal GREEN, current security evidence, zero valid unresolved review findings, qualifying independent post-last-push review, real buyer-visible runtime acceptance, immutable publication identity, SBOM/provenance, reproducibility and rollback evidence.

Naruon latest GitHub Release is `v0.14.4` and is not immutable. Therefore it is not current commercial release authority.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL. Localization Delivery: FAIL.**

## 2. External canonical-owner boundary

Naruon owns its domain truth, UI behavior, product contracts and migration lineage. Other ContextualWisdomLab repositories are consumed only through released/versioned contracts or explicit owner paths. Naruon does not source-copy their implementations, query their databases directly or treat mutable external heads as consumer contracts.

Relevant optional foundations include `.github` for reusable CI/review/security/release contracts; contextual-orchestrator for LLM capability routing; Keyverse for identity; EgressWeave for outbound policy; OriginWeave for browser capability; quarantine-sandbox-runtime for hostile-workload isolation; appguardrail for SAST/SARIF; Wardnet for gateway/SOC; and the other canonical CWL owners defined by repository policy.

Contextual-orchestrator protected `main` is currently `5665b0ad1e07ffb5e9f8c59e44b6b2a785298013`. It is an owner head, not a released Naruon contract. Its GitHub Release inventory remains exactly empty, so Naruon stays fail-closed rather than consuming mutable CO source.

### 2.1 LLM governance source drift and released-owner handoff

Protected Naruon governance is still internally inconsistent with the current CWL LLM boundary. Protected `AGENTS.md` still describes central Strix in provider/model-specific terms, including direct GitHub Models selection, named fallback models, manual Vertex modes and direct OpenAI modes. Protected `ARCHITECTURE.md` still describes direct OpenAI-compatible provider paths and fallback behavior that can be read as product authority outside a released contextual-orchestrator contract. Those protected statements are live source defects; they are not superseded merely by this ledger or a PR body.

[#1549](https://github.com/ContextualWisdomLab/naruon/pull/1549) exact `9e47f25e256f52f13df267e0383bc3b036ac6f9e` remains the sole Naruon LLM-governance repair owner. Its effective six-file delta is `AGENTS.md`, `ARCHITECTURE.md`, `CLAUDE.md`, `backend/tests/test_agent_llm_authority_docs.py`, `backend/tests/test_release_governance.py`, and `opencode.jsonc`. The repaired contract requires model-backed Actions to request only logical `orchestrator/free` through the gateway credential, leaves provider/model/group discovery and fallback to contextual-orchestrator, forbids mutable owner source as a consumer contract, and separates user cancellation/provider termination/explicit administrative limits from elapsed-time truncation.

#1549 is source-current for the intended repair but not delivery authority. It is intentionally stacked, has no exact-head GitHub Actions generation on `9e47f25e...`, and has no qualifying post-last-push approval. More importantly, contextual-orchestrator has no immutable GitHub Release carrying the required API/client/schema/provenance. Required order is immutable CO publication → legitimate stacked-PR admission through #1691 or accepted successor → #1549 exact-head checks/review → normal protected integration. Naruon must not copy `.github` or contextual-orchestrator source, pin a provider/model, or bind to CO `main` while waiting.

## 3. Product source-owner graph

### 3.1 Backend dependency/security owner

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the canonical Starlette TestClient/httpx2 and coherent backend-lock owner. Resolver exact `d166c9208b275ab88895e7711d999c4729a81025` produced a coherent five-file `httpx2/httpcore2==2.13.0` candidate. Artifact `10748790356` was re-downloaded and its five SHA-256 values still match the recorded `requirements.txt`, `pyproject.toml`, `requirements-hashes.txt`, `requirements-agent.txt`, and `uv.lock` evidence. That candidate lock resolves AnyIO `4.14.2`.

Product adoption has not succeeded. Effective protected/product source still carries the vulnerable dependency state. #1767 Security run `35925494018` scanned exact `209a0fc2c070fbe24f2abf8c9863ca47682a2ffa` and became terminal FAILURE in `trivy-fs`, reporting three inherited AnyIO findings: `CVE-2026-63374`, `CVE-2026-63349`, and `CVE-2026-64847`. This is current proof that backend dependency Security remains RED; it is not a NetworkGraph defect. The #1565 candidate version is within the upstream fixed floor for these newly disclosed AnyIO advisories, but acceptance still requires the ordinary helper-free product adoption and a fresh current-database Trivy run on that exact descendant.

Run `35939616799` is terminal FAILURE: the base-aware source rewrite completed locally, then the compound ordinary-push step failed before any branch update. Current diagnostic staging `2267a7146dd37b8c2bacf133da20e0d97ccb3d2f` preserves the same causal repair but separates remote-head equality, exact staging, commit and non-force push into independent fail-closed steps. Run `35957638723` remains queued/nonterminal at this observation. No helper-free 2.13.0 product child exists, so Security remains RED and predecessor receipts do not transfer.

### 3.2 Frontend dependency/security owner

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) exact `509be4c1d9b6c7ba239a108656e2382681a85341` remains the canonical frontend dependency-security owner. It carries the reviewed frontend dependency floor (`next`/`eslint-config-next` `16.3.4`, resolved `sharp` `0.35.4`) and has a bounded current-database frontend PASS.

The same #1767 Security run `35925494018` reported two inherited Next.js findings (`CVE-2026-75604`, `GHSA-2xp9-vwfh-vxw4`) and one Sharp finding (`GHSA-rgj7-g3m4-5g8c`) on protected-base dependency state. An intervening #1767 commit `f111866d1f28e1dc52fc770834af08048003032a` attempted to remediate those findings by changing `frontend/package.json`, `frontend/pnpm-lock.yaml`, and `backend/uv.lock` directly in the NetworkGraph lane. That was a canonical-owner violation, not an accepted dependency successor. #1767 ordinary-forward repair `157894a526165005e686f81c1f7b7a14c39f1973` restores all three dependency files to the owner-neutral prior blobs while preserving the intervening commit in history. Dependency repair remains exclusively #1565/#1623-owned.

#1623 ordinary-adopts accepted backend ancestry only after #1565 settles and must reacquire repository-wide dependency/security evidence on the resulting exact head. [#1752](https://github.com/ContextualWisdomLab/naruon/pull/1752) remains the Dependabot grouping/manifest-scan policy owner and must not absorb dependency repair.

### 3.3 Migration/workspace and repository CI/browser owner

[#1694](https://github.com/ContextualWisdomLab/naruon/pull/1694) exact `10f046ee5ea004ec9236d59d3ccfeab3e1a417be` remains the sole fresh-Alembic compatibility owner for the `email_records` / legacy `emails` bootstrap defect exposed by #1691.

[#1691](https://github.com/ContextualWisdomLab/naruon/pull/1691) last helper-free CI/browser-owner source is `4bf3efd95b8c5002c281a4b47f93e78fc63730de`. Historical Application CI `35850922236` proved exact Playwright artifact provenance but failed clean PostgreSQL migration and integrated browser acceptance.

The repeated `/api/data/quality-surface/evidence-snapshot` 404 is verified as a shared Playwright fixture defect rather than a missing backend route. Protected backend source exposes that route, `DataLayout` requests it, and full-product smoke already carries the server-shaped `data_quality_evidence_snapshot.v1` fixture. Shared `mockDashboardApi` omitted the route and allowed mocked requests to fall through to 404.

Current #1691 staging `966a4e1e0c1ee93b677ac36333e8e7c7b7070336` adds only a temporary self-removing repair workflow. It is bounded to the shared Playwright helper plus one focused Vitest regression, requires a redacted/verifier-ready 200 JSON snapshot, runs focused Vitest/ESLint, verifies remote-head equality, removes itself, and only then may normal non-force push. Run `35956903492` remains queued/nonterminal at this observation; the fixture repair is therefore staged, not accepted.

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the canonical workspace registry/document migration owner. Required ancestry remains accepted #1565 → #1623 → #1694 clean bootstrap → canonical product repairs → #1691 integrated browser acceptance → #1503 ordinary restack.

### 3.4 Utility tools

[#1718](https://github.com/ContextualWisdomLab/naruon/pull/1718) exact `7fb5b9b2578f3a12ac757e1e1b9c5d490722bfd9` remains the sole hash-generator and strict JSON-format owner. #1718→#1758 and #1758→#1763 are not actual canonical ancestry despite metadata retargets.

#1758 preserves password-generator intent only. Its generated Python primitive permitting length 4..128 is not accepted as a generic authentication contract until the bounded context distinguishes single-factor password, MFA password, activation/testing secret or another use case, Keyverse remains the identity backend, and the security-runtime Rust-first owner boundary is resolved. Weaker duplicate JSON source must not be adopted. #1763 can settle only after real canonical ancestry exists and a unique bounded delta or verified zero-delta provenance is established.

### 3.5 Generated provenance and canonical descendant repairs

Generated/provenance lanes do not bypass canonical owners. #1738 and #1725 remain ordinary-forward zero-delta corrections.

Search detail-tabs #1760 is helper-free at `6da4f4ddee65e80524546dc25b370f2568ab59ba`, a real descendant of helper-free #1603 `d65a34773540147f568fab7aeeaf28835071ede2`, with exactly three Search detail-tab files as the parent-relative delta.

Projects #1764 is helper-free at `1f462b65fed368bf1db36b9fbdf364cf5e37483b`, a real descendant of #1352 `1b8497f33e1977ce7b963640b63f107510621973`, with exactly three Projects files.

Search exception-redaction #1765 is helper-free at `821d193d807ae952c4b2e96206008107e624177c`, a real descendant of canonical #1612 `3da3ae8e60e1bb049f59ae86bfe82db12b7e3cc7`. An intervening ordinary-forward commit `67b45d53873aac92d3f7cc5a477d0f53ae44cf57` had broadened the effective delta to 15 files, reintroduced raw exception-string logging, weakened `safe_logging`, and removed canonical regression tests. The repair preserves that history but restores the prior canonical tree by an ordinary non-force descendant commit. Fresh #1612→current comparison is ahead 8 / behind 0 with exactly `backend/api/search.py` and `backend/tests/test_search_exception_redaction_contract.py` as the effective delta. Search consumes canonical `redacted_exception_info(e)` and raises fixed HTTP details `from None`; the owner-boundary regression is no longer present in the effective tree.

These are source-topology PASS results, not Delivery PASS. Current `app-ci.yml` filters normal pull-request execution to bases `develop`, `master`, and `release/**`, so valid stacked children can lack normal exact-head hosted Application CI. #1691 owns correction of that repository-CI topology; child branches do not copy CI workflow source or predecessor receipts.

## 4. Material UI owner graph and Delivery Gate

Material UI acceptance requires normal/loading/empty/error/permission/responsive/interaction states, keyboard/focus/touch/accessibility evidence, current screenshots/E2E where applicable, and exact-head current evidence. shadcn/ui source use is not Storybook acceptance.

### 4.1 Tasks

[#1463](https://github.com/ContextualWisdomLab/naruon/pull/1463) remains the Tasks active-action owner. Delivery remains FAIL pending accepted #1691 browser ancestry, current artifact inspection, applicable security/AT evidence and independent review.

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

[#1767](https://github.com/ContextualWisdomLab/naruon/pull/1767) current exact `157894a526165005e686f81c1f7b7a14c39f1973` retains only the bounded `React.memo` optimization and parent-update render-body regression as its effective product/test delta. Historical exact `209a0fc2...` had Application CI `35925494000` GREEN and its focused CodeRabbit parent-update thread resolved, but Security `35925494018` later failed on six dependency findings inherited from the protected dependency state.

Intervening commit `f111866d1f28e1dc52fc770834af08048003032a` then crossed owner boundaries by modifying backend and frontend dependency files inside the NetworkGraph lane. Ordinary-forward repair `157894a...` preserves that history while restoring `backend/uv.lock`, `frontend/package.json`, and `frontend/pnpm-lock.yaml` to the previous owner-neutral blobs. `209a0fc2...`→`157894a...` is ahead 2 / behind 0 with zero effective file delta, and the repaired tree is exactly `e41e825b0675d7d80c56e9756031c8994570cdb0` again.

Fresh exact-current runs are Application CI `35965793616`, Security `35965793843`, CodeQL `35965793657`, Bandit `35965793743`, Semgrep `35965793668`, and Docker `35965794291`; all remain nonterminal at this observation. Predecessor receipts do not transfer. The historical formal `CHANGES_REQUESTED` review also remains non-approval. No representative large-graph profiler/browser/k6 measurement exists; no p95/main-thread performance claim is accepted. Delivery remains FAIL.

## 5. UI Localization Catalog

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single buyer-visible UI Localization Catalog Gap. [#1740](https://github.com/ContextualWisdomLab/naruon/pull/1740) exact `a2ed58691b8cb98abae9ee9acb51a2e4b4877cf9` owns only pure-domain locale/selection/validation policy for KO/EN/JA/ZH/VI/ES/DE/FR; it does not own persistence, HTTP publication, cache/runtime or Storybook UI.

The target contract is a normalized/versioned DB resource with `screen_key`, `message_key`, `locale_code` and `resource_version`; screen-scoped API/cache only; immutable complete publication; and a separate ontology-label ledger. Persistence descends from accepted #1503 ancestry. UI acceptance covers all eight locales in Storybook and real browser normal/loading/empty/error/permission states, keyboard/focus/screen-reader/touch, CJK wrapping/font fallback, Vietnamese diacritics, DE/FR/ES expansion, mobile/intermediate widths and no locale hydration flash.

Repository-local browser execution comes through accepted #1691. Current #1691 Data fixture repair remains staged/nonterminal and clean PostgreSQL remains #1694-owned. **Localization Delivery: FAIL.**

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

Current commercial blockers are: helper-free #1565 2.13.0/AnyIO-fixed product adoption and fresh resulting security evidence; #1623 accepted frontend dependency-security ancestry and combined repository-wide Security; #1694 fresh PostgreSQL bootstrap on accepted ancestry; #1691 stacked-PR trigger plus integrated real-browser evidence, including the Data evidence-snapshot fixture; downstream #1503 migration ancestry; protected integration of the #1549 LLM-governance correction after an immutable contextual-orchestrator API/client/schema release; full eight-locale persistence/publication/browser acceptance; central required security/review contexts; representative performance evidence where claimed; and one immutable Naruon release with SBOM/provenance/reproducibility/rollback.

The #1767 Trivy failure is evidence of these dependency blockers, not an exception that permits dependency source-copy into the NetworkGraph lane. Cross-owner lock/manifest changes must be ordinary-forward removed from product lanes and consumed later only through accepted canonical dependency ancestry.

No E2E exclusion/assertion weakening, duplicate owner, permanent source-fix workflow, predecessor receipt transfer, source-neutral wake commit, blind rerun, self-approval, force-push/destructive rebase, scanner suppression, mutable external-contract consumption or gate weakening is accepted.