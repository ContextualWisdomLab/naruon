# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.12  
**Observed on:** 2026-09-20 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

This file is the current product/technical authority overlay. Baseline v2.11 is preserved byte-for-byte at `docs/product-technical-gap-history/2026-09-20-baseline-v2.11.md`; the older v1.9 snapshot remains at `docs/product-technical-gap-history/2026-09-12-baseline-v1.9.md`. Historical snapshots and predecessor checks/reviews are audit material, not current merge or release authority.

## 1. Evidence and release posture

Authority order is protected code/runtime/migrations/tests → protected architecture/operations docs → exact current PR source and current-head evidence → open Issues/Proposed ADRs → historical snapshots. Pending, queued, stale, predecessor-head, skipped-required, neutral, local-only, author-only, or model-only evidence is not passing evidence.

The current repository shape is **281 open PRs and 75 open Issues**. Protected `develop` has 17 required contexts. The latest published Naruon release remains `v0.14.4` and is `immutable=false`; it is historical publication evidence, not a commercial immutable release candidate.

A releasable candidate requires one exact integrated protected head, terminal required contexts, zero valid unresolved review findings, qualifying independent post-last-push review, current security evidence, immutable publication identity, SBOM/provenance, reproducibility, rollback evidence, and buyer-visible acceptance for changed behavior.

## 2. Current central CI/security owner graph

Protected central authority is `.github/main@e6334e229581a918e2f22de18733b76fa65d7e71`, the protected merge of #2279 exact `d1e4380c15e948aaf104d46aa134fa614058782a`. GitHub REST authority validation, redirect refusal, bearer non-forwarding, evidence-lineage validation, and owner-qualified foreign Semgrep evidence are therefore protected ancestry; #2279 is not an open foundation prerequisite.

- `.github#712` remains the Actions execution-capacity owner. At this observation there are **401 queued / 0 in-progress** runs. This is not stable runner acquisition; do not generate source-neutral wake commits or blind unchanged-head reruns.
- `.github#2040@652764a37fc8af032f03cbe75da84ca88aee96bb` has now completed a second ordinary/non-force reconciliation onto protected `main@e6334e...`. Its base is current main, it is **175 ahead / 0 behind**, mergeable and Draft. The current generation preserves the scheduler/credential/no-restamp contracts, adopts the landed URL/redirect authority, and repairs repository identity so hostile embedded `..` and component-ending `.` fail before `gh api` while `.github` and `repo.name` remain valid. Exact-blob probes are GREEN; predecessor local evidence includes 586 focused and 3,438 passed / 28 skipped / 40 subtests, but fresh exact-head CodeQL, Python Security, Security, SAST, Runtime Quality and Trusted-uv runs remain queued and current-head independent approval is still required.
- `.github#2271@a0e1424de409ec474e7bc6e9f91a9e99b8a0915e` is the CodeQL dispatch repository-identity descendant. It is current-main based, Ready for review, mergeable, 8 ahead / 0 behind and still awaiting terminal exact-head checks plus qualifying independent approval.
- `.github#2275@572cfed270ae3b3cd38faca4d97ce028093e5373` is the GHAS `code-scanning/analyses` capability-selector descendant of current #2271. Its exact endpoint/header contract is locally verified, but capability selection does not create repository permission. It remains Draft pending #2271 acceptance, terminal exact-head checks, independent approval, and #2276.
- `.github#2272@cd3b41b8989e096d1ee375d332347c8bb819acf9` separately preserves the Pages caller-input shell/SAST lane while carrying landed #2279 ancestry. It remains Draft pending hosted exact-head Pages/security/SAST/CodeQL/runtime evidence and independent approval.
- `.github#2269@834d285f90241b4741247408001fd7534ce5a3b0` remains historical redirect/test-seam lineage. Do not close it until a lossless succession audit proves every valid delta/test/doctoring contract is present in protected central ancestry or an accepted successor.
- `.github#2276` remains the real target-repository permission/canary boundary for the reproduced `GET .../code-scanning/analyses` HTTP 403. Acceptance requires an unchanged-target canary that reads both protected-base and exact-head analyses and completes language pairing while 401/403/transport errors remain fail-closed.

Naruon must not copy central workflow source. It records owner identities and adopts accepted/released contracts through ordinary-forward consumer changes only.

## 3. Product owner boundaries

