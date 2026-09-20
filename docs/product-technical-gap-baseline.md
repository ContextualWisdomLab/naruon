# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.27  
**Observed on:** 2026-09-20 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

This file is the current product/technical authority overlay. v2.26 remains audit-visible as blob `5d453f080d2d8b496cf14d1be2c4de5f6205358f`; v2.25 remains blob `2bc5c59b0f6e1b2ad6fb0ef2a44842a464ad8c2c`; earlier snapshots remain audit material in Git ancestry and `docs/product-technical-gap-history/`. Historical evidence is not current merge or release authority.

## 1. Evidence and release posture

Authority order is protected code/runtime/migrations/tests → protected architecture/operations docs → exact current PR source and current-head evidence → open Issues/Proposed ADRs → historical snapshots. Pending, queued, cancelled, stale, predecessor-head, skipped-required, neutral, local-only, author-only, model-only, or source-neutral wake evidence is not passing evidence.

Fresh repository inventory is **288 open PRs and 75 open Issues**. The increase from 287 is the new bounded UI Localization Catalog implementation owner #1740; it does not create a second product Gap. Protected `develop` remains exact `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required contexts. Latest published Naruon release remains `v0.14.4`, `immutable=false`; it is historical publication evidence, not a commercial immutable release candidate.

A releasable candidate requires one exact integrated protected head, terminal required contexts, zero valid unresolved review findings, qualifying independent post-last-push review, current security evidence, immutable publication identity, SBOM/provenance, reproducibility, rollback evidence, and buyer-visible acceptance for changed behavior.

## 2. Central CI/security owner graph

Protected central authority remains `.github/main@e6334e229581a918e2f22de18733b76fa65d7e71`, the protected merge of #2279 exact `d1e4380c15e948aaf104d46aa134fa614058782a`. GitHub REST authority validation, redirect refusal, bearer non-forwarding, evidence-lineage validation, and owner-qualified foreign Semgrep evidence are protected ancestry; #2279 is not an open prerequisite.

- `.github#712` remains the Actions execution-capacity owner. Fresh observation is **189 queued / 2 in progress**. The newest queued sample is a `repository_dispatch` CodeQL scan on protected central `main`; long-running Strix work remains in progress. This is not stable runner acquisition. Preserve sole current-head evidence and distinguish workflow generation/admission, first runner acquisition, downstream runner acquisition, and terminal cancellation/preemption; do not create source-neutral wake commits or blind unchanged-head reruns.
- `.github#1911@c965664a6d7fe0b75bf7ea019a9059220a32f06b` remains the canonical repository-wide/full-suite Trusted-uv owner on current protected main. Its current Python Security, SAST, Security, Trusted-uv and CodeQL generations are terminal **CANCELLED**. Cancellation is missing hosted acceptance, not source GREEN.
- `.github#2040@bd039185ddf8df88480971cdd3b69c38f4558609` has ordinary-adopted #1911 and no longer retains a parallel Trusted-uv delta. Its remaining CodeQL scheduler/credential/runtime-quality scope is still unaccepted.
- `.github#2291@a8d6261d4fc2c2a82a9b8ad6636e75677ecc5081` is the canonical Strix trusted-runtime/evidence-binder owner and remains **source RED before queue acceptance is considered**. The accepted P1 is unchanged: 26 `materialize_trusted_gate_fixture` occurrences consist of one helper definition, one already-correct trusted-runtime call, and **24 concrete specialized consumer-root materializations** that can mask a regression back to consumer-controlled binder resolution. Exact `a8d6261d...` now adds an executable test-only RED (`tests/test_strix_trusted_fixture_boundary.py`) that enumerates those owner-violating call sites; it does **not** claim repair. Acceptance requires every affected production-boundary fixture to move gate/model/binder into a sibling/non-consumer trusted runtime, invoke the trusted gate by absolute path with explicit `STRIX_REPO_ROOT="$repo_root_dir"`, keep the consumer root binder-free except explicit source-under-scan cases, preserve scenario environments/assertions, and retain negative consumer-binder proof. Existing predecessor receipts cannot override this current RED.
- `.github#2109@42e3f7a8cbb03b117c898d3e125af87a5c6ce86b` owns Draft/Ready plus stacked-base admission and depends on #2291. Same-tree evidence proves Ready admission and Draft conversion cancellation/skipping, but it is not hosted GREEN or protected acceptance. It must ordinary-adopt repaired #2291 rather than copy its runtime/binder fix.
- `.github#2271@8da5f48fa0438ff33c766f03325f6e7f2a77dd9d` ordinary-adopts canonical AnyIO 4.14.2 and retains repository-identity admission; current hosted acceptance is incomplete.
- `.github#2275@0d68d7a8435652edc288d7bb3dfb06a7c8a59eb6` remains ordinary-restacked on #2271 with only the bounded GHAS credential-routing delta. Its stacked base lacks Python Security under the protected base-name filter; #2109 owns that admission defect. After #2109 is accepted/protected, #2275 itself must reacquire Python Security/Runtime Quality on its own exact head. #2276 retains the unchanged-target GHAS permission canary.
- `.github#2272@f5b96a4cb8add16208a3c8dbacd99d94b65b4bcb` remains the Pages/SAST descendant on #2291 and must ordinary-adopt the completed parent repair; it must not become a second Strix owner.
- `.github#2269` remains historical redirect/test-seam lineage until lossless succession is proven; `.github#2276` remains the real target-repository permission/canary boundary.

