# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.28  
**Observed on:** 2026-09-20 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

This file is the current product/technical authority overlay. v2.27 remains audit-visible as blob `bf7e6e36d58899704ac3331cace1be59387b62e4`; v2.26 remains blob `5d453f080d2d8b496cf14d1be2c4de5f6205358f`; earlier snapshots remain audit material in Git ancestry and `docs/product-technical-gap-history/`. Historical evidence is not current merge or release authority.

## 1. Evidence and release posture

Authority order is protected code/runtime/migrations/tests → protected architecture/operations docs → exact current PR source and current-head evidence → open Issues/Proposed ADRs → historical snapshots. Pending, queued, cancelled, stale, predecessor-head, skipped-required, neutral, local-only, author-only, model-only, or source-neutral wake evidence is not passing evidence.

Fresh repository inventory is **289 open PRs and 75 open Issues**. Protected `develop` remains exact `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required contexts and three active rulesets. Latest published Naruon release remains `v0.14.4`, `immutable=false`; it is historical publication evidence, not a commercial immutable release candidate.

A releasable candidate requires one exact integrated protected head, terminal required contexts, zero valid unresolved review findings, qualifying independent post-last-push review, current security evidence, immutable publication identity, SBOM/provenance, reproducibility, rollback evidence, and buyer-visible acceptance for changed behavior.

## 2. Central CI/security owner graph

Protected central authority remains `.github/main@e6334e229581a918e2f22de18733b76fa65d7e71`, the protected merge of #2279 exact `d1e4380c15e948aaf104d46aa134fa614058782a`.

- `.github#712` remains the Actions execution-capacity owner. Fresh observation is **211 queued / 1 in progress**. The newest queued sample is a `repository_dispatch` CodeQL dispatch on protected central `main`; the single in-progress workload remains the long-running #2274 Strix run. This is not stable runner acquisition. Preserve sole current-head evidence and distinguish generation/admission, first runner acquisition, downstream acquisition, cancellation and preemption. No source-neutral wake commits or blind unchanged-head reruns.
- `.github#1911@c965664a6d7fe0b75bf7ea019a9059220a32f06b` remains the repository-wide/full-suite Trusted-uv owner. Its current hosted acceptance is not GREEN.
- `.github#2040@bd039185ddf8df88480971cdd3b69c38f4558609` has converged off parallel Trusted-uv ownership; its distinct CodeQL/scheduler/runtime-quality scope remains unaccepted.
- `.github#2291@a8d6261d4fc2c2a82a9b8ad6636e75677ecc5081` remains **source RED before queue acceptance**. Its executable RED enumerates the remaining 24 specialized `materialize_trusted_gate_fixture` call sites that still co-locate trusted runtime/binder material with the consumer root and can mask a regression to consumer-controlled binder resolution. Acceptance requires all affected production-boundary fixtures to move gate/model/binder to a non-consumer trusted runtime, invoke the trusted gate by absolute path with explicit `STRIX_REPO_ROOT`, preserve scenario assertions, and prove consumer-binder absence.
- `.github#2109@42e3f7a8cbb03b117c898d3e125af87a5c6ce86b` owns Draft/Ready plus stacked-base admission and depends on repaired #2291. Same-tree Ready/Draft lifecycle canary evidence is useful but is not protected acceptance.
- `.github#2271@8da5f48fa0438ff33c766f03325f6e7f2a77dd9d` retains repository-identity admission over canonical AnyIO ancestry; hosted acceptance remains incomplete.
- `.github#2275@0d68d7a8435652edc288d7bb3dfb06a7c8a59eb6` remains the bounded GHAS credential-routing child. After #2109 is accepted/protected it must reacquire Python Security/Runtime Quality on its own exact head. `.github#2276` retains the unchanged-target permission/canary boundary.
- `.github#2272` remains the Pages/SAST descendant on #2291 and must ordinary-adopt the repaired parent rather than become a second Strix owner.

Naruon does not copy central workflow source. It consumes accepted/released owner contracts through ordinary-forward changes only.

## 3. Product owner boundaries

