# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.37  
**Observed on:** 2026-09-21 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

v2.36 remains audit-visible as blob `46a79021d3811b8e0018021a437326be19bba6df`; v2.35 remains blob `bd77e2d74834da8dc916d5979b828fe4cc200dea`; v2.34 remains blob `0244bcccd5dfeed18d0994429a70ba6428a3076e`; v2.33 remains blob `91b1dcc62409da0720823f136af204ddb97b8829`; v2.32 remains blob `26a92eccb1e5479aef443ce278f293bf01a684b7`; v2.31 remains blob `560fe59c120171492eb113a08ce3ee95c2fdae52`. Earlier v2.x snapshots remain reconstructable from Git history and `docs/product-technical-gap-history/`. Historical snapshots and predecessor workflow/review receipts are audit material, not current merge or release authority.

v2.31 separated durable product/evidence contracts from volatile per-run workflow state. v2.32 advanced the RFC 9110 case-insensitive `q` parameter contract. v2.33 advanced the placeholder-schema container boundary. v2.34 advanced the translation-text persistence boundary. v2.35 advanced placeholder-element validation ordering. v2.36 added the product-default runtime type boundary and refreshed the live owner graph after generated #1742/#1743 and a new intervening #1593 regression were ordinary/non-force converged to their canonical owners. **v2.37 adds RFC 9110 recipient-side empty-list handling for the list-based `Accept-Language` field and advances the pure-policy owner to exact #1740 `8450a94d8f67ee704f126daca8fc838a3c5e5981`.**

## 1. Evidence hierarchy and release posture

When evidence conflicts, use this order: exact protected-branch code/migrations/tests/runtime contracts → protected architecture/operations docs → exact current PR source and current-head evidence → live Issue/Proposed ADR authority → historical snapshots. Pending, queued, cancelled, stale, predecessor-head, skipped-required, source-neutral, author-only, local-only, or model-only evidence is not passing evidence.

Fresh repository inventory at this observation is **291 open PRs / 75 open Issues**. Protected `develop` remains exact `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required status contexts. Rulesets `18156473` (`CWL Central required workflows`), `17214772` (`Lock default branch`) and `15586698` (`PR`) are active.

Latest Naruon GitHub Release remains `v0.14.4`, published 2026-06-19, with `immutable=false`. It is historical publication evidence only. A commercial candidate requires one exact integrated protected head with terminal required contexts, current security evidence, zero valid unresolved review findings, qualifying independent post-last-push review, immutable publication identity, SBOM/provenance, reproducibility, rollback and buyer-visible acceptance for changed behavior.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL.**

## 2. Central CI/security control plane

Protected central authority remains `ContextualWisdomLab/.github/main@e6334e229581a918e2f22de18733b76fa65d7e71`, the protected merge of #2279.

- `.github#712` remains the sole Actions execution-capacity owner. Runner queue/running state is volatile and must be read from GitHub before any acceptance decision. No blind rerun, source-neutral wake commit or required-check weakening is permitted.
- `.github#1911@c965664a6d7fe0b75bf7ea019a9059220a32f06b` remains the canonical repository-wide/full-suite Trusted-uv owner. Its current hosted acceptance is not GREEN; cancellation is missing hosted acceptance, not source GREEN.
- `.github#2040@bd039185ddf8df88480971cdd3b69c38f4558609` has losslessly converged the Trusted-uv files through #1911. Its remaining owner scope is CodeQL scheduler/credential/runtime-quality; current hosted acceptance remains incomplete and predecessor evidence does not transfer.
- `.github#2291@a8d6261d4fc2c2a82a9b8ad6636e75677ecc5081` remains source RED before hosted acceptance. Exact RED `tests/test_strix_trusted_fixture_boundary.py` enumerates 24 specialized fixtures that still co-locate trusted binder/runtime with the consumer root. Acceptance requires all 24 affected fixture families to use a non-consumer trusted runtime, absolute trusted-gate invocation with explicit `STRIX_REPO_ROOT`, binder-free consumer roots and preserved scenario assertions.
- `.github#2109@42e3f7a8cbb03b117c898d3e125af87a5c6ce86b` remains the dependent stacked-admission successor and must ordinary/non-force adopt the repaired #2291 owner after that repair is complete.
- `.github#2271`, `#2275`, `#2276` retain repository-identity, GHAS analysis-capability and unchanged-target permission/canary boundaries; `.github#2272` remains the separate Pages/SAST descendant on #2291.

