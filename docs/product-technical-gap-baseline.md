# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.18  
**Observed on:** 2026-09-20 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

This file is the current product/technical authority overlay. v2.17 remains audit-visible as blob `d611e0d3cb1dd90e9d8429fcfa112a977e989726`; v2.16 remains blob `c09c9e2f02b9f173b6d14689730b382c03701216`; v2.15 remains blob `07699b4588e1b8198c1357b8ca2064703151628f`; earlier snapshots remain audit material in Git ancestry and `docs/product-technical-gap-history/`. Historical evidence is not current merge or release authority.

## 1. Evidence and release posture

Authority order is protected code/runtime/migrations/tests → protected architecture/operations docs → exact current PR source and current-head evidence → open Issues/Proposed ADRs → historical snapshots. Pending, queued, stale, predecessor-head, skipped-required, neutral, local-only, author-only, or model-only evidence is not passing evidence.

Current repository inventory is **284 open PRs and 75 open Issues**. Protected `develop` remains exact `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required contexts. The three effective rulesets — `CWL Central required workflows`, `Lock default branch`, and `PR` — remain active. Latest published Naruon release is still `v0.14.4`, `immutable=false`; it is historical publication evidence, not a commercial immutable release candidate.

A releasable candidate requires one exact integrated protected head, terminal required contexts, zero valid unresolved review findings, qualifying independent post-last-push review, current security evidence, immutable publication identity, SBOM/provenance, reproducibility, rollback evidence, and buyer-visible acceptance for changed behavior.

## 2. Central CI/security owner graph

Protected central authority remains `.github/main@e6334e229581a918e2f22de18733b76fa65d7e71`, the protected merge of #2279 exact `d1e4380c15e948aaf104d46aa134fa614058782a`. GitHub REST authority validation, redirect refusal, bearer non-forwarding, evidence-lineage validation, and owner-qualified foreign Semgrep evidence are protected ancestry; #2279 is not an open prerequisite.

- `.github#712` remains the Actions execution-capacity owner. The latest fresh observation is **599 queued / 3 in progress**. Runner acquisition is no longer literally zero at this instant, but three active runs against a ~600-run backlog is not stable capacity. Preserve sole current-head evidence; remove only obsolete/superseded pressure through the canonical owner path; distinguish runner acquisition from workflow parse/admission defects; do not create source-neutral wake commits or blind reruns.
- `.github#2040@652764a37fc8af032f03cbe75da84ca88aee96bb` remains current-main based, 175 ahead / 0 behind, mergeable and Draft. Repository-identity repair and current-main reconciliation are present. Exact-head CodeQL, Python Security, Security, SAST, Runtime Quality and Trusted-uv generations remain nonterminal; local/predecessor evidence does not substitute for hosted exact-head acceptance or independent approval.
- `.github#2291@00082e8dc7ab6bdd3261c4f7131f6e300a66b645` is now the canonical Strix trusted-binder/runtime owner. Its production gate resolves `strix_evidence_binding.py` beside the trusted script source, while executable fixtures keep `STRIX_REPO_ROOT` as a binder-free consumer workspace and invoke the trusted gate by absolute path. Earlier fixture/recovery mistakes remain ancestry only. Current-head Runtime Quality, CodeQL, Security, Python Security and Semgrep runs are queued; same-account COMMENT receipts and predecessor full-suite results are not acceptance.
- `.github#2271@a0e1424de409ec474e7bc6e9f91a9e99b8a0915e` and `.github#2275@572cfed270ae3b3cd38faca4d97ce028093e5373` remain repository-identity/GHAS acceptance lanes. `.github#2272@0379535a87cb3c7fd4b4038c76b0670f4730fb7b` has now ordinary-adopted exact #2291 as its stack base while preserving the Pages caller-input shell boundary; the superseded consumer-binder copies and count-only fixture contract are no longer its effective owner claim. #2272 remains Draft and its Pages Input Security, Runtime Quality, Security, Python Security, Semgrep and CodeQL runs are queued/nonterminal.
- `.github#2269` remains historical redirect/test-seam lineage until a lossless succession audit proves all valid contracts are preserved. `.github#2276` remains the real unchanged-target `code-scanning/analyses` permission/canary boundary. Capability selection cannot manufacture repository permission.

