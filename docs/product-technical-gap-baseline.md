# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.33  
**Observed on:** 2026-09-21 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

v2.32 remains audit-visible as blob `26a92eccb1e5479aef443ce278f293bf01a684b7`; v2.31 remains blob `560fe59c120171492eb113a08ce3ee95c2fdae52`. Earlier v2.x snapshots remain reconstructable from Git history and `docs/product-technical-gap-history/`. Historical snapshots and predecessor workflow/review receipts are audit material, not current merge or release authority.

v2.31 separated durable product/evidence contracts from volatile per-run workflow state. v2.32 advanced the RFC 9110 case-insensitive `q` parameter contract. v2.33 advances the durable localization publication boundary: placeholder schemas are declared tuple/list collections, and arbitrary runtime iterables must not be silently coerced into versioned publication metadata or escape typed validation.

## 1. Evidence hierarchy and release posture

When evidence conflicts, use this order: exact protected-branch code/migrations/tests/runtime contracts → protected architecture/operations docs → exact current PR source and current-head evidence → live Issue/Proposed ADR authority → historical snapshots. Pending, queued, cancelled, stale, predecessor-head, skipped-required, source-neutral, author-only, local-only, or model-only evidence is not passing evidence.

Fresh repository inventory at this observation is **289 open PRs / 75 open Issues**. Protected `develop` remains exact `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required status contexts. Rulesets `18156473` (`CWL Central required workflows`), `17214772` (`Lock default branch`) and `15586698` (`PR`) are active.

Latest Naruon GitHub Release remains `v0.14.4`, published 2026-06-19, with `immutable=false`. It is historical publication evidence only. A commercial candidate requires one exact integrated protected head with terminal required contexts, current security evidence, zero valid unresolved review findings, qualifying independent post-last-push review, immutable publication identity, SBOM/provenance, reproducibility, rollback and buyer-visible acceptance for changed behavior.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL.**

## 2. Central CI/security control plane

Protected central authority remains `ContextualWisdomLab/.github/main@e6334e229581a918e2f22de18733b76fa65d7e71`, the protected merge of #2279.

- `.github#712` remains the sole Actions execution-capacity owner. Runner queue/running state is volatile and must be read from GitHub before any acceptance decision. No blind rerun, source-neutral wake commit or required-check weakening is permitted.
- `.github#1911@c965664a6d7fe0b75bf7ea019a9059220a32f06b` remains the canonical repository-wide/full-suite Trusted-uv owner. Its current hosted acceptance is not GREEN; cancellation is missing hosted acceptance, not source GREEN.
- `.github#2040@bd039185ddf8df88480971cdd3b69c38f4558609` has losslessly converged the Trusted-uv files through #1911. Its remaining owner scope is CodeQL scheduler/credential/runtime-quality; current hosted acceptance remains incomplete and predecessor evidence does not transfer.
- `.github#2291@a8d6261d4fc2c2a82a9b8ad6636e75677ecc5081` is the canonical Strix trusted-runtime/evidence-binder owner and is **source RED before hosted acceptance**. Exact RED `tests/test_strix_trusted_fixture_boundary.py` enumerates 24 specialized fixtures that still call `materialize_trusted_gate_fixture "$repo_root_dir/scripts/ci"`, co-locating trusted binder/runtime with the consumer root and masking a regression to consumer-controlled binder resolution. One unresolved Major current-head review thread independently requires the same complete matrix repair. Acceptance requires all 24 affected fixture families to use a non-consumer trusted runtime, absolute trusted-gate invocation with explicit `STRIX_REPO_ROOT`, binder-free consumer roots and preserved scenario assertions; a representative-only extra fixture is not sufficient.
- `.github#2109@42e3f7a8cbb03b117c898d3e125af87a5c6ce86b` remains the Draft/Ready + stacked-base heavy-workflow admission successor. Its live base has advanced to #2291 `a8d6261d...`, so it is intentionally diverged and must ordinary/non-force adopt the repaired owner after #2291 completes. Same-tree Ready-generation / Draft-withdrawal evidence proves lifecycle shape only, not hosted GREEN.
- `.github#2271`, `#2275`, `#2276` retain repository-identity, GHAS analysis-capability and unchanged-target permission/canary boundaries respectively. #2275 must reacquire its own Python Security/Runtime Quality after the stacked-base admission contract is protected; capability selection cannot manufacture target-repository permission.
- `.github#2272` remains the separate Pages/SAST descendant on #2291 and must consume the completed Strix owner repair instead of copying it.

Naruon does not copy central reusable-workflow source. Consumer PRs wait fail-closed for accepted/released owner contracts and ordinary-restack afterward.

## 3. Product source-owner graph

