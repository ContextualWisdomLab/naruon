# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.19  
**Observed on:** 2026-09-20 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

This file is the current product/technical authority overlay. v2.18 remains audit-visible as blob `25ec56b6493a1ed577ce4481072d6db6c74ec7eb`; v2.17 remains blob `d611e0d3cb1dd90e9d8429fcfa112a977e989726`; v2.16 remains blob `c09c9e2f02b9f173b6d14689730b382c03701216`; v2.15 remains blob `07699b4588e1b8198c1357b8ca2064703151628f`. Earlier snapshots remain audit material in Git ancestry and `docs/product-technical-gap-history/`. Historical evidence is not current merge or release authority.

## 1. Evidence and release posture

Authority order is protected code/runtime/migrations/tests → protected architecture/operations docs → exact current PR source and current-head evidence → open Issues/Proposed ADRs → historical snapshots. Pending, queued, stale, predecessor-head, skipped-required, neutral, local-only, author-only, or model-only evidence is not passing evidence.

Current repository inventory is **284 open PRs and 75 open Issues**. Protected `develop` remains exact `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required contexts. Latest published Naruon release remains `v0.14.4`, `immutable=false`; it is historical publication evidence, not a commercial immutable release candidate.

A releasable candidate requires one exact integrated protected head, terminal required contexts, zero valid unresolved review findings, qualifying independent post-last-push review, current security evidence, immutable publication identity, SBOM/provenance, reproducibility, rollback evidence, and buyer-visible acceptance for changed behavior.

## 2. Central CI/security owner graph

Protected central authority remains `.github/main@e6334e229581a918e2f22de18733b76fa65d7e71`, the protected merge of #2279 exact `d1e4380c15e948aaf104d46aa134fa614058782a`. GitHub REST authority validation, redirect refusal, bearer non-forwarding, evidence-lineage validation, and owner-qualified foreign Semgrep evidence are protected ancestry; #2279 is not an open prerequisite.

- `.github#712` remains the Actions execution-capacity owner. The latest fresh observation before this baseline generation is **620 queued / 3 in progress**. Runner acquisition is intermittent rather than totally absent, but this is not stable capacity. Preserve sole current-head evidence; remove only obsolete/superseded pressure through the canonical owner path; distinguish runner acquisition from workflow parse/admission defects; do not create source-neutral wake commits or blind reruns.
- `.github#2040` has advanced beyond its former `652764a37fc8af032f03cbe75da84ca88aee96bb` authority to exact `7901ca565fb93a9e869cd4136476384ac3a07bdf`, **177 ahead / 0 behind** protected main. Its ordinary current-main reconciliation and repository-identity repair remain ancestry. New RED `82a4e2a83be9543fe02cd208bee6837aaf5aa085` and GREEN `7901ca5...` add the Noema document hash lock to Trusted uv full-suite trigger/cache/install closure. Current CodeQL is pending and SAST/Python Security/Runtime Quality/Trusted uv/Security are nonterminal; no predecessor evidence transfers.
- The new #2040 Trusted-uv delta overlaps canonical full-suite owner `.github#1911@dfeadc7adfb02d73e166104f2987f14fbf7fe82e`. #1911 explicitly owns `trusted-uv-materializer-quality-ci.yml` repository-wide dependency closure and already carries the same Noema-lock invariant, but its current head is **22 ahead / 33 behind** protected main with merge base `64aa08d7...`. Owner-path comments require #1911 to reconcile ordinary/non-force onto current protected main first, then #2040 to adopt/adapt the canonical result rather than retain a parallel Trusted-uv owner. Neither PR is close-as-superseded material.
- `.github#2271@a0e1424de409ec474e7bc6e9f91a9e99b8a0915e` remains the CodeQL repository-identity admission owner, 8 ahead / 0 behind protected main, Draft/Proposed. SAST is terminal success while aggregate CodeQL/Python Security/Security remain nonterminal; partial hosted acquisition is not aggregate GREEN.
- `.github#2275@572cfed270ae3b3cd38faca4d97ce028093e5373` remains stacked on #2271 and owns GHAS analysis-read credential selection only. SAST is terminal success; CodeQL/Security remain nonterminal. #2276 still must prove real target-repository `code-scanning/analyses` permission; selector logic cannot manufacture repository permission.
- `.github#2291@782d67b433aa71cf2c81b2a81f55ae192a317f3b` is the canonical Strix trusted-binder/runtime owner. It keeps `STRIX_REPO_ROOT` as the consumer scan/artifact root while trusted gate/model-helper/binder runtime stays source-owned. The latest integration also models the `.github` gate/model helper as consumer source under scan without copying the binder. Local exact-tree evidence is recorded by the owner, but fresh Runtime Quality/CodeQL/Security/Python Security/Semgrep runs are queued/nonterminal. It is Ready for review, not merge-accepted.
- `.github#2272@6ac3d96dc8369a31be0fc76dd74d002424708215` now stacks on exact #2291 `782d67b...`, preserves the Pages caller-input shell boundary, and removes its superseded parallel Strix owner claim. It remains Draft/Proposed with fresh hosted acceptance and independent review pending.
- `.github#2269` remains historical redirect/test-seam lineage until a lossless succession audit proves all valid contracts are preserved. `.github#2276` remains the unchanged-target GHAS permission/canary boundary.