### Dependency and security ownership

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the sole frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`. Current vulnerability-database evidence must be reacquired before inherited Trivy findings are treated as resolved. #1733 predecessor Security Scan `35450922558` failed in `trivy-fs` job `105968932721`; #1733 changes no dependency manifest/lockfile, so repair/revalidation remains with #1623.

A new cross-owner regression was found in #1593 history: intervening `30d52cef0c708c4625825bad6fb823b3d2766986` changed `frontend/package.json` and `frontend/pnpm-lock.yaml`, introduced Next/Sharp resolution changes, and deleted PostCSS security-floor/root-snapshot regression coverage. None of that delta is accepted in #1593. Exact #1593 repair `cd6f6d545fe860215d9f6f04b549520f31f68b0e` restores the prior canonical tree; dependency/security ownership remains solely with #1623.

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the bounded Starlette TestClient/httpx2 owner. [#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) must ordinary/non-force reconcile onto it while preserving its distinct SMTP dependency delta and regenerate one coherent resolver-produced dependency graph before hosted acceptance.

[#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) remains the bounded LLM-provider error-confidentiality owner at exact `2b47bc7b57732d0dbe00db1ba498b49cdb512e8b`, Draft/open. Its inherited Trivy RED is routed to #1623; predecessor receipts do not transfer.

### NetworkGraph performance ownership

[#1593](https://github.com/ContextualWisdomLab/naruon/pull/1593) is the canonical bounded relationship/node option owner. Fresh live inspection found its documented clean `97235208...` had been followed by cross-owner regression `30d52cef...` and a no-op child `e7b0711...`. Besides dependency/security drift, that regression weakened per-iterator read-count coverage into aggregate counters and moved the `try/finally` boundary after mutation of process-global `Map.prototype.values`, reintroducing the exact test-isolation leak risk previously repaired.

Exact current #1593 is **`cd6f6d545fe860215d9f6f04b549520f31f68b0e`**, tree `ad5da38f3f6391dd4a36d8f0a2a8f6e3a251acc0`. The repair is ordinary-forward from the intervening history, not a force rewrite, and restores the canonical two-file effective delta against #1623. Old formal approval on `97235208...` is historical only; current-head hosted and independent-review evidence must be reacquired.

[#1628](https://github.com/ContextualWisdomLab/naruon/pull/1628) is the canonical first-five non-empty label-summary child at **`8786c6e9923a90b7d43ad5439c096ef0f0556148`**, tree `387e2def9f44d7bb7226d8106d4f548f7a142bfa`. It ordinary-adopts repaired #1593 and preserves exactly three effective files. Worst-case sparse-label traversal remains O(N); only result storage is bounded.

[#1674](https://github.com/ContextualWisdomLab/naruon/pull/1674) is zero-effective-delta provenance at **`48121f5adbe4a15410ec83e6f6dc44ef0a2f7f7a`** on current #1628. [#1675](https://github.com/ContextualWisdomLab/naruon/pull/1675) is the canonical memo-only child at **`059481ed9fafb34925d33df2106dcc15cc76268e`**, tree `db81645977cbddd363e592633d11377b46ec6207`, preserving the two-file `React.memo` + `React.Profiler` contract. Its old formal approval on `8addfa1c...` is stale after restack; current-head hosted/review/browser-performance evidence is required.

Generated/provenance NetworkGraph descendants have been ordinary-restacked after owner movement: #1741 `388cbddaaa1b049e5baeb457f30fb4835c5eacbd`, #1720 `e65768e869f7737538c7243f8dc7e13b775bce78`, #1728 `f1105c3fe836e8b526628794229758e7dc70d212`, #1721 `ab1297b35f7d47600f94dc301f2d6817b784a640`, #1715 `c0cac5700c22632f00431dd41b08ff500e648d87`, #1703 `c6ded3c1bc851b6358ddce725bcc4ce05a2e81ca`, #1692 `58f488efe87376339f9689211b8c9c617de68d43`, and #1683 `a472cd9073f16a575ccea56223181275cd88393e`. These lanes remain Draft provenance, not source owners; historical generated receipts do not transfer.

### Data-hygiene and checksum utility ownership

[#1247](https://github.com/ContextualWisdomLab/naruon/issues/1247) remains the auditable data-hygiene contract. Normal checksum surface is SHA-256, SHA-3-256 and BLAKE2b-256 only. MD5/SHA-1 are excluded from the normal security-labelled surface.

[#1361](https://github.com/ContextualWisdomLab/naruon/pull/1361) remains the sole bounded `content_checksum_generator` implementation owner at exact `6bf2989d571a2aa94ce1f92997650cc450e88e9d`, stacked on #1623. Generated #1739 remains zero-effective-delta provenance.

### Workspace, migrations and opaque identifiers

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the sole canonical Alembic/bootstrap owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`; descendants must not create parallel migration heads from protected `develop`. [#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains the opaque-UID backfill owner on #1503; #1736 remains provenance.

### LLM governance / released contract

[#1548](https://github.com/ContextualWisdomLab/naruon/issues/1548) / [#1549](https://github.com/ContextualWisdomLab/naruon/pull/1549) remain the sole Naruon LLM-governance owner. `contextual-orchestrator` protected `main@5665b0ad1e07ffb5e9f8c59e44b6b2a785298013` remains mutable source and its GitHub Releases inventory is exactly empty. Naruon therefore remains fail-closed and must not bind a mutable owner head as released API/client/schema authority.

## 4. Buyer-visible UI, Storybook and localization

[#1682](https://github.com/ContextualWisdomLab/naruon/pull/1682) remains the Calendar buyer-truth/detail-sidebar owner. UI Delivery stays FAIL until exact-head security/CodeQL, browser/a11y and qualifying review evidence are terminal.

[#1354](https://github.com/ContextualWisdomLab/naruon/pull/1354) remains the static design-token precursor on #1623. [#1436](https://github.com/ContextualWisdomLab/naruon/pull/1436) remains the executable Storybook/runtime lineage and must be repaired rather than replaced. Package/lock security belongs to #1623; token taxonomy belongs to #1354.

[#1463](https://github.com/ContextualWisdomLab/naruon/pull/1463) remains the Tasks async-loading owner; #1735 remains provenance. [#1676](https://github.com/ContextualWisdomLab/naruon/pull/1676) remains the Settings native-disabled semantics owner; #1737 remains provenance. Hosted/browser/keyboard/responsive/AT evidence remains outstanding.

Generated #1738 remains quarantined zero-delta provenance after fabricated participant/attachment data and static/unbound UI behavior. Its valid intent must be rebuilt through authoritative mail/thread/attachment/calendar/mobile owners with real data and full lifecycle/browser/a11y evidence.

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single DB-versioned, screen-scoped **UI Localization Catalog** Gap. Draft [#1740](https://github.com/ContextualWisdomLab/naruon/pull/1740) is the first bounded executable owner at exact **`f07de3fce6b61afd8fe9dc5b72352a9b184ab854`** and currently owns pure domain policy only: KO/EN/JA/ZH/VI/ES/DE/FR release identities, persisted → session → weighted `Accept-Language` → product-default selection, stable screen/message keys, exact named-placeholder schemas, and typed validation boundaries.

#1740 now preserves two ordinary-forward RED→repair sequences. First, RFC 4647 lookup review repaired wildcard ordering and explicit `q=0` exclusion. Second, a fresh RED proved that CR/LF/NUL arriving via `Accept-Language` was incorrectly reported as `ui_locale_input_invalid` because a shared control-character helper hard-coded the explicit-locale code. The causal repair parameterizes that helper by caller boundary: explicit locale controls → `ui_locale_input_invalid`; `Accept-Language` controls → `ui_accept_language_invalid`. Temporary duplicate regression coverage was folded into the canonical policy suite and removed.

The current #1740 head has no independent review. Application CI, CodeQL, Security Scan, SAST Semgrep, Bandit and Docker generations are queued. Earlier local 16-test/100%-coverage and `PYTHONPATH=.` receipts are predecessor history and **do not** count for the current head. Doctoring/TRACEABILITY now records RFC 5646, RFC 4647 and RFC 9110 plus the typed boundary decision without transferring stale receipts.

#1740 intentionally owns no database/Alembic/API/browser/Storybook/authoring/ontology/LLM path. Persistence still waits for #1503 or a verified complete successor to reach protected ancestry, then creates the next ordinary single-head Alembic descendant. [#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) remains the bounded OIDC interaction-state owner and consumes released screen resources only after localization persistence/API reach protected ancestry.

## 5. Generated-writer and descendant invariants

Generated branches are provenance, not new owners, when an existing canonical owner already covers the delta. Current examples include repaired NetworkGraph lanes #1741/#1720/#1728/#1721/#1715/#1703/#1692/#1683, repaired #1734, #1735 Tasks duplicate, #1736 opaque-ID duplicate, #1737 Settings duplicate, #1738 rejected placeholder UI, and #1739 checksum/hash duplicate.

Every generated descendant/new duplicate must be checked semantically for owner overlap, source/test/fixture deletion, dependency/security/performance regression, fabricated buyer-visible data, dead CTA, weak/deprecated security surface, unmounted/static interactions, severity/rule misclassification, scratch artifacts, duplicate CHANGELOG/doctoring, and self-modifying/task-specific guidance. Preserve valid ancestry, ordinary-forward to the canonical owner tree/contract, keep duplicate/rejected lanes Draft, and never transfer predecessor hosted receipts.

Canonical-owner movement invalidates an earlier zero-delta or stacked relation. Descendants must be freshly compared and ordinary-restacked when needed. The #1593 incident is a concrete owner-level example: a seemingly on-topic test commit carried dependency/security rollback and test-isolation regression, and a following no-op did not make that tree acceptable.

Issue #1178 and PR #1732 remain the OpenSSF governance/legal lane. Current proprietary licensing is an eligibility blocker for OpenSSF Passing, not a technical waiver.

## 6. Commercial Gap register

| Priority | Gap | Current boundary | Completion evidence |
| --- | --- | --- | --- |
| P0 | Release-train convergence | 289 open PRs; protected head unchanged | parent-first integration, no orphaned valid delta, one immutable RC source SHA |
| P0 | Actions execution capacity | `.github#712`; fresh 211 queued / 1 in progress | stable runner acquisition; admission/runner/cancellation classes separated; obsolete pressure removed without cancelling sole current-head evidence |
| P0 | Strix trusted-runtime isolation | #2291 exact `a8d6261d...` executable RED for 24 specialized masking call sites | complete fixture migration, consumer-binder negative proof, exact-head GREEN/review/hosted acceptance |
| P0 | Central CI/security acceptance | #1911/#2040 incomplete; #2109 depends on #2291; #2271→#2275 admission incomplete | exact-head hosted GREEN, qualifying review, accepted stacked-base contract, #2276 canary |
| P0 | Dependency-security freshness | #1623 owns Trivy/dependency revalidation and rejected #1593 cross-owner rollback evidence | current vulnerability scans, coherent manifests/locks, hostile regressions, terminal CI/security/review |
| P0 | LLM provider error confidentiality | #1733 source repaired; inherited dependency RED routed to #1623 | terminal current-head evidence and qualifying review after dependency revalidation |
| P0 | Workspace/migration convergence | #1503 sole migration line; #1727 descendant | one Alembic head, real PostgreSQL fresh/historical execution, ordinary descendant restacks |
| P0 | Released LLM contract | contextual-orchestrator release inventory empty | immutable API/client/schema release + consumer bump + contract/E2E/security/SBOM/provenance |
| P1 | NetworkGraph performance stack | #1593 `cd6f6d...` → #1628 `8786c6e...` → #1674 provenance → #1675 `059481ed...`; descendants restacked | current-head hosted GREEN/review, real browser/main-thread profile, no unsupported O(1)/p95 claim |
| P1 | Data-hygiene checksum contract | #1361 sole implementation; #1739 provenance | #1623 integration, stacked admission, exact-head hosted/security/review acceptance |
| P1 | UI localization catalog | #1731 Gap; #1740 `f07de3fc...` pure-policy owner; persistence waits for #1503 | versioned 3NF resource, immutable publication/rollback, screen-scoped API/cache, eight-locale completeness/placeholder enforcement |
| P1 | Tasks/Settings interaction acceptance | #1463/#1676 source repairs; #1735/#1737 provenance | hosted GREEN + browser keyboard/focus/touch/responsive/AT + qualifying review |
| P1 | Design-QA fidelity/mobile states | #1738 quarantined placeholder | authoritative data/action implementation, lifecycle states, browser/E2E/a11y evidence |
| P1 | Executable Storybook/design system | #1354 static owner; #1436 runtime lineage | owner-safe reconstruction, coherent lock, representative states, browser/a11y/Figma evidence |
| P1 | Generated/descendant owner lock | repaired provenance set plus owner-movement resweep | semantic overlap/fidelity gate, ordinary restack after owner movement, no scratch/self-modifying residue |

## 7. Current causal order

1. Restore stable Actions runner acquisition through `.github#712`; queue reduction alone does not make missing/cancelled/nonterminal evidence passing.
2. Reacquire legitimate exact-head hosted evidence for `.github#1911`, then terminalize `.github#2040` only on its distinct scope.
3. Repair `.github#2291` source-first from executable RED `a8d6261d...`: remove all 24 consumer-root trusted-runtime materializations, prove consumer-root binder absence, then obtain exact-head GREEN, fresh independent review and hosted acceptance.
4. Only after #2291 acceptance may #2109/#2272 ordinary-adopt it; then terminalize #2271 and reacquire #2275 under accepted stacked-base admission, preserving #2276 canary evidence.
5. Revalidate #1623 against current vulnerability data, including #1733 inherited Trivy and rejected #1593 dependency/security rollback evidence, and integrate normally.
6. Preserve repaired #1593 as sole bounded-option owner; obtain current-head hosted/review/browser-performance evidence. Then terminalize #1628 on repaired #1593. Keep #1674/#1741/#1720 provenance aligned.
7. Terminalize #1675 only after current prerequisite ancestry settles and current-head hosted/review/real performance evidence exists; keep #1683/#1692/#1703/#1715/#1721/#1728 zero-delta provenance aligned.
8. Preserve #1361 as checksum owner after #1623 and stacked admission; keep #1739 provenance.
9. Preserve #1565 as bounded TestClient/httpx2 owner; ordinary/non-force reconcile #1685 and regenerate one coherent dependency graph.
10. Terminalize #1733 after #1623 revalidation/adoption without provider-text or traceback leakage.
11. Integrate migration prerequisites and #1694 → #1691 → #1503 as the sole migration lineage; ordinary-adopt #1727/downstream consumers.
12. Preserve #1740 as the bounded #1731 pure-policy owner while current-head checks/review are incomplete. After #1503 reaches protected ancestry, extend the same lineage with the next single-head catalog migration, immutable resource aggregate and screen-scoped API/cache.
13. After contextual-orchestrator publishes an immutable API/client/schema release, finish #1549 without mutable-owner binding.
14. Ordinary-adopt released localization resources into #1729 and UI surfaces; prove KO/EN/JA/ZH/VI/ES/DE/FR normal/loading/empty/error/permission, CJK/text expansion/font fallback, keyboard/focus/touch/a11y/responsive behavior.
15. Terminalize #1463/#1676, rebuild #1738 surviving intent through authoritative data owners, and reconstruct #1436 Storybook through #1623 → #1354 with current Figma/browser/a11y evidence.
16. Reacquire buyer-visible acceptance, build one exact integrated protected candidate, then publish an immutable Naruon version/tag/package/GitHub Release with SBOM/provenance/reproducibility/rollback.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL.** Source repairs and local evidence do not substitute for terminal exact-head hosted checks, qualifying independent review, current security scans, real external permission evidence, released owner contracts, buyer-visible UI acceptance, or immutable publication.