### 3.1 Dependency/security

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the canonical frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`, Draft/open/mergeable. Its source carries `next`/`eslint-config-next 16.3.4`, `sharp 0.35.4` resolution and security-floor regressions. Its historical exact-head six-workflow GREEN and approval do not prove safety against the current vulnerability database. Later Trivy observations in #1718/#1682 and #1733 predecessor Security Scan `35450922558` require current-base/current-database revalidation in #1623 rather than dependency patches in feature PRs.

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the bounded Starlette TestClient/httpx2 owner. [#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) is the broader backend dependency descendant and must reconcile losslessly onto #1565 while preserving its distinct security-material dependency changes and one coherent resolver-produced lock graph.

[#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) remains the bounded provider-error confidentiality owner at exact `2b47bc7b57732d0dbe00db1ba498b49cdb512e8b`. Its source/test/doctoring delta is separate from inherited dependency Security RED, which is routed to #1623.

### 3.2 Migration/workspace ownership

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the sole workspace/Alembic/bootstrap owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`, stacked on #1565. Canonical migration lineage remains:

`0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`.

#1503 is Draft. The final integrated generation still depends on central execution/admission repair, #1623 current vulnerability revalidation, fresh-bootstrap owner #1694 and repository-local stacked admission owner #1691. Descendants must not create parallel Alembic heads from protected `develop`.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains the opaque-UID backfill entropy owner on #1503. Generated #1736 is provenance only.

### 3.3 NetworkGraph/performance ownership

