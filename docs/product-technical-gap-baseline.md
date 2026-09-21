# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.42  
**Observed on:** 2026-09-21 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

v2.41 remains audit-visible as blob `2eba56966e2079e8eeca9e79c22e050b3ab90daa`; v2.40 remains blob `6092e23c545afe845b206842eb118d06999faf8e`; v2.39 remains blob `9db17305b3da88f7571df20a5ce7bbc5f7756acd`; v2.38 remains blob `dbcbb4a5d6a6b369b11bf23f845d2df401d4532e`; v2.37 remains blob `7716f37c571d4d631d6d385515a4cbe76e0e19cd`. Earlier v2.x snapshots remain reconstructable from Git history and `docs/product-technical-gap-history/`. Historical snapshots and predecessor workflow/review receipts are audit material, not current merge or release authority.

v2.42 preserves v2.41's owner-graph repair and adds one performance-evidence boundary discovered from generated #1745. #1745 exact `5cdebe154f1ea24b0f924769d0073c4dc701e7d6` memoizes the `RunHistoryPanel` event-element subtree, but no realistic browser profile, stable-array trigger proof, before/after render receipt, or buyer-path p95 evidence currently supports the claimed performance improvement. The PR is therefore Draft and remains a performance hypothesis rather than accepted product progress. `useMemo` itself is not performance evidence, and task-specific `.jules/bolt.md` doctrine or decorative implementation comments are not product authority.

## 1. Evidence hierarchy and release posture

When evidence conflicts, use this order: exact protected-branch code/migrations/tests/runtime contracts → protected architecture/operations docs → exact current PR source and current-head evidence → live Issue/Proposed ADR authority → historical snapshots. Pending, queued, cancelled, stale, predecessor-head, skipped-required, source-neutral, author-only, local-only, or model-only evidence is not passing evidence.

Protected `develop` remains exact `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required status contexts. Active rulesets and live PR/Issue inventory must be re-read before acceptance; volatile queue and workflow telemetry is never frozen into this baseline.

Latest Naruon GitHub Release remains `v0.14.4`, published 2026-06-19, with `immutable=false`. It is historical publication evidence only. A commercial candidate requires one exact integrated protected head with terminal required contexts, current security evidence, zero valid unresolved review findings, qualifying independent post-last-push review, immutable publication identity, SBOM/provenance, reproducibility, rollback and buyer-visible acceptance for changed behavior.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL.**

## 2. Central CI/security control plane

Protected central `.github/main` is the authority for reusable CI/review/security/release workflows. Naruon consumes accepted/released owner contracts and does not copy central workflow source.

- `.github#712` is the Actions execution-capacity owner. Queue/running state is volatile and must be read live. No blind rerun, source-neutral wake commit or required-check weakening is permitted.
- `.github#1911` remains the canonical repository-wide/full-suite Trusted-uv owner; legitimate terminal hosted acceptance is still required.
- `.github#2040` has converged Trusted-uv ownership through #1911 and retains its distinct CodeQL scheduler/credential/runtime-quality scope; predecessor or cancelled generations are not acceptance.
- `.github#2291` remains source RED until all 24 specialized Strix fixture families stop materializing trusted binder/runtime into the consumer root. Acceptance requires non-consumer trusted runtime, absolute trusted-gate invocation with explicit `STRIX_REPO_ROOT`, binder-free consumer roots, preserved scenario assertions and exact-head hosted/review evidence.
- `.github#2109` is the dependent stacked-admission successor and must ordinary/non-force adopt repaired #2291. `.github#2272` remains its separate Pages/SAST descendant. `.github#2271/#2275/#2276` retain repository-identity, GHAS analysis-capability and real target permission/canary boundaries.

No Naruon product lane may reinterpret incomplete central hosted evidence as product GREEN.

## 3. Product source-owner graph

### 3.1 Dependency/security

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the canonical frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`, Draft/open. Its historical exact-head GREEN does not prove safety against the current vulnerability database. Current Trivy/CodeQL revalidation belongs here rather than in feature PRs.

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the bounded Starlette TestClient/httpx2 owner. [#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) remains the broader backend dependency descendant and must reconcile losslessly onto #1565 with one resolver-produced lock graph.

[#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) remains the bounded provider-error confidentiality owner; inherited dependency Security RED is routed to #1623.

### 3.2 Migration/workspace and opaque UID ownership

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the sole workspace/Alembic/bootstrap owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`, stacked on #1565. Canonical migration lineage remains:

`0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`.

#1503 is Draft. Descendants must not create parallel Alembic heads from protected `develop`.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains the canonical opaque-UID backfill entropy owner on #1503 at exact `2ac48fb7e591827804ba8e7e911f211b0c134ddf`. It owns the bounded `random()` → `gen_random_uuid()` repair for missing public UIDs, focused entropy regression, corrected Bandit/severity diagnosis and doctoring/TRACEABILITY. Opaque identity is defense in depth, not authorization.

