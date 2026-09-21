# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.53  
**Observed on:** 2026-09-21 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

v2.52 remains audit-visible as blob `7ec571a4593547ae23ddfa815f27f4148f565681`; v2.51 remains blob `0d60c3296e3e5d29fea9749effd2fa43dc61aed1`; v2.50 remains blob `e6faf4e0b6d507d6a62e3b96c8583ff7c912cab3`; earlier snapshots remain reconstructable from Git history and `docs/product-technical-gap-history/`. Historical snapshots and predecessor workflow/review receipts are audit material, not current merge or release authority.

v2.53 preserves v2.52's owner graph, #1745 zero-effective-delta performance correction, localization resource ceilings and registry-independent RFC 5646 repairs. The durable change is the twenty-third UI-localization RED→repair on #1740: RFC 4647 wildcard-only lookup no longer fabricates `selection_source=accept_language` when the selected locale is actually the configured product default. RED `deaf07941cfc2b607c2148f434ce1196a3db29d9`, causal fix `1ce7b6ed5883beda305ea2552ae5af00509510c7` and doctoring/current exact head `d48e9e6f91d922e6b0dbf7497832836254c29eb9` make the selected locale and its authority provenance agree.

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

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the canonical frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`, Draft/open. Historical exact-head GREEN does not prove safety against the current vulnerability database; current Trivy/CodeQL revalidation belongs here rather than in feature PRs.

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the bounded Starlette TestClient/httpx2 owner. [#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) remains the broader backend dependency descendant and must reconcile losslessly onto #1565 with one resolver-produced lock graph. [#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) remains the bounded provider-error confidentiality owner; inherited dependency Security RED is routed to #1623.

### 3.2 Migration/workspace and opaque UID ownership

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the sole workspace/Alembic/bootstrap owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`, stacked on #1565. Canonical migration lineage remains:

`0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`.

#1503 is Draft. Descendants must not create parallel Alembic heads from protected `develop`.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains the canonical opaque-UID backfill entropy owner on #1503 at exact `2ac48fb7e591827804ba8e7e911f211b0c134ddf`. It owns the bounded `random()` → `gen_random_uuid()` repair for missing public UIDs, focused entropy regression, corrected Bandit/severity diagnosis and doctoring/TRACEABILITY. Opaque identity is defense in depth, not authorization. Generated #1743 is ordinary/non-force converged to #1727 and remains Draft zero-effective-delta provenance.

### 3.3 NetworkGraph/performance

