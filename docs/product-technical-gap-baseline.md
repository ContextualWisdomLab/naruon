# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.20  
**Observed on:** 2026-09-20 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

This file is the current product/technical authority overlay. v2.19 remains audit-visible as blob `23cfa4c3ec24177741b8e05c45896edc540a1536`; v2.18 remains blob `25ec56b6493a1ed577ce4481072d6db6c74ec7eb`; v2.17 remains blob `d611e0d3cb1dd90e9d8429fcfa112a977e989726`. Earlier snapshots remain audit material in Git ancestry and `docs/product-technical-gap-history/`. Historical evidence is not current merge or release authority.

## 1. Evidence and release posture

Authority order is protected code/runtime/migrations/tests → protected architecture/operations docs → exact current PR source and current-head evidence → open Issues/Proposed ADRs → historical snapshots. Pending, queued, stale, predecessor-head, skipped-required, neutral, local-only, author-only, or model-only evidence is not passing evidence.

Current repository inventory remains **284 open PRs and 75 open Issues**. Protected `develop` remains exact `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required contexts. Latest published Naruon release remains `v0.14.4`, `immutable=false`; it is historical publication evidence, not a commercial immutable release candidate.

A releasable candidate requires one exact integrated protected head, terminal required contexts, zero valid unresolved review findings, qualifying independent post-last-push review, current security evidence, immutable publication identity, SBOM/provenance, reproducibility, rollback evidence, and buyer-visible acceptance for changed behavior.

## 2. Central CI/security owner graph

Protected central authority remains `.github/main@e6334e229581a918e2f22de18733b76fa65d7e71`, the protected merge of #2279 exact `d1e4380c15e948aaf104d46aa134fa614058782a`. GitHub REST authority validation, redirect refusal, bearer non-forwarding, evidence-lineage validation, and owner-qualified foreign Semgrep evidence are protected ancestry; #2279 is not an open prerequisite.

- `.github#712` remains the Actions execution-capacity owner. Fresh observation before this generation is **217 queued / 1 in progress**. That is materially lower than the earlier 600–780 backlog, but one in-progress run against a three-digit queue is not stable capacity. The sole in-progress sample is the long-running protected-main Strix scan. Preserve sole current-head evidence, remove only obsolete/superseded pressure through the canonical owner path, distinguish runner acquisition from workflow parse/admission defects, and do not create source-neutral wake commits or blind reruns.
- `.github#2040@7901ca565fb93a9e869cd4136476384ac3a07bdf` remains Draft/mergeable on current protected main. Its repository-identity repair and ordinary current-main reconciliation are retained. The newest Trusted-uv change adds the Noema document hash lock to trigger/cache/install closure, but that responsibility overlaps canonical repository-wide full-suite owner `.github#1911@dfeadc7adfb02d73e166104f2987f14fbf7fe82e`. #1911 must ordinary-reconcile onto current protected main first; #2040 must then adopt/adapt the canonical result instead of retaining a parallel owner. Current #2040 CodeQL/SAST/Python Security/Runtime Quality/Trusted-uv/Security evidence is nonterminal.
- `.github#2271` advanced to exact `8da5f48fa0438ff33c766f03325f6e7f2a77dd9d`, tree `8c129bc3266842d6e244175894bd1f40f22ba1f5`, **21 ahead / 0 behind** protected main. Python Security on the prior generation found `anyio 4.14.0` CVEs; the current owner ordinary-adopts canonical AnyIO owner #2278 and retains the repository-identity admission delta while replacing only the canonical hash lock with `anyio==4.14.2`. Fresh exact-head SAST/Python Security/Security/CodeQL evidence is queued/nonterminal. It remains Draft/Proposed.
- `.github#2275` was stale behind the moved #2271 parent and is now ordinary-restacked at exact `0d68d7a8435652edc288d7bb3dfb06a7c8a59eb6`, tree `6291c5b021562995fd94665efa5d96ced281a1e3`. Compare from current #2271 is **ahead 11 / behind 0 / merge base exact #2271**, with only the three GHAS credential-routing paths differing from the parent. The current tree therefore retains the canonical AnyIO fix while preserving the endpoint/header/capability-selector contract. No predecessor check/review receipt transfers. #2276 still must prove real target-repository `code-scanning/analyses` permission.
- `.github#2291@782d67b433aa71cf2c81b2a81f55ae192a317f3b` remains the canonical Strix trusted-binder/runtime owner and is Ready for review, not merge-accepted. `STRIX_REPO_ROOT` is the consumer scan/artifact root; gate/model helper/binder remain trusted-source-owned. Fresh hosted acceptance and qualifying approval remain required.
- `.github#2272` advanced to exact `f5b96a4cb8add16208a3c8dbacd99d94b65b4bcb`, still stacked on #2291. It preserves the trusted-binder convergence and now adds a Pages caller-input validation boundary before credentialed Wrangler execution. The exact current head has seven effective paths and remains Draft/Proposed with fresh hosted acceptance and independent review pending.
- `.github#2269` remains historical redirect/test-seam lineage until a lossless succession audit proves all valid contracts are preserved. `.github#2276` remains the unchanged-target GHAS permission/canary boundary.