### Frontend dependency security

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the sole frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`. Prior GREEN evidence is generation-specific. Reacquire vulnerability-database evidence against the then-current protected ancestry after the central CodeQL/security control plane settles; do not copy dependency fixes into unrelated UI owners.

### Backend dependency security

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) owns the direct Starlette TestClient/httpx2 foundation at exact `52dfc863d1a5d6e4e80b6366f719dd09f2aa6172`. [#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) remains the dependent broad backend lane at exact `d096a5c235d2c1d8b5a5751cdd4e2c8cbba17c21`; its `aiosmtplib==5.1.3` security delta must survive, but a valid successor must also preserve #1565's direct `httpx2` contract and regenerate one coherent plain/hash/uv lock graph. Add hostile SMTP address/hostname and connection-lifecycle regressions before acceptance.

### LLM provider error confidentiality

[#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) remains the bounded owner at exact `9d9d5e0b4bde3febb7cef0e925e493c4fc16cd04`, Draft/open/mergeable. Production logs fixed event text plus bounded operation/exception-class metadata only, emits no provider exception string/traceback, and raises fixed `LLMServiceError` messages `from None`. Four-path hostile-canary coverage spans extraction, translation, OpenAI-compatible drafting and Ollama drafting. Ordinary child `9d9d5e0...` also restored TRACEABILITY deleted by generated child `1da2457...`. Its six exact-head hosted workflows remain queued; no predecessor receipt transfers.

### Workspace and migrations

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the sole canonical Alembic owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7` with one migration line: `0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`. No descendant may create a parallel head from protected `develop`.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains the bounded opaque-ID entropy descendant at exact `2ac48fb7e591827804ba8e7e911f211b0c134ddf`, retargeted to #1503. It retains the intervening generated commit but restores the deleted executable entropy regression and doctoring. Keep Draft and ordinary-adopt on the then-current #1503 lineage before acceptance.

### LLM governance/released contract