[#1593](https://github.com/ContextualWisdomLab/naruon/pull/1593) remains the canonical bounded relationship/node option owner at exact `0eb4b6dc5264db8568fd2a54adde9a91feb3cece`, based on #1623. Its effective scope is `NetworkGraph.tsx` plus `NetworkGraph.bounded-options.test.tsx`; unrelated dependency/security drift has been repaired ordinary-forward while retained in ancestry.

[#1628](https://github.com/ContextualWisdomLab/naruon/pull/1628) remains the first-five non-empty label-summary child; #1674 remains zero-effective-delta provenance and #1675 remains memoization owner. Generated #1742 is ordinary/non-force converged to #1593 and remains zero-effective-delta provenance. Generated NetworkGraph descendants must follow current canonical owner ancestry rather than reimplement or inherit stale evidence.

### 3.4 Checksum/data hygiene

Issue #1247 remains the checksum contract. Normal security-labelled checksum surface is SHA-256, SHA-3-256 and BLAKE2b-256 only; MD5/SHA-1 remain outside the normal surface. #1361 remains the canonical `content_checksum_generator` owner; generated #1739 remains provenance.

### 3.5 Settings native-disabled accessibility

[#1676](https://github.com/ContextualWisdomLab/naruon/pull/1676) remains the sole Settings native-disabled semantics owner at exact `8a3ac51662fbe8e49f26a317ac0afe85f853c9ac`, stacked on #1623. Its bounded product tree owns the source removals, focused `SettingsLayout.native-disabled.test.tsx` regression and standards doctoring; browser/keyboard/responsive acceptance remains a separate delivery gate.

Generated #1716, #1737 and #1744 are provenance only. #1744 ordinary convergence `e50d25580a3fa840b14855661e215a3368d8a73d` preserves generated history while adopting exact #1676, retargeting to that owner and leaving zero effective product delta. It must not independently merge or broaden the narrow native-control decision into a repository-wide ban on `aria-disabled`.

### 3.6 AI Hub run-history rendering performance

Generated [#1745](https://github.com/ContextualWisdomLab/naruon/pull/1745) remains Draft zero-effective-delta provenance at exact `a501ca663e01a53b3c60a1264a6e014ad0228c64`. Fresh compare from protected `develop` is ahead-only with zero changed files; the current tree is exactly protected tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`.

The generated predecessor `5cdebe154f1ea24b0f924769d0073c4dc701e7d6` wrapped `RunHistoryPanel`'s mapped event subtree in `useMemo([events])`, added task-specific `.jules/bolt.md` doctrine and asserted that potentially large event arrays justified the optimization. Canonical backend review disproved that premise for the current product surface: `_list_agent_run_records(...).limit(8)` feeds primary `run_events`; fallback audit events are also bounded to eight and prompt fallback to five. No current browser profile, React render/commit timing, reference-stability evidence or buyer-path p95 receipt identifies mapping at most eight run rows as a material bottleneck.

Ordinary convergence `a501ca66...` preserves the generated commit as first-parent history, adopts protected `develop` as an additional parent and restores the protected product tree without force rewrite. The generated performance claim remains auditable but is not product progress. Any future RunHistory performance owner starts from reproduced buyer-path evidence on the bounded backend contract.

## 4. UI Localization Catalog — v2.53 material contract

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single buyer-visible **UI Localization Catalog** Gap. Draft [#1740](https://github.com/ContextualWisdomLab/naruon/pull/1740) is the first bounded executable owner at exact **`d48e9e6f91d922e6b0dbf7497832836254c29eb9`**. Current source repairs are present; exact-current-head hosted acceptance is pending.

#1740 owns pure domain policy only: KO/EN/JA/ZH/VI/ES/DE/FR release locale identity, persisted → session → weighted `Accept-Language` → product-default precedence, bounded locale/header parsing, bounded stable screen/message identities, bounded persistable translation text, bounded exact simple named-placeholder schemas and typed boundary failures. It owns no database/Alembic revision, HTTP API, browser cache/runtime, Storybook page, authoring UI, ontology-label authority or LLM translation path.

Twenty-three ordinary-forward RED→repair sequences now define the current source policy. Durable/current invariants are:

1. explicit persisted/session locale rejects C0 controls and DEL before normalization; only ASCII SP is benign outer whitespace;
2. explicit locale input is capped at **128 characters** and rejected above the limit without truncation;
3. RED `478bd95fdbd2b6601fae1ab70c3513abf0f985fe` and fix `3a87209306ad1b3dee67cb9e0e9e513dfb7a4f3a` reject malformed terminal private-use/extension singletons such as `en-x` and `en-u` while retaining `en-x-private` and `en-u-ca-gregory`;
4. RFC 5646 `Language-Tag` is `langtag / privateuse / grandfathered`. RED `8d9a0f67a47b26eb1e36a7bc65681470033c6f74` and fix `aceef1b282d948411fe9b04b8cd08750fcdacfe8` preserve supported-primary grandfathered `en-GB-oed → en`, `zh-min → zh`, and `zh-min-nan → zh`;
5. RED `d23d4095d1c2ac8542f1ac247b6fee87fcb9485c` and fix `dc077bec9ae47e1421fa678ae43451f65784c410` separate language-tag syntax from eight-locale product support: private-use-only `x-private` and irregular grandfathered `i-klingon` / `sgn-BE-FR` are well-formed but unsupported;
6. RED `da7e2653a158a259f4d327f1cf017674c7721064` and fix `81e061c000a13261ced87b7d6f71fbce64637821` enforce RFC 5646 §2.2.6 extension-singleton uniqueness before private use;
7. RED `c34b45957799575ea7e11c84992fdf84461b783f` and fix `96adc96dd5fab6e31734c2c23257b0f0f40447ee` reject duplicate variants case-insensitively before extensions/private use while allowing the same spelling inside private use;
8. RED `c49c80904ae1c38ee529a4b65e2fdb6612863c47` and fix `983194dd129cc593a4caa3c8531fb669986e4262` reject RFC 5646's permanently reserved second/third extlang positions while retaining one-extlang structural forms;
9. those structural checks do not create a moving registry dependency. Full BCP 47 registry membership, variant `Prefix`, preferred values and canonicalization require a dated IANA registry/version/update/provenance contract;
10. `Accept-Language` remains a separate RFC 4647 basic-language-range boundary; persisted/session language-tag validation and HTTP language-range validation are not interchangeable;
11. `Accept-Language` rejects C0/DEL except HTAB where HTTP OWS permits it; protocol OWS is SP/HTAB rather than Python generic whitespace;
12. raw `Accept-Language` is capped at **8192 characters** before list/regex work and processes at most **64 non-empty language ranges**;
13. `q=` and `Q=` are equivalent parameter-name spellings while qvalue syntax/range remains strict;
14. RFC 9110 list-recipient semantics ignore at most **32 empty comma members** under Naruon's product bound and reject the 33rd;
15. runtime `product_default` is type-validated before set membership so arbitrary Python hashability cannot leak as product semantics;
16. RFC 4647 lookup preserves later positive concrete ranges even when unsupported. `*;q=0.9, pt-BR;q=0.8` skips `*`, fails to match Portuguese to release resources and reaches `(ko, product_default)` rather than falsely attributing the same locale to `accept_language`;
17. twenty-third RED `deaf07941cfc2b607c2148f434ce1196a3db29d9` and fix `1ce7b6ed5883beda305ea2552ae5af00509510c7` close the symmetric wildcard-only provenance defect: `*;q=0.9` resolves `(ko, product_default)`, and with `product_default="fr"` resolves `(fr, product_default)`. A supported q=0 exclusion still changes the candidate set, so `ko;q=0, *;q=0.8` may truthfully remain header-dependent and select `(en, accept_language)`;
18. `screen_key` and `message_key` are capped at **128 characters** before regex acceptance; over-limit identities are rejected and never truncated;
19. translated catalog text rejects U+0000, isolated surrogate code points and non-string input before placeholder parsing/persistence and is capped at **16,384 Python characters**;
20. `placeholder_schema` is tuple/list only, validates element type/syntax before uniqueness, caps one name at **64 characters** and one message/schema at **32 unique names**, and direct extraction enforces the same 32-name ceiling;
21. placeholder source syntax is canonical before parser normalization. `{account_name}` is valid; `{account_name:}`, conversions, traversal and format specifications are invalid publication input even where Python would render an equivalent visible value;
22. all negotiation/key/content ceilings are Naruon product resource contracts layered over standards/storage boundaries. Over-limit values fail closed and no truncation is permitted;
23. source correctness does not transfer predecessor hosted evidence. Exact `d48e9e6f...` still requires fresh full-suite/coverage/security and qualifying independent post-last-push review before policy acceptance.

RFC 4647 §3.4 says `*` cannot identify a best matching tag; if it is the only range or no range follows, the default value is computed. §3.4.1 requires the application to define that defaulting behavior. RFC 9110 §5.4 allows recipients to refuse field values larger than they are willing to process and does not set one universal field-size ceiling. RFC 4647 §4.4 permits range-length restrictions comparable to tag restrictions; RFC 5646 §4.4.1 permits documented implementation limits. Naruon's 128/8192/64/32 negotiation bounds, 128/128 key ceilings and 16,384/64/32 translation/placeholder ceilings are explicit application resource contracts.

No predecessor workflow/review receipt transfers to current #1740 exact `d48e9e6f...`. The RED, source repair and doctoring are present, but exact-head hosted checks and independent review must become terminal and qualifying before merge.

### Localization persistence/API/UI order

Translation persistence must wait until #1503 or a verified complete successor reaches protected ancestry and until #1740 exact-current-head policy acceptance, then create the next ordinary Alembic descendant from the then-current single head. Published catalog versions are immutable, complete for all eight release locales, placeholder/text validated before publication and rollback-selectable without rewriting history. Persistence and API boundaries must preserve the repaired explicit-locale syntax/support/registry-independent validity contract, truthful wildcard/default provenance, the 128/128 key ceiling, the 128/8192/64/32 negotiation contract and the 16,384/64/32 translation/placeholder contract without truncation.

A screen-scoped read contract returns only the requested screen/locale with immutable resource version and ETag/cache identity. The HTTP owner must preserve parser/content resource contracts and reject over-limit negotiation/content before buyer-path work; realistic k6/E2E must measure normal, exact-boundary and over-limit behavior. Do not ship a browser-wide mega-catalog, per-key network waterfall or heavy SPA i18n dependency by default. UI-copy authority remains separate from ontology/concept labels.

KO/EN/JA/ZH/VI/ES/DE/FR acceptance requires Storybook plus real-browser E2E for normal/loading/empty/error/permission states, keyboard/focus/screen-reader/touch semantics, CJK wrapping/font fallback, Vietnamese diacritics, DE/FR/ES text expansion, mobile/intermediate widths and exact resource-version/source-head screenshots.

## 5. Contextual Orchestrator and LLM boundary

All Naruon LLM behavior must consume an immutable released contextual-orchestrator API/client/schema contract. No mutable owner head, source copy, provider group hard-code or direct provider fallback is acceptable. Until contextual-orchestrator has a canonical release identity satisfying the product contract, dependent Naruon work such as #1549 remains fail-closed. Model-backed GitHub Actions must use the central `orchestrator/free` contract and gateway token only.

## 6. Remaining commercial/buyer-visible gaps

The current causal order remains:

`.github#712` stable runner acquisition → #1911/#2040 legitimate terminal acceptance → #2291 complete 24-specialized-fixture trusted-runtime repair → #2109/#2272 → #2271/#2275/#2276 → #1623 current-vulnerability revalidation → #1694 fresh-bootstrap Alembic repair → #1691 repository-local stacked admission → #1593 → #1628/#1674/#1675 → checksum/backend dependency owners → #1676 Settings native-disabled owner + zero-delta generated provenance → #1503 → #1727 plus zero-delta provenance → #1740 `d48e9e6f...` exact-head policy acceptance → localization persistence/API/cache preserving repaired explicit-locale syntax/support/registry-independent validity and truthful wildcard/default provenance, 128/128 key, 128/8192/64/32 negotiation and 16,384/64/32 translation/placeholder contracts → immutable contextual-orchestrator release + #1549 → #1729 and eight-locale rendered UI → Tasks/Settings and authoritative #1738 intent through their canonical owners → Storybook owners → exact protected integrated candidate → immutable Naruon release with SBOM/provenance/reproducibility/rollback.`

#1745 is not an active causal blocker. It retains generated performance intent as zero-effective-delta provenance only. Any future RunHistory performance owner must start from reproduced buyer-path evidence rather than the rejected memoization.

Wait state in one lane does not stop repair/development in independent lanes. Generated descendants remain open as provenance unless a verified successor fully inherits all valid delta/test/fixture/contract/evidence or the user explicitly authorizes closure.

## 7. Delivery gates

**Merge/Release Gate: FAIL.** There is no exact protected integrated candidate satisfying required checks, current security evidence, independent post-last-push review and immutable release evidence.

**UI Delivery Gate: FAIL.** The localization pure-policy source repairs are present, but exact-current-head acceptance is pending and eight-locale catalog persistence/API/page composition, Storybook/browser/a11y acceptance and current exact resource-version evidence are not integrated. #1745's generated memoization remains outside effective product scope rather than counted as UI/performance progress.

Do not claim completion from routine reporting, queued checks, historical GREEN, mutable release artifacts, generated-provenance branches, unmeasured memoization, source-only correctness, malformed-versus-unsupported locale collapse, wildcard provenance fabrication, repeated extension singletons, duplicate variants, reserved multi-extlang occupancy or unresolved exact-head acceptance evidence. The next run must fresh-read all live authority before mutating or accepting any lane.