Naruon does not copy central workflow source. It records owner identities and consumes accepted/released contracts through ordinary-forward changes only.

## 3. Product owner boundaries

### Dependency and security ownership

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the sole frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`; current vulnerability-database evidence must be reacquired before inherited Trivy findings are treated as resolved.

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the bounded Starlette TestClient/httpx2 owner at exact `52dfc863d1a5d6e4e80b6366f719dd09f2aa6172`. [#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) is retargeted to #1565 but is not yet a valid Git descendant and does not preserve the direct `httpx2` development/TestClient contract. Preserve #1685's `aiosmtplib==5.1.3`, ordinary/non-force reconcile onto #1565, regenerate one coherent `pyproject.toml` / plain requirements / hashed requirements / `uv.lock` graph, then reacquire installation, warnings-as-errors, TestClient selection, hostile SMTP/lifecycle, Security and CodeQL evidence. Never hand-edit generated lock/hash material.

[#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) remains the bounded LLM-provider error-confidentiality owner at exact `9d9d5e0b4bde3febb7cef0e925e493c4fc16cd04`, Draft/open/mergeable. Provider text/traceback suppression plus four-path hostile canaries and restored TRACEABILITY are source-complete, but exact-head hosted acceptance remains incomplete.

### Workspace, migrations and opaque identifiers

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the sole canonical Alembic/bootstrap owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`; descendants must not create parallel migration/bootstrap heads from protected `develop`.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains the sole opaque-UID backfill entropy owner at exact `2ac48fb7e591827804ba8e7e911f211b0c134ddf`, stacked on #1503. Generated direct-`develop` PR [#1736](https://github.com/ContextualWisdomLab/naruon/pull/1736) remains Draft provenance only at `46c7a9b3a6472f4e4188964ee1778bc99960d752` with zero effective product delta.

### LLM governance / released contract