Naruon must not copy central workflow source. It records owner identities and consumes accepted/released contracts through ordinary-forward changes only.

## 3. Product owner boundaries

### Dependency and security ownership

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the sole frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`; current vulnerability-database evidence must be reacquired before inherited Trivy findings are treated as resolved.

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the bounded Starlette TestClient/httpx2 owner at exact `52dfc863d1a5d6e4e80b6366f719dd09f2aa6172`. [#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) is retargeted to #1565 but is not yet a valid Git descendant and does not preserve the direct `httpx2` development/TestClient contract. Preserve #1685's `aiosmtplib==5.1.3`, ordinary/non-force reconcile onto #1565, regenerate one coherent `pyproject.toml` / plain requirements / hashed requirements / `uv.lock` graph, then reacquire installation, warnings-as-errors, TestClient selection, hostile SMTP/lifecycle, Security and CodeQL evidence. Never hand-edit generated lock/hash material as a workaround.

[#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) remains the bounded LLM-provider error-confidentiality owner at exact `9d9d5e0b4bde3febb7cef0e925e493c4fc16cd04`, Draft/open/mergeable. Provider text/traceback suppression plus four-path hostile canaries and restored TRACEABILITY are source-complete, but exact-head hosted acceptance remains incomplete.

### Workspace, migrations and opaque identifiers

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the sole canonical Alembic/bootstrap owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`; descendants must not create parallel migration/bootstrap heads from protected `develop`.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains the sole opaque-UID backfill entropy owner at exact `2ac48fb7e591827804ba8e7e911f211b0c134ddf`, stacked on #1503. It correctly treats Bandit B608 as the hard-coded SQL-expression heuristic rather than a weak-randomness rule, covers all three bootstrap UID generators plus historical migration `0003_prompt_template_scope`, forbids `random()::text`, preserves already-populated identifiers, and retains dedicated regression + doctoring/TRACEABILITY.