Naruon does not copy central reusable-workflow source. Consumer PRs wait fail-closed for accepted/released owner contracts and ordinary-restack afterward.

## 3. Product source-owner graph

### 3.1 Dependency/security

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the canonical frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`, Draft/open. Historical exact-head GREEN does not prove safety against the current vulnerability database; dependency/security changes remain owned here rather than in feature PRs.

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the bounded Starlette TestClient/httpx2 owner. [#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) remains the broader backend dependency descendant and must reconcile losslessly onto #1565 with one resolver-produced lock graph.

[#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) remains the bounded provider-error confidentiality owner at exact `2b47bc7b57732d0dbe00db1ba498b49cdb512e8b`; inherited dependency Security RED is routed to #1623.

### 3.2 Migration/workspace ownership and opaque UID entropy

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the sole workspace/Alembic/bootstrap owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`, stacked on #1565. Canonical migration lineage remains:

`0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`.

#1503 is Draft. Descendants must not create parallel Alembic heads from protected `develop`.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains the canonical opaque-UID backfill entropy owner on #1503 at exact `2ac48fb7e591827804ba8e7e911f211b0c134ddf`. It owns the bounded `random()` → `gen_random_uuid()` repair for missing `prompt_uid`, WebDAV `source_uid`, and `folder_uid`, its focused entropy regression, corrected Bandit/severity diagnosis, and doctoring/TRACEABILITY. Opaque identity is defense in depth, not authorization.

Generated #1743 started directly from `develop`, duplicated the same source repair, edited the historical `0003_prompt_template_scope` migration plus bootstrap source and asserted CRITICAL/authentication-bypass impact without #1727's narrower owner contract. It has been ordinary/non-force converged: `b4867a85c4b53f4155136abf9fcd68ae84f6a1a1` preserves the generated predecessor as first-parent history, adopts #1727 exact tree `ea5333fbf6949573a7a99ddb3e1f0439d81bdad8`, retargets onto #1727 and leaves **0 changed files / 0 additions / 0 deletions**. #1743 is Draft provenance, not a parallel security/migration owner.

### 3.3 NetworkGraph/performance ownership