Naruon does not copy central workflow source. It records canonical owner identities and consumes accepted/released contracts through ordinary-forward changes only.

## 3. Product owner boundaries

### Dependency and security ownership

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the sole frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`. Current vulnerability-database evidence must be reacquired before inherited Trivy findings are treated as resolved. Consumer evidence from #1733 predecessor exact `9d9d5e0...` includes Security Scan `35450922558` failing in `trivy-fs` job `105968932721`; #1733 changes no dependency manifest/lockfile, so repair/revalidation remains with #1623 rather than broadening the feature owner.

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the bounded Starlette TestClient/httpx2 owner at exact `52dfc863d1a5d6e4e80b6366f719dd09f2aa6172`. [#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) must ordinary/non-force reconcile onto #1565 while preserving its distinct SMTP dependency delta and regenerate one coherent resolver-produced `pyproject.toml` / requirements / hashed requirements / `uv.lock` graph before hosted acceptance. Never hand-edit generated lock/hash material.

[#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) remains the bounded LLM-provider error-confidentiality owner at exact `2b47bc7b57732d0dbe00db1ba498b49cdb512e8b`, Draft/open/mergeable. Production/test/TRACEABILITY repairs suppress provider-controlled exception text/traceback across the four owned paths. Its predecessor inherited Trivy RED is routed to #1623; current exact-head workflow generation is nonterminal and no predecessor receipt or approval transfers.

### Data-hygiene and checksum utility ownership

[#1247](https://github.com/ContextualWisdomLab/naruon/issues/1247) remains the product contract for the auditable data-hygiene suite. The normal checksum surface is SHA-256, SHA-3-256 and BLAKE2b-256 only. MD5/SHA-1 are excluded from the normal security-labelled surface; any buyer-backed legacy mode must be separately named, disabled by default, explicitly acknowledged as non-security use, and machine-deprecated.

[#1361](https://github.com/ContextualWisdomLab/naruon/pull/1361) is the sole bounded `content_checksum_generator` implementation owner at exact `6bf2989d571a2aa94ce1f92997650cc450e88e9d`, stacked on #1623. It preserves exact UTF-8 bytes, enforces the one-MiB byte ceiling, stable invalid-UTF-8/algorithm errors and authenticity warning, and pins known-answer/chunk-equivalence evidence. Exact-head PR workflow generation remains an admission prerequisite. Generated #1739 exact `79ced706b20f65c934d187df32ddcb7d15cbe18e` ordinary-adopts #1361 with zero effective product delta and remains provenance only.

### Workspace, migrations and opaque identifiers

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the sole canonical Alembic/bootstrap owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`; descendants must not create parallel migration heads from protected `develop`. [#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains the sole opaque-UID backfill owner on #1503; generated #1736 remains zero-effective-delta provenance.

### LLM governance / released contract

[#1548](https://github.com/ContextualWisdomLab/naruon/issues/1548) / [#1549](https://github.com/ContextualWisdomLab/naruon/pull/1549) remain the sole Naruon LLM-governance owner. Protected `AGENTS.md` still contains provider/model-specific GitHub Models fallback guidance that conflicts with the canonical `contextual-orchestrator` boundary, but this is already owned by #1548/#1549 and must not spawn a second governance writer. `contextual-orchestrator` protected `main@5665b0ad1e07ffb5e9f8c59e44b6b2a785298013` remains mutable source and its GitHub Releases inventory is empty; Naruon therefore remains fail-closed and must not bind a mutable owner head as released API/client/schema authority.

## 4. Buyer-visible UI, Storybook and localization

[#1682](https://github.com/ContextualWisdomLab/naruon/pull/1682) remains the Calendar buyer-truth/detail-sidebar owner. Inherited dependency/central evidence remains incomplete; UI Delivery stays FAIL until exact-head security/CodeQL, browser/a11y and qualifying review evidence are terminal.

[#1354](https://github.com/ContextualWisdomLab/naruon/pull/1354) remains the static design-token precursor on #1623. Open [#1436](https://github.com/ContextualWisdomLab/naruon/pull/1436) is the existing executable Storybook/runtime lineage and must be repaired rather than replaced. Package/lock security belongs to #1623; token taxonomy belongs to #1354; baseline ownership stays here; unintegrated Storybook ADRs remain Proposed. Required reconstruction is #1623 → #1354 → repaired #1436 with resolver-backed package/lock state, deterministic static build, representative normal/loading/empty/error/permission/destructive/busy states, keyboard/focus/touch/responsive/200%-zoom evidence, WCAG-oriented browser automation, manual accessible-name/AT evidence and current Figma mapping.

[#1463](https://github.com/ContextualWisdomLab/naruon/pull/1463) remains the Tasks async-loading owner; source-level pending-action repair exists, but current hosted/browser/AT/independent-review evidence is incomplete. Generated #1735 remains zero-delta provenance.

[#1676](https://github.com/ContextualWisdomLab/naruon/pull/1676) remains the Settings native-disabled semantics owner; generated #1737 is zero-delta provenance. Current hosted/browser/keyboard/responsive evidence and qualifying review remain outstanding.

Generated #1738 remains quarantined zero-delta provenance after its predecessor fabricated participant counts and attachment names, exposed an unbound CTA, and added static unmounted mobile panels. Its valid intent must be rebuilt through authoritative EmailDetail/mail/thread/attachment/calendar owners and #1570 or a verified mobile-state successor with real data plus normal/loading/empty/error/permission, touch/keyboard/focus/AT/responsive, exact-head browser/E2E/screenshot evidence. Historical #1193 closure does not prove delivery.

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single DB-versioned, screen-scoped UI Localization Catalog Gap. Draft [#1740](https://github.com/ContextualWisdomLab/naruon/pull/1740) is now its first bounded executable implementation owner at exact `6e80999b261610880089a852bc36f6f6ed5fb4da`. #1740 owns **pure domain policy only**: KO/EN/JA/ZH/VI/ES/DE/FR release identities, persisted → session → weighted `Accept-Language` → product-default selection, stable screen/message keys, and exact named-placeholder schemas. It intentionally owns no database/Alembic/API/browser/Storybook/authoring/ontology/LLM path. A local standards review produced a real RED at `859b892e...` for wildcard lookup semantics; exact `6e80999b...` repairs that contract and has focused 16-test / 100% statement+branch local evidence. Its current Application CI, SAST, Security, CodeQL, Docker and Bandit generations are queued and it has no independent review, so it remains Draft. Persistence still waits for #1503 or a verified complete successor to reach protected ancestry, then creates the next ordinary single-head Alembic descendant. [#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) remains the bounded OIDC interaction-state owner and consumes released screen resources only after localization persistence/API reach protected ancestry.

## 5. Generated-writer and descendant invariants

Generated branches are provenance, not new owners, when an existing canonical owner already covers the delta. Current examples include #1728 cross-owner rollback, repaired #1734 NetworkGraph provenance, #1735 Tasks duplicate, #1736 opaque-ID duplicate, #1737 Settings duplicate, #1738 rejected placeholder UI, and #1739 checksum/hash duplicate.

Every generated descendant/new duplicate must be checked semantically for owner overlap, source/test/fixture deletion, dependency/security/performance regression, fabricated buyer-visible data, dead CTA, weak/deprecated security surface, unmounted/static interactions, severity/rule misclassification, scratch artifacts, duplicate CHANGELOG/doctoring, and self-modifying/task-specific guidance. Preserve valid ancestry, ordinary-forward to the canonical owner tree/contract, keep duplicate/rejected lanes Draft, and never transfer predecessor hosted receipts.

Canonical-owner movement invalidates an earlier zero-delta or stacked relation. Descendants must be freshly compared and ordinary-restacked when needed. Queue reduction alone never proves succession.

Issue #1178 and PR #1732 remain the OpenSSF governance/legal lane. Current proprietary licensing is an eligibility blocker for OpenSSF Passing, not a technical waiver.

## 6. Commercial Gap register

| Priority | Gap | Current boundary | Completion evidence |
| --- | --- | --- | --- |
| P0 | Release-train convergence | 288 open PRs; protected head unchanged | parent-first integration, no orphaned valid delta, one immutable RC source SHA |
| P0 | Actions execution capacity | `.github#712`; fresh 189 queued / 2 in progress | stable runner acquisition; admission/runner/cancellation classes separated; obsolete pressure removed without cancelling sole current-head evidence |
| P0 | Strix trusted-runtime isolation | #2291 exact `a8d6261d...` carries executable RED for 24 specialized masking call sites; #2109/#2272 depend on it | all 24 production-boundary fixtures moved to non-consumer trusted runtime, consumer binder-free negative proof, exact-head GREEN/review/hosted acceptance |
| P0 | Central CI/security acceptance | #1911 cancelled; #2040 unique scope incomplete; #2271→#2275 stacked admission incomplete; #2276 canary pending | exact-head hosted GREEN without wake commits, qualifying review, accepted stacked-base contract, unchanged-target GHAS proof |
| P0 | Dependency-security freshness | #1623 owns current Trivy/dependency revalidation including #1733 inherited RED; #1565→#1685 backend graph repair | current vulnerability scans, coherent manifests/locks, hostile regressions, terminal CI/security/review |
| P0 | LLM provider error confidentiality | #1733 exact `2b47bc7...` source/test/TRACEABILITY repaired; current evidence nonterminal | terminal current-head evidence, zero valid findings, qualifying review after dependency revalidation |
| P0 | Workspace/migration convergence | #1503 sole migration line; #1727 descendant; #1736 provenance | one Alembic head, real PostgreSQL fresh/historical execution, ordinary descendant restacks |
| P0 | Released LLM contract | contextual-orchestrator release inventory empty | immutable API/client/schema publication + consumer bump + contract/E2E/security/SBOM/provenance |
| P1 | Data-hygiene checksum contract | #1361 sole implementation; #1739 provenance | #1623 prerequisite integration, stacked admission, exact-head hosted/security/review acceptance, bounded UTF-8/known-vector contract |
| P1 | UI localization catalog | #1731 Gap; #1740 pure-policy owner; persistence waits for #1503 | versioned 3NF resource + immutable publication/rollback + screen-scoped API/cache + eight-locale completeness/placeholder enforcement |
| P1 | Tasks/Settings interaction acceptance | #1463 and #1676 source repairs exist; #1735/#1737 provenance | hosted GREEN + browser keyboard/focus/touch/responsive/AT + qualifying review |
| P1 | Design-QA fidelity/mobile states | #1738 placeholder implementation quarantined | authoritative data/action implementation, lifecycle states, browser/E2E/a11y evidence |
| P1 | Executable Storybook/design system | #1354 static owner; #1436 existing runtime lineage | owner-safe reconstruction, coherent lock, representative states, browser/a11y/Figma evidence |
| P1 | Generated/descendant owner lock | current zero-delta/rejected provenance set | semantic overlap/fidelity gate, owner-movement resweep, no scratch/self-modifying residue |

## 7. Current causal order

1. Restore stable Actions runner acquisition through `.github#712`; backlog reduction alone does not make cancellation, missing generation, or runner-unassigned work passing evidence.
2. Reacquire legitimate exact-head hosted evidence for `.github#1911`; then terminalize already-converged `.github#2040` only on its distinct CodeQL/runtime-quality scope.
3. Repair `.github#2291` **source-first** from current executable RED `a8d6261d...`: remove all 24 consumer-root binder/runtime materializations, prove consumer-root binder absence, then obtain exact-head GREEN, fresh independent review and hosted acceptance. Only after that may #2109 and #2272 ordinary-adopt the repaired parent and reacquire their own evidence.
4. Terminalize #2271; then reacquire #2275 under the accepted stacked-base admission contract so Python Security/Runtime Quality are generated on #2275 itself. Prove #2269 succession and #2276 unchanged-target GHAS permission.
5. Revalidate #1623 against current vulnerability data, including #1733 inherited Trivy evidence, and integrate normally.
6. Preserve #1361 as sole checksum owner; after #1623 + stacked admission integrate, obtain #1361 exact-head hosted/security/review acceptance. Keep #1739 zero-delta provenance.
7. Preserve #1565 as bounded TestClient/httpx2 owner; ordinary/non-force reconcile #1685 and regenerate one coherent dependency graph before hosted acceptance.
8. Terminalize #1733 after #1623 revalidation/adoption without reintroducing provider text, traceback logging, or generated TRACEABILITY rollback.
9. Integrate #1694 → #1691 and prerequisites, then #1503 as the sole migration lineage; ordinary-adopt #1727 and downstream consumers. Keep #1736 provenance only.
10. Preserve #1740 as the bounded #1731 pure-policy owner while Draft/current-head checks/review are incomplete. Once #1503 reaches protected ancestry, extend this lineage with the next single-head catalog migration, immutable resource-version aggregate and screen-scoped API/cache; do not create a second localization writer.
11. After contextual-orchestrator publishes an immutable API/client/schema release, finish #1549 without mutable-owner binding.
12. Ordinary-adopt released localization resources into #1729 and other UI surfaces and prove KO/EN/JA/ZH/VI/ES/DE/FR normal/loading/empty/error/permission, CJK/text expansion/font fallback, keyboard/focus/touch/a11y/responsive behavior.
13. Terminalize #1463 and #1676 with exact-head hosted plus real browser/accessibility evidence; keep #1735/#1737 aligned if their owners move.
14. Repair #1738's surviving EmailDetail/mobile intent through authoritative product owners; do not restore fabricated/static placeholder implementations.
15. Terminalize #1623 → #1354 and reconstruct #1436 as the executable Storybook lane with current Figma/browser/a11y evidence.
16. Reacquire buyer-visible acceptance, build one exact integrated protected candidate, then publish an immutable Naruon version/tag/package/GitHub Release with SBOM/provenance/reproducibility/rollback.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL.** Source repairs and local evidence do not substitute for terminal exact-head hosted checks, qualifying independent review, current security scans, real external permission evidence, released owner contracts, buyer-visible UI acceptance, or immutable publication.