Generated direct-`develop` PR [#1736](https://github.com/ContextualWisdomLab/naruon/pull/1736) duplicated that same repair with inflated MEDIUM/cryptographic-vulnerability framing and task-specific Sentinel doctrine. It was repaired ordinary-forward: current head `46c7a9b3a6472f4e4188964ee1778bc99960d752` keeps generated predecessor `22020df3...` as first-parent provenance, adopts #1727 as second parent, points at exact canonical #1727 tree `ea5333fbf6949573a7a99ddb3e1f0439d81bdad8`, retargets onto the #1727 branch, and is Draft with zero effective product delta. #1736 owns no independent security/migration delta and its former direct-`develop` receipts do not transfer.

### LLM governance / released contract

[#1548](https://github.com/ContextualWisdomLab/naruon/issues/1548) / [#1549](https://github.com/ContextualWisdomLab/naruon/pull/1549) remain the sole Naruon LLM-governance owner. `contextual-orchestrator` protected main is still mutable owner source until an immutable API/client/schema release exists. Naruon remains fail-closed and must not bind a mutable owner head as a released contract.

## 4. Buyer-visible UI, Storybook and localization

[#1682](https://github.com/ContextualWisdomLab/naruon/pull/1682) remains the Calendar buyer-truth/detail-sidebar owner. Application CI/Bandit/Semgrep/Docker evidence does not override inherited Trivy and central CodeQL verdict failures. UI Delivery remains FAIL until exact-head security/CodeQL, browser/a11y and qualifying review evidence are terminal.

[#1354](https://github.com/ContextualWisdomLab/naruon/pull/1354) remains a static Storybook design-token precursor only. It does not supply Storybook runtime/config, representative component-state stories, real-browser interaction/a11y/responsive evidence, DTCG artifact or current Figma mapping. Executable Storybook/design-system delivery remains a P1 buyer-visible Gap; shadcn/ui component source is not Storybook evidence.

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single DB-versioned, screen-scoped UI Localization Catalog Gap for KO/EN/JA/ZH/VI/ES/DE/FR. It must follow the canonical migration lineage, keep UI translation separate from ontology labels, avoid whole-catalog browser loading, and verify CJK/text expansion/font fallback/keyboard/focus/touch/a11y/responsive states in Storybook and real browser E2E. [#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) remains the bounded OIDC interaction-state owner rather than a parallel localization implementation.

### Tasks async loading feedback

[#1463](https://github.com/ContextualWisdomLab/naruon/pull/1463) is the repaired canonical owner for visual loading feedback on `팔로업 작업 생성`, `의도 생성`, and `실행 요청`. Ordinary two-parent repair `9673832c785db70470432b42f2e7cd046867a4ee` preserves its prior polluted ancestry, adopts protected `develop`, and reduces effective scope to exactly three intended files: `TasksLayout.tsx` plus synchronized component/page Lucide mocks. Unrelated central-governance, backend URL-validation, doctoring/generated-guidance, scratch artifacts and duplicate CHANGELOG changes are absent from the effective diff.

Fresh review/source verification exposed a still-valid functional RED on that repaired exact head. `의도 생성` and `실행 요청` share the single per-task `currentKnowledgeIntent.state === 'loading'`. Triggering either POST therefore disables both controls, marks both `aria-busy=true`, displays a Loader2 on both, and simultaneously changes the labels to `생성 중` and `실행 중`, even though only one action initiated the request. A resolved/outdated predecessor thread does not make this current behavior correct.

The minimum causal fix is action-specific pending identity per task (for example `pendingAction: 'create' | 'execute' | null`) while preserving mutual exclusion. Both controls may stay disabled while either request is pending, but only the initiating control may be busy, render the spinner and expose its loading label. Add deferred-request regressions that hold create and execute POSTs unresolved independently, prove the active/inactive button states, and prove success/error settlement resets. Reply-SLA has independent state and must remain unchanged.

No source fix is claimed at `9673832c...`; #1463 remains Draft. **UI Delivery Gate: FAIL.** Functional completeness and accessibility semantics fail on the shared-pending-state RED; real-browser keyboard/focus/responsive/AT evidence, terminal exact-head hosted checks and qualifying independent post-last-push approval also remain missing.

Generated direct-`develop` duplicate [#1735](https://github.com/ContextualWisdomLab/naruon/pull/1735) re-proposed the same feature and introduced `TasksLayout.test.tsx.orig` plus duplicate CHANGELOG text. It was repaired ordinary-forward after #1463: current head `be1172b745c0e786597aa1a9ce5142b3b6fa3745` preserves generated predecessor `831bbfe9...`, adopts #1463 `9673832c...`, points at exact canonical #1463 tree `56a1fe2f444db0ddfd482503c7db4814842a291e`, retargets onto #1463, and is Draft with zero effective product delta. #1735 is provenance only; it does not repair the canonical #1463 interaction RED.

## 5. Generated-writer invariant

Generated branches are provenance, not new owners, when an existing canonical owner already covers the delta. Existing examples now include #1727/#1733 evidence/TRACEABILITY rollback, #1728 cross-owner dependency/security/performance rollback, #1734 duplicate NetworkGraph work, #1735 duplicate Tasks loading UX, and #1736 duplicate opaque-ID security work.

Every generated descendant/new duplicate must be checked semantically for existing owner overlap, source/test/fixture deletion, dependency or security regression, bounded-performance regression, severity/rule misclassification, scratch artifacts, duplicate CHANGELOG/doctoring, and self-modifying guidance. Preserve valid ancestry, ordinary-forward to the canonical owner tree/contract, convert duplicate lanes to Draft provenance, and never transfer their predecessor hosted receipts to the owner.

Issue #1178 and PR #1732 remain the OpenSSF governance/legal lane. Current proprietary licensing is an eligibility blocker for OpenSSF Passing, not a technical waiver; do not weaken licensing or branch protection for badge attainment.

## 6. Commercial Gap register

| Priority | Gap | Current boundary | Completion evidence |
| --- | --- | --- | --- |
| P0 | Release-train convergence | 284 open PRs; newest #1735/#1736 reduced to canonical-owner provenance; protected head unchanged | parent-first integration, no orphaned valid delta, one immutable RC source SHA |
| P0 | Actions execution capacity | `.github#712`; 599 queued / 3 in progress in the latest fresh observation | stable runner acquisition, parse/admission RCA separated, obsolete pressure removed without cancelling sole current-head evidence |
| P0 | Central CI/security acceptance | #2279 landed; #2040 current-main reconciled; #2271→#2275 plus #2291→#2272; #2276 real canary pending | terminal exact-head checks, qualifying independent review, #2269 succession, unchanged-target GHAS canary |
| P0 | Dependency-security freshness | frontend #1623 revalidation; backend #1565→#1685 real ancestry/coherent graph repair | current vulnerability scans, coherent manifests/locks, hostile regressions, terminal CI/security/review |
| P0 | LLM provider error confidentiality | #1733 source/test/TRACEABILITY repair present | terminal current-head hosted evidence + zero valid findings + qualifying review |
| P0 | Workspace/migration convergence | #1503 sole migration line; #1727 sole opaque-ID descendant; #1736 zero-delta provenance | one Alembic head, real PostgreSQL fresh/historical execution, ordinary descendant restacks |
| P0 | Released LLM contract | immutable CO release absent | immutable API/client/schema publication + consumer bump + contract/E2E/security/SBOM/provenance |
| P1 | Tasks loading interaction | #1463 bounded owner repaired, but create/execute share one pending state; #1735 is zero-delta provenance | action-specific pending identity, deferred-request regressions, browser keyboard/focus/responsive/AT, terminal exact-head checks/review |
| P1 | Executable Storybook/design system | #1354 static precursor only | pinned runtime/build, representative states, browser/a11y/responsive evidence, token audit, fresh Figma mapping |
| P1 | UI localization | #1731 specified; implementation not yet protected | eight-locale versioned resource + Storybook/browser/a11y + cache/API/rollback evidence |
| P1 | OIDC interaction acceptance | #1729 rendered contract incomplete | real browser/AT/responsive/eight-locale current-head acceptance |
| P1 | Generated-writer owner lock | #1728/#1734/#1735/#1736 demonstrate cross-owner duplication/regression modes | semantic owner-overlap gate, canonical-tree/delta check, no scratch/self-modifying residue, duplicate lanes reduced to provenance |

## 7. Current causal order

1. Restore stable Actions runner acquisition through `.github#712`; do not blind-rerun unchanged heads.
2. Terminalize #2040 exact `652764a...`, then #2271 → #2275 and #2291 → #2272; prove #2269 succession and #2276 unchanged-target GHAS canary.
3. Revalidate frontend dependency-security #1623 against current vulnerability data.
4. Preserve #1565 as the bounded TestClient/httpx2 owner; ordinary/non-force reconcile #1685 and regenerate one coherent dependency graph before hosted acceptance.
5. Terminalize #1733 without reintroducing provider text, traceback logging or generated TRACEABILITY rollback.
6. Integrate #1694 → #1691 and prerequisites, then #1503 as the sole migration lineage; ordinary-adopt #1727 and downstream consumers. Keep #1736 zero-delta provenance only.
7. After contextual-orchestrator publishes an immutable API/client/schema release, finish #1549 without mutable-owner binding.
8. Implement #1731 as the sole localization owner, then ordinary-adopt released screen resources into #1729 and other UI surfaces.
9. Repair #1463's create/execute pending-action identity ordinary-forward, add deferred-request RED→GREEN tests, then acquire real browser keyboard/focus/responsive/AT and hosted/review evidence. Keep #1735 zero-delta provenance only.
10. Reconcile #1354 onto the then-current protected base and build executable Storybook/design-system delivery with real component/browser/a11y/responsive/Figma evidence.
11. Reacquire buyer-visible acceptance, build one exact integrated protected candidate, then publish an immutable Naruon version/tag/package/GitHub Release with SBOM/provenance/reproducibility/rollback.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL.** Source repairs and local evidence do not substitute for terminal exact-head hosted checks, qualifying independent review, current security scans, real external permission evidence, released owner contracts, buyer-visible UI acceptance, or immutable publication.