[#1593](https://github.com/ContextualWisdomLab/naruon/pull/1593) remains the canonical bounded relationship/node option owner. A fresh intervening commit `b2766686624ec1f35d4dbc523a2c35d763e8c717` again mixed unrelated CHANGELOG/dependency-lock/security-test changes and rewrote the bounded-options regression after prior repair `cd6f6d545fe860215d9f6f04b549520f31f68b0e`. Ordinary child **`0eb4b6dc5264db8568fd2a54adde9a91feb3cece`** restores canonical tree `ad5da38f3f6391dd4a36d8f0a2a8f6e3a251acc0`; current effective scope is again only `NetworkGraph.tsx` and `NetworkGraph.bounded-options.test.tsx`.

[#1628](https://github.com/ContextualWisdomLab/naruon/pull/1628) remains the separate first-five non-empty label-summary child. Sparse-label traversal can remain O(N); only result storage is bounded. #1674 remains zero-effective-delta provenance and #1675 remains the memoization owner.

Generated #1742 directly reimplemented #1593's relationship/node bounded loops from protected `develop` and repeated an unsupported end-to-end `O(1)`/`O(K)` claim. It has been ordinary/non-force converged: `05c0b87f79b9e49416a0316f1cc91075c9a1e574` preserves generated history, adopts current #1593 canonical tree, retargets onto #1593 and leaves **0 changed files / 0 additions / 0 deletions**. #1742 is Draft provenance. Generated receipts do not transfer.

Generated NetworkGraph lanes remain Draft provenance after ordinary/non-force convergence to their canonical owner trees. If a canonical owner moves, descendants must re-read intervening deltas and follow the current owner without force-rewrite.

### 3.4 Checksum/data-hygiene

Issue #1247 remains the checksum contract. Normal security-labelled checksum surface is SHA-256, SHA-3-256 and BLAKE2b-256 only; MD5/SHA-1 are excluded from the normal surface. #1361 remains the sole `content_checksum_generator` implementation owner on #1623; generated #1739 remains zero-effective-delta provenance.

## 4. UI Localization Catalog — v2.37 material contract

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single buyer-visible **UI Localization Catalog** Gap. Draft [#1740](https://github.com/ContextualWisdomLab/naruon/pull/1740) is the first bounded implementation owner at exact **`8450a94d8f67ee704f126daca8fc838a3c5e5981`**.

#1740 owns pure domain policy only: KO/EN/JA/ZH/VI/ES/DE/FR release locale identity, persisted → session → weighted `Accept-Language` → product-default precedence, stable screen/message keys, translation-text persistence validation, exact simple named-placeholder schemas and typed boundary failures. It owns no database/Alembic revision, HTTP API, browser cache/runtime, Storybook page, authoring UI, ontology-label authority or LLM translation path.

Ten ordinary-forward RED→repair sequences define the executable policy:

1. RFC 4647 wildcard ordering and explicit `q=0` exclusion.
2. Boundary-specific control-character codes (`ui_locale_input_invalid` vs `ui_accept_language_invalid`).
3. Control rejection before normalization so leading/trailing CRLF cannot disappear through `.strip()`.
4. **RFC 9110 protocol-whitespace repair**: RED `8265e9bb08cc407c860f148f1823dd0f4ab6d13d` → fix `9a6c8bb04be237c968b58987ca6ac4efb789a482`; protocol OWS is SP/HTAB, not Python's broader whitespace set.
5. **RFC 9110 quality-parameter case repair**: RED `962e250c54d0da324ec29b21283ab0b02cd55e8c` → fix `b20b5593498c09855e6ef6fb213d9bf6ea764e15`; `q=` and `Q=` have identical parameter-name semantics while qvalue grammar remains strict.
6. **Placeholder-schema runtime boundary repair**: RED `e299d29b14943c368e581bcb3d35303a1ba3fb8f` → fix `92a50acef8c7a3fbb38a926994add1641ac6c49d`; runtime schema containers are tuple/list only.
7. **Translation-text persistence boundary repair**: RED `3e251cc253d2ccf62ec1a3209ab629c6cffbe149` → fix `dec6c694dcf930ef184b158de04260d8db433bec`; NUL, surrogate and non-string translation input fail before persistence/placeholder parsing with `ui_translation_input_invalid`.
8. **Placeholder-element validation-order repair**: RED `489bfd4fa2d6f3630cf33412f6d910d73c47e110` → fix `244cff4f8d8805f2b3eacf91a75c7da84052bfc2`; every element is validated before `set(...)` duplicate detection so nested unhashable values cannot leak raw `TypeError`.
9. **Product-default runtime boundary repair**: RED `652137bd5b4fae436af207d8823a4e6e5122b8a0` proves list/mapping `product_default` values reach frozenset membership and leak raw unhashable `TypeError`. Causal fix `f079bb270aadb2748937d5491b718e87b4198834` validates runtime string type before membership and preserves `ui_locale_unsupported`; doctoring `cf10a222d55fc27e49b28b7a9fb55f4d31a349aa` records this as an internal product/runtime invariant.
10. **RFC 9110 list-recipient repair**: RED `20a7475c190585a1f94d34bd19c363f97dcc4e81` proves the parser rejects empty list elements in values such as `, fr;q=0.4, , en;q=0.8,` and an all-empty `,` field. Causal fix `eff473a04fd8cca5d76396c36ff0c1dbf3a033f6` ignores empty members before language-range matching, as RFC 9110 §5.6.1.2 requires recipients to do for a reasonable number of empty list elements. Empty members add no preference, do not become wildcards, and an all-empty list falls through to the existing product-default tier. Doctoring `8450a94d8f67ee704f126daca8fc838a3c5e5981` records the standard mapping and keeps the decision Proposed.

Current localization invariants:

- explicit persisted/session locale rejects C0 controls and DEL before normalization; only ASCII SP is benign outer whitespace;
- `Accept-Language` rejects C0/DEL except HTAB in valid RFC 9110 OWS positions; protocol OWS is exactly SP/HTAB;
- `q=` and `Q=` are equivalent quality-parameter spellings; qvalue syntax and range remain strict;
- list recipients ignore a reasonable number of empty comma members rather than treating them as syntax errors or preference values; an all-empty list contributes no negotiated preference;
- `product_default` is runtime-validated as a string before supported-locale set membership, so malformed/unhashable values fail with `ui_locale_unsupported` instead of raw Python exceptions;
- translated catalog text rejects U+0000 and U+D800–U+DFFF before placeholder parsing with `ui_translation_input_invalid`; ordinary valid Unicode, line breaks and tabs remain valid copy;
- placeholder schemas are tuple/list runtime collections of unique lowercase names; arbitrary containers fail closed and elements are validated before hash-based uniqueness;
- once a locale is selected, missing active translation keys must fail rather than silently fall back per message;
- UI-copy resources remain separate from ontology/concept-label authority.

The tenth repair has executable regression source, but **no local/container PASS is claimed** because the current execution environment does not contain the repository checkout needed for exact-head execution. Immediately after exact doctoring `8450a94d...`, the exact-head pull-request workflow inventory was empty and formal review inventory was `[]`; workflow/review state remains volatile and must be read fresh before acceptance. The baseline claims no terminal GREEN and no qualifying independent post-last-push review. No predecessor receipt transfer or source-neutral wake commit is permitted.

Persistence remains blocked until #1503 or a verified complete successor reaches protected ancestry. Then localization storage must create the next ordinary single-head Alembic descendant, use normalized 3NF resources, immutable published versions, translation-text/placeholder/completeness validation, short aggregate publication transactions, screen-scoped reads with ETag/version identity and no whole-catalog browser hydration.

Buyer UI acceptance remains required for KO/EN/JA/ZH/VI/ES/DE/FR across normal/loading/empty/error/permission states, CJK wrapping/font fallback, Latin-script expansion/diacritics, keyboard/focus/touch/AT, responsive widths and exact-version screenshots. #1729 remains the bounded OIDC pending-interaction owner and may consume localization only after a released screen-resource contract exists.

## 5. Other buyer-visible UI and generated-writer boundaries

#1682 remains the Calendar buyer-truth/detail-sidebar owner. #1463 remains the Tasks async-loading owner; generated #1735 is provenance. #1676 remains Settings native-disabled semantics owner; generated #1737 is provenance. #1354 remains the design-token precursor and #1436 the executable Storybook/runtime lineage; dependency/lock security stays with #1623.

Generated #1738 remains zero-effective-delta provenance because its predecessor fabricated participant/attachment data, exposed a dead CTA and supplied static/unmounted mobile panels without authoritative state. Any valid density/mobile intent must be rebuilt through canonical mail/thread/attachment/calendar/mobile owners with actual data and lifecycle/browser/a11y evidence.

Generated descendants are re-read every run. When they duplicate an existing owner or delete/weaken tests, fixtures, traceability, dependency floors, buyer truth or security boundaries, repair is ordinary/non-force adoption/restack. Do not close useful history merely because effective delta becomes zero; keep provenance until the canonical owner integrates or a verified complete successor inherits all valid source/test/evidence.

## 6. LLM/released-contract boundary

#1548/#1549 remain Naruon's LLM-governance owner path. `ContextualWisdomLab/contextual-orchestrator` protected `main` remains exact `5665b0ad1e07ffb5e9f8c59e44b6b2a785298013`; GitHub Releases inventory is exactly `[]`. Naruon therefore has no immutable released CO API/client/schema identity to consume and remains fail-closed. Mutable owner head, copied provider routing or direct provider/model hard-coding is not an acceptable substitute.

## 7. Current causal order

The current minimum causal sequence is:

`.github#712` stable runner acquisition → `.github#1911/#2040` legitimate terminal acceptance → **`.github#2291` complete 24-specialized-fixture trusted-runtime repair, exact-head GREEN/review/hosted acceptance** → #2109/#2272 ordinary adoption → #2271/#2275/#2276 → #1623 current vulnerability revalidation → #1694 → #1691 repository-local stacked admission → #1593 `0eb4b6dc...` exact-owner acceptance with #1742 provenance following it → #1628/#1674/#1675 and generated provenance convergence → #1361/#1739 → #1565/#1685 → #1733 → #1503 → #1727 `2ac48fb7...` with #1743 zero-delta provenance → localization migration lineage → #1740 `8450a94d...` exact pure-policy acceptance → localization persistence/API/cache after #1503 protected ancestry → immutable contextual-orchestrator release + #1549 → #1729 and eight-locale rendered UI → #1463/#1676 and authoritative #1738 intent → #1354/#1436 Storybook/runtime acceptance → one exact protected integrated candidate → immutable Naruon release with SBOM/provenance/reproducibility/rollback`.

Review/check waiting blocks only the affected lane. Any genuine failure is RCA/fix/retest work, not a reason to weaken a gate. No force push, destructive rebase, self-approval, administrator bypass, source-neutral wake commit, blind rerun, mutable sibling dependency, cross-service SQL, duplicate canonical owner, parallel Alembic head, fabricated buyer-visible content, dead CTA, synthetic status or predecessor-evidence transfer is accepted.