[#1593](https://github.com/ContextualWisdomLab/naruon/pull/1593) remains the canonical bounded relationship/node option owner at exact `cd6f6d545fe860215d9f6f04b549520f31f68b0e`, tree `ad5da38f3f6391dd4a36d8f0a2a8f6e3a251acc0`. It restores per-iterator read-count and process-global `Map.prototype.values` cleanup contracts after an intervening cross-owner regression.

[#1628](https://github.com/ContextualWisdomLab/naruon/pull/1628) remains the first-five non-empty label-summary child at exact `8786c6e9923a90b7d43ad5439c096ef0f0556148`. Sparse-label traversal can remain O(N); only result storage is bounded. #1674 remains zero-effective-delta provenance and #1675 remains the memoization owner at exact `059481ed9fafb34925d33df2106dcc15cc76268e`.

Generated NetworkGraph lanes, including #1741 and repaired #1734, remain Draft provenance after ordinary/non-force convergence to their canonical owner trees. Generated receipts do not transfer and unsupported O(1)/buyer-p95 claims are not accepted.

### 3.4 Checksum/data-hygiene

Issue #1247 remains the checksum contract. Normal security-labelled checksum surface is SHA-256, SHA-3-256 and BLAKE2b-256 only; MD5/SHA-1 are excluded from the normal surface. #1361 remains the sole `content_checksum_generator` implementation owner on #1623; generated #1739 remains zero-effective-delta provenance.

## 4. UI Localization Catalog — v2.33 material contract

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single buyer-visible **UI Localization Catalog** Gap. Draft [#1740](https://github.com/ContextualWisdomLab/naruon/pull/1740) is the first bounded implementation owner at exact **`b1808593ca9ac147c06d8c6d1cc3ac0d0ed5efb2`**.

#1740 still owns pure domain policy only: KO/EN/JA/ZH/VI/ES/DE/FR release locale identity, persisted → session → weighted `Accept-Language` → product-default precedence, stable screen/message keys, exact simple named-placeholder schemas and typed boundary failures. It owns no database/Alembic revision, HTTP API, browser cache/runtime, Storybook page, authoring UI, ontology-label authority or LLM translation path.

Six ordinary-forward RED→repair sequences define the executable policy:

1. RFC 4647 wildcard ordering and explicit `q=0` exclusion.
2. Boundary-specific control-character codes (`ui_locale_input_invalid` vs `ui_accept_language_invalid`).
3. Control rejection before normalization so leading/trailing CRLF cannot disappear through `.strip()`.
4. **RFC 9110 protocol-whitespace repair**: RED `8265e9bb08cc407c860f148f1823dd0f4ab6d13d` proves that generic Python `str.strip()` and regex `\s` are broader than HTTP OWS. Causal fix `9a6c8bb04be237c968b58987ca6ac4efb789a482` rejects C0/DEL at explicit-locale boundaries, permits HTAB only in the HTTP boundary where OWS allows it, restricts OWS parsing to SP/HTAB, and replaces broad stripping with explicit ASCII normalization.
5. **RFC 9110 quality-parameter case repair**: the standard explicitly defines the content-negotiation parameter name `q` as case-insensitive, while the implementation matched lowercase `q=` only. RED `962e250c54d0da324ec29b21283ab0b02cd55e8c` pins `Q=` semantics at two ordering points. Causal fix `b20b5593498c09855e6ef6fb213d9bf6ea764e15` narrows the change to `[qQ]=` while preserving the existing qvalue and OWS grammar.
6. **Placeholder-schema runtime boundary repair**: RED `e299d29b14943c368e581bcb3d35303a1ba3fb8f` proves blind `tuple(placeholder_schema)` coercion lets `None` escape as raw `TypeError` and lets a one-key mapping masquerade as a valid schema by iterating its key. Causal fix `92a50acef8c7a3fbb38a926994add1641ac6c49d` validates the declared tuple/list container before conversion and emits `ui_placeholder_schema_invalid` for invalid containers. Doctoring/TRACEABILITY is current at `b1808593...`.

Current localization invariants:

- explicit persisted/session locale: reject C0 controls and DEL before normalization; only ASCII SP is benign outer whitespace;
- `Accept-Language`: reject C0/DEL except HTAB in valid RFC 9110 OWS positions; protocol OWS is exactly SP/HTAB; VT, FF, NBSP and other Unicode whitespace are not protocol OWS;
- `q=` and `Q=` are equivalent quality-parameter spellings; qvalue syntax and range remain strict;
- boundary-specific stable validation codes are preserved;
- placeholder schemas are tuple/list runtime collections of unique lowercase names; mappings, generators, scalars, `None` and other arbitrary iterables fail closed rather than inheriting Python iteration semantics;
- once a locale is selected, missing active translation keys must fail rather than silently fall back per message;
- UI-copy resources remain separate from ontology/concept-label authority.

The sixth repair has executable regression source, but **no local/container PASS is claimed** because the current automation runtime does not contain the repository checkout needed for exact-head execution. Exact-head workflow state is authoritative in #1740/checks and must be read fresh before acceptance. The baseline claims no terminal GREEN and no qualifying independent post-last-push review. No predecessor receipt transfer or source-neutral wake commit is permitted.

Persistence remains blocked until #1503 or a verified complete successor reaches protected ancestry. Then localization storage must create the next ordinary single-head Alembic descendant, use normalized 3NF resources, immutable published versions, placeholder/completeness validation, short aggregate publication transactions, screen-scoped reads with ETag/version identity and no whole-catalog browser hydration.

Buyer UI acceptance remains required for KO/EN/JA/ZH/VI/ES/DE/FR across normal/loading/empty/error/permission states, CJK wrapping/font fallback, Latin-script expansion/diacritics, keyboard/focus/touch/AT, responsive widths and exact-version screenshots. #1729 remains the bounded OIDC pending-interaction owner and may consume localization only after a released screen-resource contract exists.

## 5. Other buyer-visible UI and generated-writer boundaries

#1682 remains the Calendar buyer-truth/detail-sidebar owner. #1463 remains the Tasks async-loading owner; generated #1735 is provenance. #1676 remains Settings native-disabled semantics owner; generated #1737 is provenance. #1354 remains the design-token precursor and #1436 the executable Storybook/runtime lineage; dependency/lock security stays with #1623.

Generated #1738 remains zero-effective-delta provenance because its predecessor fabricated participant/attachment data, exposed a dead CTA and supplied static/unmounted mobile panels without authoritative state. Any valid density/mobile intent must be rebuilt through canonical mail/thread/attachment/calendar/mobile owners with actual data and lifecycle/browser/a11y evidence.

Generated descendants are re-read every run. When they duplicate an existing owner or delete/weaken tests, fixtures, traceability, dependency floors, buyer truth or security boundaries, repair is ordinary/non-force adoption/restack. Do not close useful history merely because effective delta becomes zero; keep provenance until the canonical owner integrates or a verified complete successor inherits all valid source/test/evidence.

## 6. LLM/released-contract boundary

#1548/#1549 remain Naruon's LLM-governance owner path. `ContextualWisdomLab/contextual-orchestrator` protected `main` remains exact `5665b0ad1e07ffb5e9f8c59e44b6b2a785298013`; GitHub Releases inventory is exactly `[]`. Naruon therefore has no immutable released CO API/client/schema identity to consume and remains fail-closed. Mutable owner head, copied provider routing or direct provider/model hard-coding is not an acceptable substitute.

## 7. Current causal order

The current minimum causal sequence is:

`.github#712` stable runner acquisition → `.github#1911/#2040` legitimate terminal acceptance → **`.github#2291` complete 24-specialized-fixture trusted-runtime repair, exact-head GREEN/review/hosted acceptance** → #2109/#2272 ordinary adoption → #2271/#2275/#2276 → #1623 current vulnerability revalidation → #1694 → #1691 repository-local stacked admission → #1593 → #1628/#1674/#1675 and generated provenance convergence → #1361/#1739 → #1565/#1685 → #1733 → #1503/#1727 migration lineage → #1740 exact pure-policy acceptance → localization persistence/API/cache after #1503 protected ancestry → immutable contextual-orchestrator release + #1549 → #1729 and eight-locale rendered UI → #1463/#1676 and authoritative #1738 intent → #1354/#1436 Storybook/runtime acceptance → one exact protected integrated candidate → immutable Naruon release with SBOM/provenance/reproducibility/rollback`.

Review/check waiting blocks only the affected lane. Any genuine failure is RCA/fix/retest work, not a reason to weaken a gate. No force push, destructive rebase, self-approval, administrator bypass, source-neutral wake commit, blind rerun, mutable sibling dependency, cross-service SQL, duplicate canonical owner, parallel Alembic head, fabricated buyer-visible content, dead CTA, synthetic status or predecessor-evidence transfer is accepted.
