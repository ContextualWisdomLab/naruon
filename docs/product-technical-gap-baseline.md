# Naruon Product and Technical Gap Baseline

**Baseline version:** 2.55  
**Observed on:** 2026-09-21 (Asia/Seoul)  
**Protected product authority:** `develop@042b0c70531b229af3acbd0421a2f23098d848b3` / tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`  
**Observed product version:** `0.14.4`  
**Canonical completion issue:** [#1428](https://github.com/ContextualWisdomLab/naruon/issues/1428)  
**Canonical Gap-ledger writer:** [#1602](https://github.com/ContextualWisdomLab/naruon/pull/1602)

v2.54 remains audit-visible as blob `ccf12a55634e88fb1cd52caea4f1cb4d7c645f3e`; v2.53 remains blob `0eeb08e6a75a819e89adbf2d08e6c83a3909a26b`; v2.52 remains blob `7ec571a4593547ae23ddfa815f27f4148f565681`; earlier snapshots remain reconstructable from Git history and `docs/product-technical-gap-history/`. Historical snapshots and predecessor workflow/review receipts are audit material, not current merge or release authority.

v2.55 preserves v2.54's owner graph, #1740 twenty-third RFC 4647 wildcard/default provenance repair and #1746 generated-tool overlap correction. The durable addition is the dependency-update grouping repair now owned by Draft #1752. Protected `.github/dependabot.yml` grouped all backend Python, root CI Python and frontend npm version changes with wildcard `patterns: ["*"]` and no SemVer bound. The policy reproduced direct-to-`develop` generated PRs #1749 (76 backend updates), #1750 (19 frontend updates) and #1751 (104 root/CI updates), coupling security-material changes and unrelated compatibility migrations across existing canonical owners. #1752 exact `70d315da85be046d1d0f24a2ded861cd44e2bb69` adds an executable RED and a minimal prospective fix: those three wildcard groups are version-update patch-only; backend `aiosmtplib` is excluded for independent security review; major/minor updates remain visible as separate Dependabot PRs rather than being disabled. Existing generated PRs remain provenance/migration lanes and must still reconcile through their canonical owners.

## 1. Evidence hierarchy and release posture

Evidence authority is: exact protected code/migrations/tests/runtime contracts → protected architecture/operations docs → exact current PR source and current-head evidence → live Issue/Proposed ADR authority → historical snapshots. Pending, queued, cancelled, stale, predecessor-head, skipped-required, source-neutral, author-only, local-only, or model-only evidence is not passing evidence.

Protected `develop` is `042b0c70531b229af3acbd0421a2f23098d848b3`, tree `8fde14381aaa430eeaaf61151dab6f6800127cd3`, with 17 required status contexts. Active rulesets, PR/Issue inventory, owner heads and releases must be re-read before acceptance; volatile queue telemetry is never frozen into this baseline.

Latest Naruon GitHub Release remains `v0.14.4`, published 2026-06-19, with `immutable=false`. It is historical publication evidence only. A commercial candidate requires one exact protected integrated head with terminal required contexts, current security evidence, zero valid unresolved review findings, qualifying independent post-last-push review, immutable publication identity, SBOM/provenance, reproducibility, rollback and buyer-visible acceptance for changed behavior.

**Merge/Release Gate: FAIL. UI Delivery Gate: FAIL.**

## 2. Central CI/security control plane

Protected `ContextualWisdomLab/.github/main` owns reusable CI/review/security/release workflows. Naruon consumes canonical owner contracts and does not copy central workflow source.

- `.github#712` owns Actions execution capacity. Queued current-head evidence remains incomplete; blind rerun, source-neutral wake commits and required-check weakening are prohibited.
- `.github#1911` owns repository-wide/full-suite Trusted-uv acceptance; legitimate terminal hosted evidence is required.
- `.github#2040` consumes #1911 and retains its distinct CodeQL scheduler/credential/runtime-quality scope.
- `.github#2291` remains source RED until every one of the 24 specialized Strix fixture families stops materializing trusted binder/runtime into the consumer root. Acceptance requires a non-consumer trusted runtime, absolute trusted-gate invocation with explicit `STRIX_REPO_ROOT`, binder-free consumer roots, preserved scenario assertions and exact-head hosted/review evidence.
- `.github#2109` is the stacked-admission successor and must ordinary/non-force adopt repaired #2291. `.github#2272` remains its separate Pages/SAST descendant. `.github#2271/#2275/#2276` retain repository-identity, GHAS analysis-capability and real target permission/canary boundaries.