[#1548](https://github.com/ContextualWisdomLab/naruon/issues/1548) / [#1549](https://github.com/ContextualWisdomLab/naruon/pull/1549) remain the sole Naruon LLM-governance owner. `contextual-orchestrator` protected main is currently `5665b0ad1e07ffb5e9f8c59e44b6b2a785298013`, but its GitHub Releases inventory is empty. That mutable protected SHA is not a released API/client/schema identity. Naruon remains fail-closed until CO publishes an immutable versioned contract, then ordinary-bumps the consumer.

## 4. Buyer-visible UI and localization

[#1682](https://github.com/ContextualWisdomLab/naruon/pull/1682) remains the Calendar detail-sidebar owner at exact `477a333be738da0ca1f02faa809db98a59f250d2`. Its source/test contract removes fabricated event facts and inert controls and exposes honest disabled-action reasons. Exact-head Application CI, Bandit, Semgrep and Docker are GREEN; Security is RED specifically in `trivy-fs` while scorecard, dependency-review and OSV are GREEN; CodeQL compatibility verdicts for JavaScript/TypeScript, Actions and Python are RED at the current central dispatch verdict gate. Because this PR changes only frontend product/test files and `frontend/package.json`, do not patch central workflow or duplicate dependency-security ownership here. Route current vulnerability attribution/revalidation through #1623 and CodeQL control-plane repair through the central owner graph. UI Delivery remains FAIL until exact-head security/CodeQL plus qualifying post-change review/browser acceptance are terminal.

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single UI Localization Catalog Gap. The implementation must follow #1503's then-current migration head, use a product-owned DB-versioned screen-scoped resource, keep UI translation separate from ontology labels, support KO/EN/JA/ZH/VI/ES/DE/FR, and validate CJK/text expansion/font fallback/keyboard/focus/touch/a11y/responsive states in Storybook and real browser E2E. Do not broaden #1729 into the catalog implementation.

[#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) remains the bounded OIDC pending-state owner at exact `85e312360c6342f9bb02b6a6004b2a69599bd4e6`. Rendered interaction contracts exist, but real-browser keyboard/focus/touch/AT, responsive screenshots, eight-locale released resources and current-head independent acceptance remain missing. **UI Delivery Gate: FAIL.**

## 5. Generated-writer and governance boundaries

Generated branches are provenance, not new owners, when an existing canonical owner already covers the delta. #1727 and #1733 both demonstrate why generated commits must be inspected as intervening deltas: deleting executable tests or doctoring after a valid owner repair is a repair finding, not a reason to force-rewrite history. Preserve valid generated deltas, restore lost contracts ordinary-forward, remove task-specific self-modifying guidance after its durable purpose is complete, and never treat source-neutral `trigger CI` commits as acceptance evidence.

Issue #1178 and PR #1732 own the OpenSSF Best Practices evidence lane. Current proprietary licensing is an eligibility blocker for OpenSSF Passing, not a technical waiver item. This is a governance/legal lane unless the business explicitly makes Passing a release criterion; do not weaken licensing or branch protection to satisfy a badge.

## 6. Commercial Gap register

| Priority | Gap | Current boundary | Completion evidence |
| --- | --- | --- | --- |
| P0 | Release-train convergence | 281 open PRs; protected head unchanged | canonical owner inventory, parent-first integration, no orphaned valid delta, one immutable RC source SHA |
| P0 | Actions execution capacity | `.github#712`; 401 queued / 0 in-progress at observation | stable runner acquisition; obsolete pressure removed without cancelling sole current-head evidence; required lanes settle terminally |
| P0 | Central CI/security acceptance | #2279 landed; #2040 current-main reconciliation/source repair is complete at `652764a...`; #2271→#2275 and separate #2272 still await hosted/current-head acceptance; #2276 permission canary open | terminal exact-head checks + qualifying independent review + real unchanged-target GHAS canary + verified #2269 succession |
| P0 | Dependency-security freshness | frontend #1623 current-vulnerability revalidation; backend #1565→#1685 coherent lock/security reconciliation | current DB scans, coherent manifests/locks, hostile regression evidence, terminal CI/security/review |
| P0 | LLM provider error confidentiality | #1733 source/test/TRACEABILITY repair present; hosted generation queued | terminal current-head six-workflow evidence + zero valid findings + qualifying post-last-push approval |
| P0 | Workspace/migration convergence | #1503 sole migration line; downstream stacks must not fork it | one Alembic head, real PostgreSQL fresh/historical evidence, ordinary descendant restacks |
| P0 | Released LLM contract | CO main exists but Releases inventory is empty | immutable CO API/client/schema publication + Naruon consumer version bump + contract/E2E/security/SBOM/provenance evidence |
| P1 | Calendar buyer truth/a11y | #1682 product contract repaired; inherited security/central CodeQL gates still RED | current Trivy attribution/revalidation through owner path, central CodeQL verdict acceptance, browser/a11y/current-head review |
| P1 | UI localization | #1731 specified; no canonical DB/API implementation yet | eight-locale versioned resource + Storybook/browser/a11y + p95/API/cache/rollback evidence |
| P1 | OIDC interaction acceptance | #1729 jsdom contract only | real browser/AT/responsive/eight-locale current-head acceptance |
| P1 | Generated-writer owner lock | valid owner tests/doctoring have been deleted by generated children | semantic owner-overlap gate, protected test/doctoring invariants, no self-modifying residue |

## 7. Current causal order

1. Restore stable Actions runner acquisition through `.github#712`; do not blind-rerun unchanged heads.
2. Let #2040 exact `652764a...` settle terminal hosted checks and obtain qualifying current-head independent approval; source reconciliation and repository-identity repair are already present.
3. Accept #2271 `a0e1424...`, then #2275 `572cfed...`; independently accept Pages #2272 `cd3b41...`; prove #2269 succession and #2276 real unchanged-target analysis-read canary before claiming central CodeQL/GHAS acceptance.
4. Revalidate frontend dependency-security #1623 against the then-current vulnerability database; use it to resolve inherited Trivy findings rather than patching unrelated UI branches.
5. Integrate #1565 and ordinary/non-force reconcile #1685 so `httpx2` and `aiosmtplib==5.1.3` coexist in one coherent manifest/hash/uv graph with hostile SMTP/TestClient evidence.
6. Terminalize and independently review #1733 exact `9d9d5e0...` without reintroducing provider text, traceback logging or generated doctoring rollback.
7. Integrate #1694 → #1691 and prerequisites, then #1503 as the single migration lineage; ordinary-adopt #1727 and downstream workspace/Reply-SLA consumers on that protected ancestry.
8. After contextual-orchestrator publishes an immutable API/client/schema release, finish #1549 without mutable-owner binding.
9. Implement #1731 as the sole localization owner after the canonical migration lineage lands, then ordinary-adopt its released screen resources into #1729 and other UI surfaces.
10. Reacquire buyer-visible browser/a11y/responsive/localization evidence, build one exact integrated protected candidate, then publish immutable Naruon version/tag/package/GitHub Release with SBOM/provenance/reproducibility/rollback.

**Merge/Release Gate: FAIL.** Source repairs and local evidence do not substitute for terminal exact-head hosted checks, qualifying independent review, real external permission evidence, current security scans, released owner contracts, buyer-visible UI acceptance, or immutable publication.
