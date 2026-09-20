# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.24  
**Observed on:** 2026-09-20 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

This file is the current product/technical authority overlay. v2.23 remains audit-visible as blob `a46b95e7e7d7135c5d9d9afd45b17145b37ade9f`; v2.22 remains audit-visible as blob `6e6608fd2da9c1105215ba325d4999dffb7b484e`; v2.21 remains blob `b993307ebcd05fb9f09090bb85f02af7697e2be1`; v2.20 remains blob `a9e35592842c7b06bc78181e7d6fe25a20843e91`; v2.19 remains blob `23cfa4c3ec24177741b8e05c45896edc540a1536`. Earlier snapshots remain audit material in Git ancestry and `docs/product-technical-gap-history/`. Historical evidence is not current merge or release authority.

## 1. Evidence and release posture

Authority order is protected code/runtime/migrations/tests → protected architecture/operations docs → exact current PR source and current-head evidence → open Issues/Proposed ADRs → historical snapshots. Pending, queued, cancelled, stale, predecessor-head, skipped-required, neutral, local-only, author-only, model-only, or source-neutral wake evidence is not passing evidence.

Fresh repository inventory before this generation is **286 open PRs and 75 open Issues**. Protected `develop` remains exact `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required contexts. Latest published Naruon release remains `v0.14.4`, `immutable=false`; it is historical publication evidence, not a commercial immutable release candidate.

A releasable candidate requires one exact integrated protected head, terminal required contexts, zero valid unresolved review findings, qualifying independent post-last-push review, current security evidence, immutable publication identity, SBOM/provenance, reproducibility, rollback evidence, and buyer-visible acceptance for changed behavior.

## 2. Central CI/security owner graph

Protected central authority remains `.github/main@e6334e229581a918e2f22de18733b76fa65d7e71`, the protected merge of #2279 exact `d1e4380c15e948aaf104d46aa134fa614058782a`. GitHub REST authority validation, redirect refusal, bearer non-forwarding, evidence-lineage validation, and owner-qualified foreign Semgrep evidence are protected ancestry; #2279 is not an open prerequisite.

- `.github#712` remains the Actions execution-capacity owner. Two consecutive fresh observations immediately before this generation were **220 queued / 2 in progress**. The newest queued sample is still a `repository_dispatch` against protected `main@e6334e...`, while long-running Strix/review work occupies scarce execution. Raw queue totals therefore remain insufficient: preserve sole current-head evidence and distinguish workflow generation/admission, first runner acquisition, downstream runner acquisition, and terminal cancellation/preemption. Do not create source-neutral wake commits or blind unchanged-head reruns.
- Canonical repository-wide/full-suite Trusted-uv owner `.github#1911` is exact `c965664a6d7fe0b75bf7ea019a9059220a32f06b`, ordinary-reconciled to current protected main. The predecessor `169852c7...` correctly reduced the protected-base owner delta, but its retained contract test still encoded the older two-job/path-filter design. Current `c965664a...` repairs the test to the actual single hardened job, unfiltered `push: main`, exact PR-head/main-push checkout semantics, and both hash-locked OpenCode/Noema dependency closures. Fresh current-head hosted evidence is **not GREEN**: Python Security `35484950365`, SAST `35484950385`, Security `35484950398`, Trusted-uv `35484950390`, and CodeQL `35484950369` are all terminal **CANCELLED**. Keep Draft and route execution RCA through #712 rather than mutating source to manufacture another generation.
- `.github#2040@bd039185ddf8df88480971cdd3b69c38f4558609` has completed Trusted-uv owner convergence by ordinary-adopting exact #1911 `c965664a...`; neither the Trusted-uv workflow nor its contract test remains in #2040's effective delta. #2040 therefore retains only its distinct CodeQL scheduler/credential/runtime-quality and related documentation/test surface. Hosted acceptance remains incomplete: SAST `35484975926`, Security `35484975879`, Python Security `35484975909`, Trusted-uv `35484975956`, and Runtime Quality `35484975898` are **CANCELLED** while CodeQL `35484975910` remains nonterminal. No #1911 or predecessor receipt transfers.
- `.github#2291@782d67b433aa71cf2c81b2a81f55ae192a317f3b` remains the canonical Strix trusted-binder/runtime owner. `STRIX_REPO_ROOT` is the consumer scan/artifact root; gate/model helper/binder remain trusted-source-owned. Fresh hosted acceptance and qualifying approval remain required.
- `.github#2109@42e3f7a8cbb03b117c898d3e125af87a5c6ce86b` is the canonical required-workflow lifecycle/stacked-base admission owner, stacked on #2291 and currently **Draft**, not protected ancestry. Its current tree is unchanged from predecessor `f62172a...`; the later stale-generation oracle was withdrawn rather than becoming a second scheduler owner. On this same exact tree, a Ready transition generated CodeQL, Python Security, Runtime Quality, SAST and Security for the stacked base; converting the PR back to Draft cancelled the queued heavy Ready generation, while the latest Draft generation skips the heavy jobs/produces no CodeQL job. This validates the bounded Ready/Draft admission lifecycle, including stacked-base admission and Draft withdrawal behavior, but is not hosted GREEN or protected acceptance. #2283/#2289 retain exact-head review scheduling/predecessor-cleanup ownership. Naruon and #2275 must consume the accepted central contract rather than copy workflow source.
- `.github#2271@8da5f48fa0438ff33c766f03325f6e7f2a77dd9d` ordinary-adopts canonical AnyIO owner #2278 and retains repository-identity admission while using `anyio==4.14.2`. Current Python Security `35480431734`, SAST `35480431728`, and Security `35480431743` are terminal **CANCELLED** while CodeQL `35480431778` remains nonterminal; this is incomplete acceptance, not recurrence of the pre-adoption AnyIO source RED.
- `.github#2275@0d68d7a8435652edc288d7bb3dfb06a7c8a59eb6` is ordinary-restacked on current #2271, ahead 11 / behind 0 with merge base exact parent, preserving only the bounded GHAS credential-routing delta. Its current SAST `35480836004` and Security `35480836015` are terminal **CANCELLED**, CodeQL `35480836023` remains nonterminal, and **no Python Security generation exists** because protected `python-security.yml` still admits PR bases only `[main, master, develop]` while #2275 targets a stacked owner branch. Treat this as deterministic admission omission owned by #2109, not runner starvation or #2275 source failure. After #2109 is accepted/protected, #2275 itself must reacquire Python Security/Runtime Quality on its own exact head; #2109 canary receipts do not transfer. #2276 still must prove real target-repository `code-scanning/analyses` permission.
- `.github#2272@f5b96a4cb8add16208a3c8dbacd99d94b65b4bcb` remains stacked on #2291, preserving trusted-binder convergence and adding the Pages caller-input validation boundary before credentialed Wrangler execution. It remains Draft/Proposed pending fresh hosted acceptance and review.
- `.github#2269` remains historical redirect/test-seam lineage until a lossless succession audit proves all valid contracts are preserved. `.github#2276` remains the unchanged-target GHAS permission/canary boundary.