No Naruon lane may reinterpret incomplete central hosted evidence as GREEN.

## 3. Product source-owner graph

### 3.1 Dependency/security

[#1623](https://github.com/ContextualWisdomLab/naruon/pull/1623) remains the canonical frontend dependency-security owner at exact `509be4c1d9b6c7ba239a108656e2382681a85341`, Draft/open. Current vulnerability-database revalidation belongs there rather than in feature PRs. Generated #1750 is now Draft and retargeted onto #1623 because it changes the same `frontend/package.json`/`pnpm-lock.yaml` surface; its Next.js `16.3.5` successor intent and React/Vitest/Playwright/other compatibility migrations must be reconciled ordinary/non-force above the security owner rather than accepted as one direct-to-`develop` group.

[#1565](https://github.com/ContextualWisdomLab/naruon/pull/1565) remains the bounded Starlette TestClient/httpx2 owner at exact `52dfc863d1a5d6e4e80b6366f719dd09f2aa6172`. Auto-closed predecessor [#1685](https://github.com/ContextualWisdomLab/naruon/pull/1685) is audit lineage, not proof of complete succession. Generated #1749 is the current broad backend update lane, has been restored to Draft and retargeted onto #1565. It must preserve #1565's direct `httpx2`, warnings-as-errors runtime proof and one coherent `pyproject.toml` / plain requirements / hashed requirements / `uv.lock` graph while retaining independent verification of security-material `aiosmtplib==5.1.3`. Its current generated four-file delta lacks #1565's `backend/uv.lock` owner delta and is therefore not yet a valid reconciled descendant. [#1733](https://github.com/ContextualWisdomLab/naruon/pull/1733) retains provider-error confidentiality scope; inherited dependency Security RED routes to #1623.

Generated #1751 is Draft provenance for the reproduced cross-boundary `ci-python` mega-group. It spans backend, connector, root CI/Strix and provider/model-client requirement inputs, so there is deliberately no synthetic single owner to retarget it onto. Strix behavior remains with canonical central `.github` owners; connector runtime/version intent must route through its connector dependency/release owner; backend intent must not compete with #1565/#1749; model/provider client bumps do not alter Naruon's immutable released contextual-orchestrator authority.

Draft [#1752](https://github.com/ContextualWisdomLab/naruon/pull/1752) at exact `70d315da85be046d1d0f24a2ded861cd44e2bb69` is the sole Naruon owner for the grouping-policy defect. RED `9935b1d6140a20cb54300810290e5769d576cf1a` asserts explicit version-update scope, patch-only wildcard groups and independent backend `aiosmtplib` treatment. Causal fix `c27a8c0ef391845393b1a87b0fe4bed361bdf569` changes only `backend-python`, `ci-python` and `frontend-npm`; it does not edit current generated locks, disable major/minor updates, copy central workflow source or weaken security/review gates. Exact-head hosted acceptance, independent review and a later Dependabot-cycle operational check remain required.

### 3.2 Migration/workspace and opaque UID ownership

[#1503](https://github.com/ContextualWisdomLab/naruon/pull/1503) remains the sole workspace/Alembic/bootstrap owner at exact `9151c75568c582c8147cfee6757cd00a9b4d60b7`, stacked on #1565. Canonical migration lineage is `0018_workspace_registry → 0019_email_read_state_repair → 0020_workspace_organization_binding → 0021_workspace_personal_owner_binding`. Descendants must not create parallel Alembic heads from protected `develop`.

[#1727](https://github.com/ContextualWisdomLab/naruon/pull/1727) remains the canonical opaque-UID backfill entropy owner on #1503 at exact `2ac48fb7e591827804ba8e7e911f211b0c134ddf`. Generated #1743 is zero-effective-delta provenance. Opaque identity remains defense in depth, not authorization.

### 3.3 NetworkGraph/performance

[#1593](https://github.com/ContextualWisdomLab/naruon/pull/1593) remains the canonical bounded relationship/node option owner at exact `0eb4b6dc5264db8568fd2a54adde9a91feb3cece`, based on #1623. #1628 remains its first-five non-empty label-summary child; #1674 is provenance and #1675 is the memoization owner. Generated #1742 is zero-effective-delta provenance after ordinary convergence.

### 3.4 Data-hygiene/checksum/URL ownership

Issue [#1247](https://github.com/ContextualWisdomLab/naruon/issues/1247) is the auditable data-hygiene product contract.

- [#1361](https://github.com/ContextualWisdomLab/naruon/pull/1361) is the canonical `content_checksum_generator` owner at exact `6bf2989d571a2aa94ce1f92997650cc450e88e9d`, stacked on #1623. Normal security-labelled algorithms are exactly SHA-256, SHA-3-256 and BLAKE2b-256. MD5/SHA-1 are outside the normal surface. #1361 also owns exact UTF-8 byte semantics, 1 MiB byte ceiling, stable invalid-UTF-8 failure, known-answer/chunk-equivalence tests, ADR/doctoring and the explicit statement that an unkeyed digest is not sender authentication.
- [#1418](https://github.com/ContextualWisdomLab/naruon/pull/1418) is the canonical URL/contact hygiene owner at exact `87a94a4c2b78f12a61ec699dee9ce081ea3d8578`. `url_evidence_extractor` preserves raw/normalized values, source offsets and repeated occurrences, parses bounded absolute HTTP(S) candidates, handles userinfo/IDNA/IPv6/percent encoding and carries warnings without fetching or DNS resolution. It also owns the bounded contact-data redaction slice.
- Generated #1739 and earlier generated checksum descendants remain provenance only where their useful delta is inherited by #1361.
- Generated [#1746](https://github.com/ContextualWisdomLab/naruon/pull/1746) is Draft zero-effective-delta provenance at exact `167b32ec7077ff11e1d3e81c43a2205433a2bbd7`. Its predecessor exposed MD5/SHA-1 under security-labelled `hash_generator` and introduced an unbounded regex-only `url_extractor`. Both violate #1247/canonical-owner contracts. Ordinary two-parent convergence preserves generated history while restoring exact protected tree; fresh protected-base compare is ahead 2 / behind 0 / zero changed files. It is not a second checksum or URL owner and must not independently merge as product progress.

### 3.5 Settings native-disabled accessibility

[#1676](https://github.com/ContextualWisdomLab/naruon/pull/1676) remains the sole Settings native-disabled semantics owner at exact `8a3ac51662fbe8e49f26a317ac0afe85f853c9ac`, stacked on #1623. Generated #1716, #1737 and #1744 are provenance only; #1744 ordinary convergence `e50d25580a3fa840b14855661e215a3368d8a73d` has zero effective delta. Browser/keyboard/responsive acceptance remains a separate delivery gate.

### 3.6 AI Hub run-history rendering performance

Generated [#1745](https://github.com/ContextualWisdomLab/naruon/pull/1745) is Draft zero-effective-delta provenance at exact `a501ca663e01a53b3c60a1264a6e014ad0228c64`. Its generated `useMemo([events])` premise was rejected because canonical `/api/ai-hub/surface` bounds primary run events to eight, fallback audit events to eight and prompt fallback to five, while no current browser profile, render/commit timing, reference-stability evidence or buyer-path p95 identifies that bounded map as causal. Future performance work must start from reproduced buyer-path evidence.

## 4. UI Localization Catalog — v2.55 material contract

[#1731](https://github.com/ContextualWisdomLab/naruon/issues/1731) remains the single buyer-visible **UI Localization Catalog** Gap. Draft [#1740](https://github.com/ContextualWisdomLab/naruon/pull/1740) is the first bounded executable owner at exact `d48e9e6f91d922e6b0dbf7497832836254c29eb9`. It owns pure localization domain policy only and no persistence, Alembic migration, HTTP API, browser cache/runtime, Storybook, authoring UI, ontology-label authority or LLM translation path.

Twenty-three ordinary-forward RED→repair sequences define the current policy. Durable invariants are:

1. release locales are exactly KO/EN/JA/ZH/VI/ES/DE/FR;
2. explicit persisted/session locale rejects C0/DEL before normalization, permits ASCII SP as the benign outer whitespace, and is capped at 128 characters without truncation;
3. malformed terminal singleton forms such as `en-x` and `en-u` are rejected while `en-x-private` and `en-u-ca-gregory` are retained;
4. supported-primary grandfathered `en-GB-oed`, `zh-min`, and `zh-min-nan` are retained; private-use-only and irregular-grandfathered syntax is separated from eight-locale support;
5. registry-independent RFC 5646 validity rejects repeated extension singletons, duplicate variants and permanently reserved second/third extlang occupancy while leaving live registry membership/prefix/preferred-value/canonicalization to a dated IANA-registry contract;
6. `Accept-Language` is a separate RFC 4647 basic-language-range boundary, rejects C0/DEL except HTAB as HTTP OWS, uses SP/HTAB rather than Python generic whitespace, caps raw input at 8192 characters, handles at most 64 non-empty ranges and at most 32 empty list members, and treats `q=`/`Q=` equivalently while retaining strict qvalue syntax;
7. runtime `product_default` is type-validated before set membership;
8. lookup preserves later positive concrete ranges even when unsupported. `*;q=0.9, pt-BR;q=0.8` skips `*`, fails Portuguese against release resources and reaches `(ko, product_default)`;
9. twenty-third RED `deaf07941cfc2b607c2148f434ce1196a3db29d9` and fix `1ce7b6ed5883beda305ea2552ae5af00509510c7` close wildcard-only provenance: `*;q=0.9` resolves `(ko, product_default)`, and with `product_default="fr"` resolves `(fr, product_default)`. Supported q=0 exclusion remains header-dependent, so `ko;q=0, *;q=0.8` may select `(en, accept_language)`;
10. `screen_key` and `message_key` are each capped at 128 characters before regex acceptance and are never truncated;
11. translated text rejects U+0000, isolated surrogates and non-string input and is capped at 16,384 Python characters;
12. placeholder schema is tuple/list only, validates elements before uniqueness, caps names at 64 characters and a message/schema at 32 unique names, and direct extraction enforces the same 32-name ceiling;
13. canonical source syntax accepts `{name}` only; empty/non-empty format specifiers, conversions and traversal are publication-invalid even where Python could render equivalent visible text;
14. all parser/key/content ceilings are Naruon application resource contracts layered over standards/storage boundaries; over-limit values fail closed and no identity/content truncation is permitted;
15. predecessor workflow/review receipts do not transfer. Exact `d48e9e6f...` still requires current full-suite/coverage/security and qualifying independent post-last-push review before policy acceptance.

RFC 4647 §3.4 states that `*` cannot identify a best matching tag and defaulting is computed when `*` is the only effective range or no later range follows; §3.4.1 requires the application to define default behavior. The doctoring on exact #1740 records this alongside RFC 9110/5646 resource-boundary reasoning.

### Localization persistence/API/UI order

Translation persistence waits until #1503 or a verified complete successor reaches protected ancestry and #1740 exact-current-head policy acceptance. The next persistence owner must create one ordinary Alembic descendant from the then-current single head, publish immutable complete eight-locale resource versions, preserve exact placeholder/text validation and truthful wildcard/default provenance, and retain the 128/128 key, 128/8192/64/32 negotiation and 16,384/64/32 translation/placeholder contracts without truncation.

The read API is screen-scoped with immutable resource version plus ETag/cache identity; no browser-wide mega-catalog, per-key network waterfall, heavy browser i18n default or cross-service SQL. Realistic k6/E2E must cover normal, exact-boundary and over-limit behavior. KO/EN/JA/ZH/VI/ES/DE/FR UI acceptance requires Storybook plus real browser E2E across normal/loading/empty/error/permission states, keyboard/focus/screen-reader/touch, CJK wrapping/font fallback, Vietnamese diacritics, DE/FR/ES expansion, mobile/intermediate widths and exact resource-version/source-head screenshots.

## 5. Contextual Orchestrator and LLM boundary

All Naruon LLM behavior consumes an immutable released contextual-orchestrator API/client/schema contract. Mutable owner heads, source copy, provider-group hard-codes and direct provider fallback are not accepted. Until contextual-orchestrator has the required canonical immutable release identity, dependent Naruon work such as #1549 remains fail-closed. Model-backed GitHub Actions use central `orchestrator/free` and gateway token only.

## 6. Current causal order and buyer-visible gaps

`.github#712` stable runner acquisition → #1911/#2040 legitimate terminal acceptance → #2291 complete 24-specialized-fixture trusted-runtime repair → #2109/#2272 → #2271/#2275/#2276 → #1752 bounded dependency-update grouping acceptance → #1623 current-vulnerability revalidation + generated #1750 owner reconciliation → #1565 exact dependency/TestClient acceptance + generated #1749 reconciliation → bounded successors of generated #1751 through their canonical owners → #1694 fresh-bootstrap Alembic repair → #1691 repository-local stacked admission → #1593 and canonical NetworkGraph descendants → canonical data-hygiene/checksum owners (#1361/#1418; generated #1746 is provenance only) → #1676 Settings native-disabled owner + generated provenance → #1503 → #1727 + generated provenance → #1740 `d48e9e6f...` exact-head policy acceptance → localization persistence/API/cache preserving repaired locale and wildcard/default provenance contracts → immutable contextual-orchestrator release + #1549 → #1729/eight-locale rendered UI → Tasks/Settings and authoritative #1738 intent through canonical owners → Storybook/browser/a11y owners → exact protected integrated candidate → immutable Naruon release with SBOM/provenance/reproducibility/rollback.

#1745 and #1746 are not active causal blockers; both preserve rejected/generated intent as zero-effective-delta provenance. #1749/#1750/#1751 remain open generated migration/provenance lanes until bounded owner descendants completely inherit their valid version intents, lock/test/fixture/contract/evidence deltas. Wait state in one lane does not stop repair/development in independent lanes. Generated descendants remain open unless a verified successor completely inherits every valid delta/test/fixture/contract/evidence or the user explicitly authorizes closure.

## 7. Delivery gates

**Merge/Release Gate: FAIL.** No exact protected integrated candidate currently satisfies required checks, current security evidence, qualifying independent post-last-push review and immutable release evidence.

**UI Delivery Gate: FAIL.** Localization pure-policy repairs are present, but exact-current-head acceptance and eight-locale persistence/API/page composition, Storybook/browser/a11y and exact resource-version evidence are not integrated.

**Dependency-update ownership gate: FAIL for generated #1749/#1750/#1751; repair present in #1752.** The reproduced wildcard mega-group policy now has an executable RED and bounded prospective fix, but #1752 itself still needs exact-head hosted/review acceptance and the current generated dependency lanes still require owner-specific reconciliation. Do not count their direct generated branches as accepted security or compatibility upgrades.

**Data-hygiene duplicate-owner gate: PASS for #1746 convergence, not feature delivery.** The generated weak-digest and regex-only duplicate surfaces are removed from effective product delta and canonical #1361/#1418 ownership is preserved. This does not make either canonical feature owner merge-ready.

Do not claim completion from routine reporting, queued checks, historical GREEN, mutable releases, generated-provenance branches, dependency mega-groups, unmeasured performance claims, weak-digest security labelling, regex-only URL evidence, source-only correctness, malformed-versus-unsupported locale collapse, wildcard provenance fabrication, repeated extension singletons, duplicate variants, reserved multi-extlang occupancy or unresolved exact-head acceptance evidence. Every run must fresh-read live authority before mutation or acceptance.