[#1548](https://github.com/ContextualWisdomLab/naruon/issues/1548) / [#1549](https://github.com/ContextualWisdomLab/naruon/pull/1549) remain the sole Naruon LLM-governance owner. `contextual-orchestrator` protected `main@5665b0ad1e07ffb5e9f8c59e44b6b2a785298013` remains mutable owner source and its GitHub Releases inventory remains empty. Naruon remains fail-closed and must not bind a mutable owner head as a released API/client/schema contract.

## 4. Buyer-visible UI, Storybook and localization

[#1682](https://github.com/ContextualWisdomLab/naruon/pull/1682) remains the Calendar buyer-truth/detail-sidebar owner. Application CI/Bandit/Semgrep/Docker evidence does not override inherited Trivy and central CodeQL verdict failures. UI Delivery remains FAIL until exact-head security/CodeQL, browser/a11y and qualifying review evidence are terminal.

### Storybook/design-system owner graph

[#1354](https://github.com/ContextualWisdomLab/naruon/pull/1354) is the bounded **static token-contract precursor**, not executable Storybook delivery. It has now been repaired onto canonical frontend dependency-security owner #1623 without changing package/lock/runtime source:

- predecessor `655c97376d0c5ad4560f96973663d55add76d082` remains first-parent ancestry;
- exact current `42e11bcf01de90c3b2045f9adc2c41a566062057` ordinary-adopts #1623 `509be4c...` as additional parent;
- current compare from #1623 is ahead-only / 0 behind with merge base exact #1623;
- the effective PR delta remains exactly five additive files: three design/doctoring documents, `storybook-design-tokens.css`, and its regression test.

Its old repository-local GREEN receipts are predecessor evidence after the restack. The new exact head requires fresh terminal checks and qualifying independent review. UI Delivery remains FAIL because this lane deliberately has no runtime/config/stories or browser/a11y evidence.

Open [#1436](https://github.com/ContextualWisdomLab/naruon/pull/1436) is the **existing executable Storybook/runtime lineage** and must be repaired rather than replaced with a new duplicate writer. It is currently exact `034d2ff4e0d120d1e7b7669b35ea8eea7d8c1221`, Draft/non-mergeable on a historical base with 28 changed files. Its valid runtime/config/story intent is mixed with stale or cross-owner deltas:

- package/lock security belongs to #1623; do not transplant #1436's historical lock over the security owner;
- the static token taxonomy belongs to current #1354 and should be ordinary-adopted;
- `docs/product-technical-gap-baseline.md` belongs solely to #1602;
- reusable/shared workflow authority follows the central `.github` owner path rather than a feature-lane `.github/workflows/app-ci.yml` fork;
- confidence semantics belong to #1559's strict backend `0..100` contract; #1436's historical `[0,2)` unit-interval inference is obsolete and must not be revived;
- unintegrated ADR-0013/0014 `Accepted` status is premature; surviving Storybook architecture remains Proposed until landed evidence, while obsolete confidence semantics should be superseded by #1559;
- `DecisionPointCard`, `EmailDetail`, `SearchLayout`, product-events and related tests require fresh component/domain owner-overlap review before retention.

Required executable Storybook reconstruction is therefore **#1623 → #1354 → repaired #1436**, using a resolver-backed coherent package/lock graph, valid Storybook runtime/config/stories only, deterministic static build, no remote font/image/analytics/telemetry dependency, normal/loading/empty/error/permission/destructive/busy state coverage, keyboard/focus/touch/responsive/200%-zoom evidence, WCAG-oriented browser automation, manual accessible-name/AT evidence, current Figma mapping, terminal exact-head checks, and qualifying independent review. Do not hand-edit a stale lockfile to manufacture convergence.

### Tasks async loading feedback

[#1463](https://github.com/ContextualWisdomLab/naruon/pull/1463) remains the canonical Tasks async-loading owner. Exact `bf9ce8e8f5ad1b4cf2f2ddc9c5f547a7d733f60e` repairs the prior shared-busy RED with action-specific `pending_action`, preserving mutual exclusion while assigning `aria-busy`, Loader2 and busy label only to the initiating action. Fresh repository workflows exist but remain nonterminal; real-browser keyboard/focus/touch/responsive/AT evidence and qualifying independent review remain absent. **UI Delivery Gate therefore remains FAIL despite source-level functional repair.**

Generated duplicate [#1735](https://github.com/ContextualWisdomLab/naruon/pull/1735) remains ordinary-restacked zero-effective-delta provenance at `b53d2018a14ec0aa2ed778142d04ef4abd7be1d7` and must be reswept if #1463 moves again.

### Localization and interaction ownership

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single DB-versioned, screen-scoped UI Localization Catalog Gap for KO/EN/JA/ZH/VI/ES/DE/FR. It follows canonical migration lineage, keeps UI translation separate from ontology labels, avoids whole-catalog browser loading, and requires CJK/text expansion/font fallback/keyboard/focus/touch/a11y/responsive evidence. [#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) remains the bounded OIDC interaction-state owner rather than a parallel localization implementation.

## 5. Generated-writer and descendant invariants

Generated branches are provenance, not new owners, when an existing canonical owner already covers the delta. Existing examples include #1728 cross-owner dependency/security/performance rollback, #1734 duplicate NetworkGraph work, #1735 duplicate Tasks loading UX, and #1736 duplicate opaque-ID security work.

Every generated descendant/new duplicate must be checked semantically for owner overlap, source/test/fixture deletion, dependency/security/performance regression, severity/rule misclassification, scratch artifacts, duplicate CHANGELOG/doctoring, and self-modifying guidance. Preserve valid ancestry, ordinary-forward to the canonical owner tree/contract, convert duplicate lanes to Draft provenance, and never transfer predecessor hosted receipts.

Canonical-owner movement invalidates an earlier zero-delta or stacked relation. Descendants must be freshly compared and ordinary-restacked when necessary. This applies to generated provenance and to normal central stacks: this generation repaired #2275 immediately after #2271 moved to adopt #2278's AnyIO security owner.

Issue #1178 and PR #1732 remain the OpenSSF governance/legal lane. Current proprietary licensing is an eligibility blocker for OpenSSF Passing, not a technical waiver; do not weaken licensing or branch protection for badge attainment.

## 6. Commercial Gap register

| Priority | Gap | Current boundary | Completion evidence |
| --- | --- | --- | --- |
| P0 | Release-train convergence | 284 open PRs; protected head unchanged; owner movement requires descendant resweep | parent-first integration, no orphaned valid delta, one immutable RC source SHA |
| P0 | Actions execution capacity | `.github#712`; 217 queued / 1 in progress at this generation | stable runner acquisition, parse/admission RCA separated, obsolete pressure removed without cancelling sole current-head evidence |
| P0 | Central CI/security acceptance | #2040/#1911 owner overlap; #2271→#2275 repaired current; #2291→#2272; #2276 canary pending | canonical-owner convergence, terminal exact-head checks, qualifying independent review, #2269 succession, unchanged-target GHAS canary |
| P0 | Dependency-security freshness | frontend #1623 revalidation; backend #1565→#1685 real ancestry/coherent graph repair | current vulnerability scans, coherent manifests/locks, hostile regressions, terminal CI/security/review |
| P0 | LLM provider error confidentiality | #1733 source/test/TRACEABILITY repair present | terminal current-head hosted evidence + zero valid findings + qualifying review |
| P0 | Workspace/migration convergence | #1503 sole migration line; #1727 sole opaque-ID descendant; #1736 provenance | one Alembic head, real PostgreSQL fresh/historical execution, ordinary descendant restacks |
| P0 | Released LLM contract | contextual-orchestrator release inventory empty | immutable API/client/schema publication + consumer bump + contract/E2E/security/SBOM/provenance |
| P1 | Tasks loading interaction | #1463 source-level RED→GREEN; #1735 zero-delta provenance | exact-head hosted GREEN, browser keyboard/focus/touch/responsive/AT evidence, qualifying review |
| P1 | Executable Storybook/design system | #1354 static owner now on #1623; #1436 is dirty existing runtime lineage | owner-safe #1436 reconstruction, coherent resolver-produced lock, representative states, browser/a11y/responsive evidence, token/Figma audit |
| P1 | UI localization | #1731 specified; implementation not protected | eight-locale versioned resource + Storybook/browser/a11y + cache/API/rollback evidence |
| P1 | OIDC interaction acceptance | #1729 rendered contract incomplete | real browser/AT/responsive/eight-locale current-head acceptance |
| P1 | Generated/descendant owner lock | #1728/#1734/#1735/#1736 + central #2271→#2275 movement | semantic owner-overlap gate, owner-movement descendant sweep, canonical-tree/delta check, no scratch/self-modifying residue |

## 7. Current causal order

1. Restore stable Actions runner acquisition through `.github#712`; reduced backlog is not yet stable capacity.
2. Reconcile `.github#1911` onto current protected main and converge its canonical Trusted-uv/full-suite dependency closure with #2040; terminalize #2040 without duplicate ownership.
3. Terminalize current #2271 `8da5f48...` → current-restacked #2275 `0d68d7a...`; separately terminalize #2291 `782d67b...` → #2272 `f5b96a4...`; prove #2269 succession and #2276 unchanged-target GHAS canary.
4. Revalidate frontend dependency-security #1623 against current vulnerability data.
5. Preserve #1565 as the bounded TestClient/httpx2 owner; ordinary/non-force reconcile #1685 and regenerate one coherent dependency graph before hosted acceptance.
6. Terminalize #1733 without reintroducing provider text, traceback logging or generated TRACEABILITY rollback.
7. Integrate #1694 → #1691 and prerequisites, then #1503 as the sole migration lineage; ordinary-adopt #1727 and downstream consumers. Keep #1736 provenance only.
8. After contextual-orchestrator publishes an immutable API/client/schema release, finish #1549 without mutable-owner binding.
9. Implement #1731 as the sole localization owner, then ordinary-adopt released screen resources into #1729 and other UI surfaces.
10. Terminalize #1463 exact `bf9ce8e...` with hosted gates, real browser keyboard/focus/touch/responsive/AT evidence and qualifying independent review; keep #1735 aligned if the owner moves.
11. Terminalize the static design-token chain #1623 → #1354 `42e11bc...`, then reconstruct existing #1436 as the executable Storybook lane without stale dependency, CI, baseline, confidence or product-domain ownership. Acquire current Figma/Storybook/browser/a11y evidence.
12. Reacquire buyer-visible acceptance, build one exact integrated protected candidate, then publish an immutable Naruon version/tag/package/GitHub Release with SBOM/provenance/reproducibility/rollback.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL.** Source repairs and local evidence do not substitute for terminal exact-head hosted checks, qualifying independent review, current security scans, real external permission evidence, released owner contracts, buyer-visible UI acceptance, or immutable publication.