Naruon does not copy central workflow source. It records owner identities and consumes accepted/released contracts through ordinary-forward changes only.

## 3. Product owner boundaries

### Dependency and security ownership

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the sole frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`; current vulnerability-database evidence must be reacquired before inherited Trivy findings are treated as resolved. Consumer evidence from #1733 predecessor exact `9d9d5e0...` now includes Security Scan `35450922558` failing specifically in `trivy-fs` job `105968932721`. #1733 changes no dependency manifest/lockfile and its frontend snapshot still carries the protected-line `next`/`eslint-config-next 16.2.12`, while #1623 carries the newer `16.3.4` dependency-security floor. The connector does not expose the failing Trivy print-step output, so no specific CVE is attributed from that run; repair/revalidation remains here rather than broadening #1733.

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the bounded Starlette TestClient/httpx2 owner at exact `52dfc863d1a5d6e4e80b6366f719dd09f2aa6172`. [#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) is retargeted to #1565 but is not yet a valid Git descendant and does not preserve the direct `httpx2` development/TestClient contract. Preserve #1685's `aiosmtplib==5.1.3`, ordinary/non-force reconcile onto #1565, regenerate one coherent `pyproject.toml` / plain requirements / hashed requirements / `uv.lock` graph, then reacquire installation, warnings-as-errors, TestClient selection, hostile SMTP/lifecycle, Security and CodeQL evidence. Never hand-edit generated lock/hash material.

[#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) remains the bounded LLM-provider error-confidentiality owner at exact `2b47bc7b57732d0dbe00db1ba498b49cdb512e8b`, Draft/open/mergeable. A second intervening generated child `958cf7765d0cd1d6f4163938dfb648aa241712b8` repeated the earlier doctoring/TRACEABILITY rollback without changing production source or the four-path hostile-canary regression; ordinary-forward `2b47bc7...` retains that ancestry and restores the stronger traceability record. The predecessor exact `9d9d5e0...` had Application CI/SAST/Bandit/Docker GREEN but Security `35450922558` terminal **FAILURE** in `trivy-fs`, now routed to #1623 as inherited dependency evidence; CodeQL never terminalized before the head moved. Current exact `2b47bc7...` has a fresh six-workflow generation (`35501312839`, `35501312832`, `35501312851`, `35501312870`, `35501312824`, `35501313014`) still queued/pending. No predecessor check/review receipt transfers, and there is no qualifying independent current-head approval.

### Workspace, migrations and opaque identifiers

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the sole canonical Alembic/bootstrap owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`; descendants must not create parallel migration/bootstrap heads from protected `develop`.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains the sole opaque-UID backfill entropy owner at exact `2ac48fb7e591827804ba8e7e911f211b0c134ddf`, stacked on #1503. Generated direct-`develop` PR [#1736](https://github.com/ContextualWisdomLab/naruon/pull/1736) remains Draft provenance only at `46c7a9b3a6472f4e4188964ee1778bc99960d752` with zero effective product delta.