Generated #1743 is ordinary/non-force converged to #1727 and remains Draft zero-effective-delta provenance. It must not become a parallel migration/security owner.

### 3.3 NetworkGraph/performance

[#1593](https://github.com/ContextualWisdomLab/naruon/pull/1593) remains the canonical bounded relationship/node option owner at exact `0eb4b6dc5264db8568fd2a54adde9a91feb3cece`, based on #1623. Its effective scope is `NetworkGraph.tsx` plus `NetworkGraph.bounded-options.test.tsx`; unrelated dependency/security drift has been repaired ordinary-forward while retained in ancestry.

[#1628](https://github.com/ContextualWisdomLab/naruon/pull/1628) remains the first-five non-empty label-summary child; #1674 remains zero-effective-delta provenance and #1675 remains memoization owner. Generated #1742 is ordinary/non-force converged to #1593 and remains zero-effective-delta provenance. Generated NetworkGraph descendants must follow current canonical owner ancestry rather than reimplement or inherit stale evidence.

### 3.4 Checksum/data hygiene

Issue #1247 remains the checksum contract. Normal security-labelled checksum surface is SHA-256, SHA-3-256 and BLAKE2b-256 only; MD5/SHA-1 remain outside the normal surface. #1361 remains the canonical `content_checksum_generator` owner; generated #1739 remains provenance.

### 3.5 Settings native-disabled accessibility

[#1676](https://github.com/ContextualWisdomLab/naruon/pull/1676) remains the sole Settings native-disabled semantics owner at exact `8a3ac51662fbe8e49f26a317ac0afe85f853c9ac`, stacked on #1623. Its bounded product tree owns the two source removals, focused `SettingsLayout.native-disabled.test.tsx` regression and standards doctoring; browser/keyboard/responsive acceptance remains a separate delivery gate.

Generated #1716, #1737 and #1744 are provenance only. #1744 started as a direct-`develop` two-line duplicate plus task-specific `.jules/palette.md`; ordinary convergence `e50d25580a3fa840b14855661e215a3368d8a73d` preserves the generated history while adopting the exact #1676 tree, retargeting the PR to #1676 and leaving zero changed files. It must not independently merge or broaden the narrow native-control decision into a repository-wide ban on `aria-disabled`.

### 3.6 AI Hub run-history rendering performance

Generated [#1745](https://github.com/ContextualWisdomLab/naruon/pull/1745) is Draft at exact `5cdebe154f1ea24b0f924769d0073c4dc701e7d6`. It memoizes the mapped `RunEvent` element subtree on `events` reference identity. The implementation is a hypothesis until the claimed trigger is demonstrated on realistic data and browser/runtime conditions.

Acceptance requires a reproducible before/after profile on the same workload, evidence that unrelated state changes preserve `events` identity and currently incur material list construction/reconciliation cost, correctness/a11y parity, and the applicable buyer-path p95 measurement. If the profile instead identifies list volume, reconciliation, unstable data identity, or another bottleneck, repair that causal path rather than retaining `useMemo` by inertia. Synthetic tiny lists, cache-warm-only runs, decorative performance comments and task-specific `.jules/bolt.md` text are not acceptance evidence.

## 4. UI Localization Catalog — v2.42 material contract

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single buyer-visible **UI Localization Catalog** Gap. Draft [#1740](https://github.com/ContextualWisdomLab/naruon/pull/1740) is the first bounded executable owner at exact **`eb8fe8c43a017fed0ea029623d1380d824fd3150`**.

#1740 owns pure domain policy only: KO/EN/JA/ZH/VI/ES/DE/FR release locale identity, persisted → session → weighted `Accept-Language` → product-default precedence, stable screen/message keys, translation-text persistence validation, exact simple named-placeholder schemas and typed boundary failures. It owns no database/Alembic revision, HTTP API, browser cache/runtime, Storybook page, authoring UI, ontology-label authority or LLM translation path.

Thirteen ordinary-forward RED→repair sequences define the executable policy. The durable invariants include:

1. explicit persisted/session locale rejects C0 controls and DEL before normalization; only ASCII SP is benign outer whitespace;
2. `Accept-Language` rejects C0/DEL except HTAB where HTTP OWS permits it; protocol OWS is SP/HTAB rather than Python generic whitespace;
3. `q=` and `Q=` are equivalent quality-parameter names while qvalue syntax/range remains strict;
4. RFC 9110 list recipients ignore at most 32 empty comma members under the Naruon product bound and reject the 33rd with `ui_accept_language_invalid`;
5. runtime `product_default` is type-validated before set membership so arbitrary Python hashability cannot leak as product semantics;
6. `placeholder_schema` is tuple/list only, validates element type/syntax before uniqueness, and never relies on incidental iterable/hashability behavior;
7. translated catalog text rejects U+0000, isolated surrogate code points and non-string input before placeholder parsing/persistence;
8. wildcard/q=0 behavior preserves release-level supported-locale exclusions;
9. RFC 4647 wildcard control flow preserves positive later concrete ranges even when they are unsupported by the current release. `*;q=0.9, pt-BR;q=0.8` reaches `(ko, product_default)` rather than falsely attributing the same locale to `accept_language`;
10. **placeholder source syntax is canonical before parser normalization.** `{account_name}` is valid; `{account_name:}`, conversions and format specifications are invalid publication input even where Python's formatter would produce the same visible value. RED `8b19c7dfe43e3dca3c1e4b8980c0a9998a3aec43` proves the empty-format-specifier ambiguity and fix `6ed310e1065940fa14c258b48412490e7b98d751` preserves lexical `:`/`!` operator information before `Formatter.parse()`.

Python 3.14 defines `:` as the delimiter for `format_spec` and documents that an empty format specification has default behavior. The product therefore does not use parsed semantic equivalence as publication identity; versioned source must satisfy the narrower catalog grammar.

No exact-head local/container PASS is claimed for the current thirteenth repair. Current-head hosted full-suite/coverage/security evidence and qualifying independent post-last-push review must be reacquired naturally. Predecessor workflow/review receipts do not transfer.

### Localization persistence/API/UI order

Translation persistence must wait until #1503 or a verified complete successor reaches protected ancestry, then create the next ordinary Alembic descendant from the then-current single head. Published catalog versions are immutable, complete for all eight release locales, placeholder/text validated before publication and rollback-selectable without rewriting history.

A screen-scoped read contract returns only the requested screen/locale with immutable resource version and ETag/cache identity. Do not ship a browser-wide mega-catalog, a per-key network waterfall or a heavy SPA i18n dependency by default. UI-copy authority remains separate from ontology/concept labels.

KO/EN/JA/ZH/VI/ES/DE/FR acceptance requires Storybook plus real-browser E2E for normal/loading/empty/error/permission states, keyboard/focus/screen-reader/touch semantics, CJK wrapping/font fallback, Vietnamese diacritics, DE/FR/ES text expansion, mobile/intermediate widths and exact resource-version/source-head screenshots.

## 5. Contextual Orchestrator and LLM boundary

All Naruon LLM behavior must consume an immutable released contextual-orchestrator API/client/schema contract. No mutable owner head, source copy, provider group hard-code or direct provider fallback is acceptable. Until contextual-orchestrator has a canonical release identity satisfying the product contract, dependent Naruon work such as #1549 remains fail-closed. Model-backed GitHub Actions must use the central `orchestrator/free` contract and gateway token only.

## 6. Remaining commercial/buyer-visible gaps

The current causal order remains:

`.github#712` stable runner acquisition → #1911/#2040 legitimate terminal acceptance → #2291 complete 24-specialized-fixture trusted-runtime repair → #2109/#2272 → #2271/#2275/#2276 → #1623 current-vulnerability revalidation → #1694 fresh-bootstrap Alembic repair → #1691 repository-local stacked admission → #1593 → #1628/#1674/#1675 → checksum/backend dependency owners → #1676 Settings native-disabled owner + zero-delta generated provenance → #1745 measured AI Hub performance acceptance or causal replacement → #1503 → #1727 plus zero-delta provenance → #1740 exact-head policy acceptance → localization persistence/API/cache → immutable contextual-orchestrator release + #1549 → #1729 and eight-locale rendered UI → Tasks/Settings and authoritative #1738 intent through their canonical owners → Storybook owners → exact protected integrated candidate → immutable Naruon release with SBOM/provenance/reproducibility/rollback.`

Wait state in one lane does not stop repair/development in independent lanes. Generated descendants remain open as provenance unless a verified successor fully inherits all valid delta/test/fixture/contract/evidence or the user explicitly authorizes closure.

## 7. Delivery gates

**Merge/Release Gate: FAIL.** There is no exact protected integrated candidate satisfying required checks, current security evidence, independent post-last-push review and immutable release evidence.

**UI Delivery Gate: FAIL.** The eight-locale catalog persistence/API/page composition, Storybook/browser/a11y acceptance and current exact resource-version evidence are not yet integrated. #1745 also lacks measured browser performance evidence and cannot be treated as UI delivery progress yet.

Do not claim completion from routine reporting, queued checks, historical GREEN, mutable release artifacts, generated-provenance branches, unmeasured memoization, or source-only correctness. The next run must fresh-read all live authority before mutating or accepting any lane.