Naruon must not copy central workflow source. It records owner identities and consumes accepted/released contracts through ordinary-forward changes only.

## 3. Product owner boundaries

### Dependency and security ownership

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the sole frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`; current vulnerability-database evidence must be reacquired before inherited Trivy findings are treated as resolved.

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the bounded Starlette TestClient/httpx2 owner at exact `52dfc863d1a5d6e4e80b6366f719dd09f2aa6172`. [#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) is retargeted to #1565 but is not yet a valid Git descendant and does not preserve the direct `httpx2` development/TestClient contract. Preserve #1685's `aiosmtplib==5.1.3`, ordinary/non-force reconcile onto #1565, regenerate one coherent `pyproject.toml` / plain requirements / hashed requirements / `uv.lock` graph, then reacquire installation, warnings-as-errors, TestClient selection, hostile SMTP/lifecycle, Security and CodeQL evidence. Never hand-edit generated lock/hash material as a workaround.

[#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) remains the bounded LLM-provider error-confidentiality owner at exact `9d9d5e0b4bde3febb7cef0e925e493c4fc16cd04`, Draft/open/mergeable. Provider text/traceback suppression plus four-path hostile canaries and restored TRACEABILITY are source-complete, but exact-head hosted acceptance remains incomplete.

### Workspace, migrations and opaque identifiers

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the sole canonical Alembic/bootstrap owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`; descendants must not create parallel migration/bootstrap heads from protected `develop`.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains the sole opaque-UID backfill entropy owner at exact `2ac48fb7e591827804ba8e7e911f211b0c134ddf`, stacked on #1503. It treats Bandit B608 as the hard-coded SQL-expression heuristic rather than a weak-randomness rule, covers all three bootstrap opaque-ID generators plus historical migration `0003_prompt_template_scope`, forbids `random()::text`, preserves populated identifiers, and retains dedicated regression plus doctoring/TRACEABILITY.