### LLM governance / released contract

[#1548](https://github.com/ContextualWisdomLab/naruon/issues/1548) / [#1549](https://github.com/ContextualWisdomLab/naruon/pull/1549) remain the sole Naruon LLM-governance owner. `contextual-orchestrator` protected `main@5665b0ad1e07ffb5e9f8c59e44b6b2a785298013` remains mutable owner source and its GitHub Releases inventory remains empty. Naruon remains fail-closed and must not bind a mutable owner head as a released API/client/schema contract.

## 4. Buyer-visible UI, Storybook and localization

[#1682](https://github.com/ContextualWisdomLab/naruon/pull/1682) remains the Calendar buyer-truth/detail-sidebar owner. Application CI/Bandit/Semgrep/Docker evidence does not override inherited Trivy and central CodeQL verdict failures. UI Delivery remains FAIL until exact-head security/CodeQL, browser/a11y and qualifying review evidence are terminal.

### Storybook/design-system owner graph

[#1354](https://github.com/ContextualWisdomLab/naruon/pull/1354) is the bounded static token-contract precursor, not executable Storybook delivery. Exact current `42e11bcf01de90c3b2045f9adc2c41a566062057` ordinary-adopts #1623 `509be4c...`; its effective delta remains exactly five additive design/doctoring/token-regression files and deliberately excludes package/lock/runtime Storybook source. Fresh terminal checks and qualifying independent review remain required.

Open [#1436](https://github.com/ContextualWisdomLab/naruon/pull/1436) is the existing executable Storybook/runtime lineage and must be repaired rather than replaced. Exact `034d2ff4e0d120d1e7b7669b35ea8eea7d8c1221` remains Draft/non-mergeable on a historical base with mixed valid runtime/config/story intent and stale cross-owner deltas. Package/lock security belongs to #1623; static token taxonomy belongs to #1354; this Gap ledger belongs to #1602; shared CI follows central `.github`; confidence semantics follow #1559's strict backend `0..100` contract; unintegrated Storybook ADRs remain Proposed; component/domain files require owner-overlap review before retention.

Required executable Storybook reconstruction is **#1623 → #1354 → repaired #1436**, using a resolver-backed coherent package/lock graph, valid runtime/config/stories only, deterministic static build, no remote font/image/analytics/telemetry dependency, normal/loading/empty/error/permission/destructive/busy state coverage, keyboard/focus/touch/responsive/200%-zoom evidence, WCAG-oriented browser automation, manual accessible-name/AT evidence, current Figma mapping, terminal exact-head checks, and qualifying independent review.

### Tasks async loading feedback

[#1463](https://github.com/ContextualWisdomLab/naruon/pull/1463) remains the canonical Tasks async-loading owner. Exact `bf9ce8e8f5ad1b4cf2f2ddc9c5f547a7d733f60e` repairs the prior shared-busy RED with action-specific `pending_action`, preserving mutual exclusion while assigning `aria-busy`, Loader2 and busy label only to the initiating action. Fresh exact-head Application CI, CodeQL, Security, Semgrep, Bandit and Docker generations all remain queued; all review threads are resolved/outdated, but there is still no qualifying independent post-last-push approval. Real-browser keyboard/focus/touch/responsive/AT evidence is also absent. **UI Delivery Gate remains FAIL despite source-level functional repair.**

Generated duplicate [#1735](https://github.com/ContextualWisdomLab/naruon/pull/1735) is ordinary-restacked zero-effective-delta provenance at `b53d2018a14ec0aa2ed778142d04ef4abd7be1d7` against current #1463 and must be reswept if #1463 moves again.

### Settings native-disabled semantics

[#1676](https://github.com/ContextualWisdomLab/naruon/pull/1676) remains the sole Settings native-disabled semantics owner. Causal source/doctoring head `1c8701e20984b54c13aeded2e975af3317a3b369` and live exact `8a3ac51662fbe8e49f26a317ac0afe85f853c9ac` have the same tree `44359ea501bbe94e8a82aa1deb8e34e4b2c514b2`; the two later commits are source-neutral ancestry, not product progress or refreshed acceptance evidence. Exact-live-head hosted/browser/keyboard/responsive evidence and qualifying independent review remain pending.

Fresh generated duplicate [#1737](https://github.com/ContextualWisdomLab/naruon/pull/1737) initially reimplemented the same two-line `aria-disabled` removal plus task-specific `.jules/palette.md` guidance directly from `develop`. It has been repaired ordinary-forward at exact `3c8c02ff97f80c264088dd1664ba8590db574c14`: generated predecessor remains first-parent provenance, current #1676 `8a3ac516...` is the additional parent/base, current tree equals #1676, and the PR is Draft with zero effective product delta. #1737 is not an independent accessibility owner.

### Design-QA fidelity and mobile state delivery

Fresh generated [#1738](https://github.com/ContextualWisdomLab/naruon/pull/1738) exposed a buyer-visible correctness regression, not acceptable visual polish. Its generated predecessor `959dc2d6674e36623b0e75ea62d64d303ae7d736` hard-coded participant count `3명 (수신 2, 참조 1)`, invented attachment filenames `Q2_Plan_Draft.pdf` and `budget_v2.xlsx`, rendered `제안 확인` as a visible action without a handler, and added three static mobile cards without authoritative data, mounted buyer-path proof, or normal/loading/empty/error/permission interaction contracts. Task-specific `.jules/palette.md` explicitly recommended visual placeholders until real data was wired.

Current corrective child `b6bd7f6483266cf296395ba8fbbd9c3c280ab201` preserves the generated predecessor in ancestry but restores the exact protected-`develop` tree, making #1738 Draft provenance with zero effective product delta. The fabricated content, dead CTA, static panels and placeholder doctrine are therefore quarantined rather than shipped.

Closed historical #1193 proposed the same participant/attachment/meeting + mobile-panel slice and was closed to “drain PR queue” without a verified successor. Its tree contained the same class of hard-coded placeholder data and dead actions. That closure is not evidence that the valid product requirement was delivered, and its stale broad tree must not be restored wholesale.

The surviving requirement is still real and must be routed through canonical product owners: EmailDetail participant/attachment/calendar behavior must use authoritative mail/thread/attachment/calendar contracts after owner/succession surgery of the relevant historical lineage; mobile workspace state composition must extend #1570 or a verified bounded successor with real data and mounted interactions. Completion requires no fabricated production content, no dead action, normal/loading/empty/error/permission states, real touch/keyboard/focus/AT/responsive evidence, current-head browser/E2E/screenshots, and qualifying review. **UI Delivery Gate for this slice is FAIL.**

### Localization and interaction ownership

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single DB-versioned, screen-scoped UI Localization Catalog Gap for KO/EN/JA/ZH/VI/ES/DE/FR. It follows canonical migration lineage, keeps UI translation separate from ontology labels, avoids whole-catalog browser loading, and requires CJK/text expansion/font fallback/keyboard/focus/touch/a11y/responsive evidence. [#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) remains the bounded OIDC interaction-state owner rather than a parallel localization implementation.

## 5. Generated-writer and descendant invariants

Generated branches are provenance, not new owners, when an existing canonical owner already covers the delta. Current examples include #1728 cross-owner dependency/security/performance rollback, #1734 duplicate NetworkGraph work, #1735 duplicate Tasks loading UX, #1736 duplicate opaque-ID security work, and #1737 duplicate Settings semantics.

Generated design work is also rejected when it fabricates buyer truth or creates dead interactions. #1738 is the current exemplar: ancestry is retained but its effective tree is restored to protected `develop` until the valid intent is implemented by the proper product owners. A generated UI cannot pass Delivery Gate merely because decorative accessibility attributes are present.

Every generated descendant/new duplicate must be checked semantically for owner overlap, source/test/fixture deletion, dependency/security/performance regression, fabricated buyer-visible data, dead CTA, unmounted/static interaction placeholders, severity/rule misclassification, scratch artifacts, duplicate CHANGELOG/doctoring, and self-modifying/task-specific guidance. Preserve valid ancestry, ordinary-forward to the canonical owner tree/contract, convert duplicate/rejected lanes to Draft provenance, and never transfer predecessor hosted receipts.

Canonical-owner movement invalidates an earlier zero-delta or stacked relation. Descendants must be freshly compared and ordinary-restacked when necessary. Queue reduction alone never proves valid succession: a closed PR with unresolved unique delta must be reopened or repaired through a verified successor rather than treated as completed.

Issue #1178 and PR #1732 remain the OpenSSF governance/legal lane. Current proprietary licensing is an eligibility blocker for OpenSSF Passing, not a technical waiver; do not weaken licensing or branch protection for badge attainment.

## 6. Commercial Gap register

| Priority | Gap | Current boundary | Completion evidence |
| --- | --- | --- | --- |
| P0 | Release-train convergence | 286 open PRs; protected head unchanged; owner movement requires descendant resweep | parent-first integration, no orphaned valid delta, one immutable RC source SHA |
| P0 | Actions execution capacity | `.github#712`; 220 queued / 2 in progress in two consecutive fresh sweeps | stable runner acquisition; generation/admission/first-runner/downstream-runner/cancellation classes separated; obsolete pressure removed without cancelling sole current-head evidence |
| P0 | Central CI/security acceptance | #1911 current families cancelled; #2040 Trusted-uv convergence complete; #2291→#2109 owns stacked-base/Draft admission; #2271→#2275 currently lacks Python Security generation; #2291→#2272; #2276 canary pending | protected admission contract, exact-head hosted GREEN without wake commits, qualifying review, #2269 succession, unchanged-target GHAS canary |
| P0 | Dependency-security freshness | frontend #1623 owns current Trivy/dependency revalidation including #1733 inherited Security RED; backend #1565→#1685 real ancestry/coherent graph repair | current vulnerability scans, coherent manifests/locks, hostile regressions, terminal CI/security/review |
| P0 | LLM provider error confidentiality | #1733 exact `2b47bc7...`; source/test/TRACEABILITY repair restored after second generated rollback; fresh hosted generation nonterminal | terminal current-head hosted evidence + zero valid findings + qualifying review after canonical dependency revalidation |
| P0 | Workspace/migration convergence | #1503 sole migration line; #1727 sole opaque-ID descendant; #1736 provenance | one Alembic head, real PostgreSQL fresh/historical execution, ordinary descendant restacks |
| P0 | Released LLM contract | contextual-orchestrator release inventory empty | immutable API/client/schema publication + consumer bump + contract/E2E/security/SBOM/provenance |
| P1 | Tasks loading interaction | #1463 source-level RED→GREEN; #1735 zero-delta provenance | exact-head hosted GREEN, browser keyboard/focus/touch/responsive/AT evidence, qualifying review |
| P1 | Settings native-disabled semantics | #1676 canonical; live head source-neutral over causal tree; #1737 zero-delta provenance | exact-live-head hosted + browser/keyboard/responsive evidence + qualifying review |
| P1 | Design-QA fidelity/mobile states | #1738 generated placeholder implementation quarantined; #1193 closure did not prove succession | authoritative EmailDetail/mobile owner implementation, no fabricated data/dead CTA, mounted lifecycle states, browser/E2E/a11y evidence |
| P1 | Executable Storybook/design system | #1354 static owner on #1623; #1436 dirty existing runtime lineage | owner-safe #1436 reconstruction, coherent resolver-produced lock, representative states, browser/a11y/responsive evidence, token/Figma audit |
| P1 | UI localization | #1731 specified; implementation not protected | eight-locale versioned resource + Storybook/browser/a11y + cache/API/rollback evidence |
| P1 | OIDC interaction acceptance | #1729 rendered contract incomplete | real browser/AT/responsive/eight-locale current-head acceptance |
| P1 | Generated/descendant owner lock | #1728/#1734/#1735/#1736/#1737/#1738 + central parent movement | semantic owner-overlap/fidelity gate, owner-movement descendant sweep, canonical-tree/delta check, no scratch/self-modifying residue |

## 7. Current causal order

1. Restore stable Actions runner acquisition through `.github#712`; a smaller backlog does not make current-head cancellation or missing workflow generation acceptable evidence.
2. Reacquire legitimate exact-head hosted evidence for canonical `.github#1911@c965664a...`; then terminalize already-converged `.github#2040@bd039185...` on its distinct CodeQL/runtime-quality scope without reopening Trusted-uv ownership.
3. Terminalize canonical Strix parent `.github#2291`, then land/accept `.github#2109@42e3f7a...`'s stacked-base and Draft/Ready admission contract. `.github#2272` remains a separate #2291 descendant for Pages shell-input security.
4. Terminalize #2271 parent, then reacquire #2275 on the accepted central admission contract so Python Security/Runtime Quality are actually generated on #2275's own exact head; prove #2269 succession and #2276 unchanged-target GHAS canary.
5. Revalidate frontend dependency-security #1623 against current vulnerability data, including the inherited #1733 predecessor Trivy RED; do not manufacture a feature-local dependency fix.
6. Preserve #1565 as bounded TestClient/httpx2 owner; ordinary/non-force reconcile #1685 and regenerate one coherent dependency graph before hosted acceptance.
7. Terminalize #1733 exact `2b47bc7...` after #1623 revalidation/adoption as required, without reintroducing provider text, traceback logging or generated TRACEABILITY rollback; current exact-head six-workflow generation and independent review are still outstanding.
8. Integrate #1694 → #1691 and prerequisites, then #1503 as the sole migration lineage; ordinary-adopt #1727 and downstream consumers. Keep #1736 provenance only.
9. After contextual-orchestrator publishes an immutable API/client/schema release, finish #1549 without mutable-owner binding.
10. Implement #1731 as sole localization owner, then ordinary-adopt released screen resources into #1729 and other UI surfaces.
11. Terminalize #1463 exact `bf9ce8e...` with hosted gates, real browser keyboard/focus/touch/responsive/AT evidence and qualifying independent review; keep #1735 aligned if the owner moves.
12. Terminalize #1676 live exact `8a3ac516...` on its unchanged causal tree and keep #1737 zero-delta provenance aligned.
13. Repair the valid #1738 design-QA intent through authoritative EmailDetail and #1570/mobile owner paths; do not restore #1193 or any fabricated/static placeholder implementation.
14. Terminalize static design-token chain #1623 → #1354, then reconstruct existing #1436 as executable Storybook lane without stale dependency, CI, baseline, confidence or product-domain ownership. Acquire current Figma/Storybook/browser/a11y evidence.
15. Reacquire buyer-visible acceptance, build one exact integrated protected candidate, then publish an immutable Naruon version/tag/package/GitHub Release with SBOM/provenance/reproducibility/rollback.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL.** Source repairs and local evidence do not substitute for terminal exact-head hosted checks, qualifying independent review, current security scans, real external permission evidence, released owner contracts, buyer-visible UI acceptance, or immutable publication.