Generated direct-`develop` PR [#1736](https://github.com/ContextualWisdomLab/naruon/pull/1736) remains Draft provenance only. Current `46c7a9b3a6472f4e4188964ee1778bc99960d752` adopts #1727 and has zero effective product delta; generated severity inflation, Sentinel doctrine, and weaker standalone implementation are not owner authority.

### LLM governance / released contract

[#1548](https://github.com/ContextualWisdomLab/naruon/issues/1548) / [#1549](https://github.com/ContextualWisdomLab/naruon/pull/1549) remain the sole Naruon LLM-governance owner. `contextual-orchestrator` protected main is mutable owner source until an immutable API/client/schema release exists. Naruon remains fail-closed and must not bind a mutable owner head as a released contract. Legacy protected `AGENTS.md` provider/model fallback prose does not override this owner path.

## 4. Buyer-visible UI, Storybook and localization

[#1682](https://github.com/ContextualWisdomLab/naruon/pull/1682) remains the Calendar buyer-truth/detail-sidebar owner. Application CI/Bandit/Semgrep/Docker evidence does not override inherited Trivy and central CodeQL verdict failures. UI Delivery remains FAIL until exact-head security/CodeQL, browser/a11y and qualifying review evidence are terminal.

[#1354](https://github.com/ContextualWisdomLab/naruon/pull/1354) remains a static Storybook design-token precursor only. It does not supply Storybook runtime/config, representative component-state stories, real-browser interaction/a11y/responsive evidence, DTCG artifact or current Figma mapping. Executable Storybook/design-system delivery remains a P1 buyer-visible Gap; shadcn/ui component source is not Storybook evidence.

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single DB-versioned, screen-scoped UI Localization Catalog Gap for KO/EN/JA/ZH/VI/ES/DE/FR. It follows canonical migration lineage, keeps UI translation separate from ontology labels, avoids whole-catalog browser loading, and requires CJK/text expansion/font fallback/keyboard/focus/touch/a11y/responsive evidence. [#1729](https://github.com/ContextualWisdomLab/naruon/pull/1729) remains the bounded OIDC interaction-state owner rather than a parallel localization implementation.

### Tasks async loading feedback

[#1463](https://github.com/ContextualWisdomLab/naruon/pull/1463) is the canonical Tasks async-loading owner. The bounded owner repair `9673832c785db70470432b42f2e7cd046867a4ee` had exposed a real interaction/accessibility RED: `의도 생성` and `실행 요청` shared one per-task loading state, so either POST made both controls claim busy/spinner/loading labels.

This RED is now repaired ordinary-forward, without reopening unrelated owners:

- focused RED `5caa7713293e610e68c87b0db0cc872c3ad2e068` adds a deferred-request contract for create and execute separately;
- exact current GREEN/source repair `bf9ce8e8f5ad1b4cf2f2ddc9c5f547a7d733f60e` adds `pending_action: 'create' | 'execute' | null`, preserves shared disablement for mutual exclusion, and assigns `aria-busy`, Loader2 and the busy label only to the initiating action;
- success/error settlement clears pending identity; reply-SLA keeps its independent state;
- protected-base compare is **16 ahead / 0 behind**, four effective frontend files, mergeable/Draft.

Exact `bf9ce8e...` has fresh Application CI, CodeQL, Security, Semgrep, Bandit and Docker generations, but all are currently queued/nonterminal. No local/container PASS is claimed for this generation. Real-browser keyboard/focus/touch/responsive/assistive-technology evidence and qualifying independent post-last-push review are also absent. **UI Delivery Gate therefore remains FAIL despite the source-level functional repair.**

Generated duplicate [#1735](https://github.com/ContextualWisdomLab/naruon/pull/1735) was stale after #1463 advanced. It was descendant-restacked ordinary-forward at `b53d2018a14ec0aa2ed778142d04ef4abd7be1d7`: existing provenance is first parent, exact current #1463 is an additional parent, and the tree is exactly current #1463 tree `c14b5fbd79c4eb91919710524b7466b9d5a58a5c`. Fresh compare from #1463 is **ahead 3 / behind 0 / zero changed files**. #1735 remains Draft provenance only and owns no parallel UI delta or acceptance receipt.

## 5. Generated-writer and descendant invariants

Generated branches are provenance, not new owners, when an existing canonical owner already covers the delta. Existing examples include #1728 cross-owner dependency/security/performance rollback, #1734 duplicate NetworkGraph work, #1735 duplicate Tasks loading UX, and #1736 duplicate opaque-ID security work.

Every generated descendant/new duplicate must be checked semantically for owner overlap, source/test/fixture deletion, dependency/security/performance regression, severity/rule misclassification, scratch artifacts, duplicate CHANGELOG/doctoring, and self-modifying guidance. Preserve valid ancestry, ordinary-forward to the canonical owner tree/contract, convert duplicate lanes to Draft provenance, and never transfer predecessor hosted receipts.

Canonical owner movement also invalidates an earlier zero-delta provenance relation. When the owner advances, descendants must be freshly compared and ordinary-restacked if necessary. #1735 demonstrates this rule: it became 2 owner commits behind #1463 after the RED→GREEN repair and was immediately restored to a zero-effective-delta descendant without force rewriting history.

Issue #1178 and PR #1732 remain the OpenSSF governance/legal lane. Current proprietary licensing is an eligibility blocker for OpenSSF Passing, not a technical waiver; do not weaken licensing or branch protection for badge attainment.

## 6. Commercial Gap register

| Priority | Gap | Current boundary | Completion evidence |
| --- | --- | --- | --- |
| P0 | Release-train convergence | 284 open PRs; #1735/#1736 are canonical-owner provenance; protected head unchanged | parent-first integration, descendant restack after owner movement, no orphaned valid delta, one immutable RC source SHA |
| P0 | Actions execution capacity | `.github#712`; 620 queued / 3 in progress in latest pre-generation observation | stable runner acquisition, parse/admission RCA separated, obsolete pressure removed without cancelling sole current-head evidence |
| P0 | Central CI/security acceptance | #2279 landed; #2040 current-main lineage plus #1911 Trusted-uv overlap finding; #2271→#2275 and #2291→#2272; #2276 canary pending | canonical-owner convergence, terminal exact-head checks, qualifying independent review, #2269 succession, unchanged-target GHAS canary |
| P0 | Dependency-security freshness | frontend #1623 revalidation; backend #1565→#1685 real ancestry/coherent graph repair | current vulnerability scans, coherent manifests/locks, hostile regressions, terminal CI/security/review |
| P0 | LLM provider error confidentiality | #1733 source/test/TRACEABILITY repair present | terminal current-head hosted evidence + zero valid findings + qualifying review |
| P0 | Workspace/migration convergence | #1503 sole migration line; #1727 sole opaque-ID descendant; #1736 zero-delta provenance | one Alembic head, real PostgreSQL fresh/historical execution, ordinary descendant restacks |
| P0 | Released LLM contract | immutable CO release absent | immutable API/client/schema publication + consumer bump + contract/E2E/security/SBOM/provenance |
| P1 | Tasks loading interaction | #1463 source-level RED→GREEN at `bf9ce8e...`; #1735 restacked zero-delta provenance | exact-head focused/hosted GREEN, browser keyboard/focus/touch/responsive/AT evidence, qualifying review |
| P1 | Executable Storybook/design system | #1354 static precursor only | pinned runtime/build, representative states, browser/a11y/responsive evidence, token audit, fresh Figma mapping |
| P1 | UI localization | #1731 specified; implementation not yet protected | eight-locale versioned resource + Storybook/browser/a11y + cache/API/rollback evidence |
| P1 | OIDC interaction acceptance | #1729 rendered contract incomplete | real browser/AT/responsive/eight-locale current-head acceptance |
| P1 | Generated-writer owner lock | #1728/#1734/#1735/#1736 demonstrate duplicate/regression and owner-movement modes | semantic owner-overlap gate, owner-movement descendant sweep, canonical-tree/delta check, no scratch/self-modifying residue |

## 7. Current causal order

1. Restore stable Actions runner acquisition through `.github#712`; do not blind-rerun unchanged heads.
2. Reconcile `.github#1911` onto current protected main and converge its canonical Trusted-uv/full-suite dependency closure with #2040; then terminalize #2040 exact `7901ca5...` without duplicate ownership.
3. Terminalize #2271 → #2275 and #2291 → #2272; prove #2269 succession and #2276 unchanged-target GHAS canary.
4. Revalidate frontend dependency-security #1623 against current vulnerability data.
5. Preserve #1565 as the bounded TestClient/httpx2 owner; ordinary/non-force reconcile #1685 and regenerate one coherent dependency graph before hosted acceptance.
6. Terminalize #1733 without reintroducing provider text, traceback logging or generated TRACEABILITY rollback.
7. Integrate #1694 → #1691 and prerequisites, then #1503 as the sole migration lineage; ordinary-adopt #1727 and downstream consumers. Keep #1736 provenance only.
8. After contextual-orchestrator publishes an immutable API/client/schema release, finish #1549 without mutable-owner binding.
9. Implement #1731 as the sole localization owner, then ordinary-adopt released screen resources into #1729 and other UI surfaces.
10. Terminalize #1463 exact `bf9ce8e...`: run its focused deferred-request contract and hosted gates on the unchanged head, acquire real browser keyboard/focus/touch/responsive/AT evidence and qualifying independent review. Keep #1735 zero-effective-delta provenance aligned if the owner moves again.
11. Reconcile #1354 onto the then-current protected base and build executable Storybook/design-system delivery with real component/browser/a11y/responsive/Figma evidence.
12. Reacquire buyer-visible acceptance, build one exact integrated protected candidate, then publish an immutable Naruon version/tag/package/GitHub Release with SBOM/provenance/reproducibility/rollback.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL.** Source repairs and local evidence do not substitute for terminal exact-head hosted checks, qualifying independent review, current security scans, real external permission evidence, released owner contracts, buyer-visible UI acceptance, or immutable publication.
