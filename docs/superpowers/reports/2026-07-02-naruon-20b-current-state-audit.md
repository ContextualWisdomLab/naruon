# Naruon 20B Current State Audit

Audit date: 2026-07-02 KST

## Decision Being Supported

Question: can the current Naruon repository be treated as a 2,000,000,000 KRW sale-ready program?

Decision: no. The current state supports a controlled buyer technical review for the implemented frontend pilot slice and now has a localhost-only full-product route smoke gate, but it is still not a full enterprise procurement package. The gap is not only code. The missing work includes full interaction coverage, production deployment proof, live provider integration, security/compliance packaging, operations, analytics/ROI evidence, and buyer handoff material.

## Current Goal Registration

The active Goal is to move `ContextualWisdomLab/naruon` toward a 20B KRW enterprise-sale submission package using Figma, Product Design, Superpowers, Ponytail, and Data Analytics, without Figma Code Connect and without waiting for review-process delays.

## Repository State

Current branch:

```text
sellable-pilot-hardening-2026-07-02
```

Latest commits:

```text
a970b78 Test pilot smoke localhost guard
8ad4499 Harden Naruon enterprise sale readiness
80b613a Document Naruon pilot PR handoff
439beb4 Prepare Naruon commercial pilot frontend
00e9c15 Merge pull request #888 from ContextualWisdomLab/codex/visual-gap-round2
```

Working tree:

```text
 M .Jules/palette.md
 M .Jules/sentinel.md
```

Interpretation: `.Jules/*` changes are preserved user changes and are not part of this sale-readiness package.

## PR #893 State

PR:

- URL: `https://github.com/ContextualWisdomLab/naruon/pull/893`
- Title: `Naruon 상용 파일럿 프론트엔드 준비`
- Base: `develop`
- Head branch: `sellable-pilot-hardening-2026-07-02`
- Head SHA: `a970b78c5eb6664e844b48ce15689feb0c27bda2`
- Mergeable: `MERGEABLE`
- Merge state: `BLOCKED`
- Review decision: `CHANGES_REQUESTED`

Current check interpretation:

- Product-relevant checks that were observed successful include frontend, backend, Bandit, Trivy, CodeQL, dependency review, image validation, Strix, scorecard, metadata-only governance, queue scan, and coverage evidence.
- `opencode-review` was observed `IN_PROGRESS`.
- The stale review decision and review wait are not blockers under the current user instruction.
- A failing check with concrete product, security, or build evidence would be a blocker.

## Open GitHub Issue

Open issue:

- `#634 Track post-merge security gate failure on PR #631`
- URL: `https://github.com/ContextualWisdomLab/naruon/issues/634`
- Status: open
- Branch follow-up: `scripts/ci/pr_governance_gate.sh` now exits non-zero after posting or updating a blocker comment, with regression evidence in `docs/superpowers/reports/2026-07-02-naruon-security-governance-followup.md`.
- Meaning: governance/security gate hardening remains an enterprise-readiness risk until this patch lands on the trusted base branch and issue #634 is closed with remote evidence.
- Current interpretation: this is not a current PR #893 product-code failure, but it must be resolved or explicitly disclosed before treating the program as final procurement-ready.

## Product Design Context

Product Design saved context preflight:

```json
{
  "exists": false,
  "status": "missing",
  "entries": []
}
```

Interpretation: use repository sources as the authoritative design context. The durable source set is:

- `docs/ui-ux/naruon-ui-ux-mapping.md`
- `docs/ui-ux/mockups/mockup_01.png` through `mockup_41.png`
- `docs/ui-ux/reference-set-2026-06-18/images/`
- `docs/ui-ux/individual-assets-2026-06-22/manifest.tsv`

## Figma State

Current Figma file:

- `https://www.figma.com/design/68b5XB58w8nwT2LYOOnikK`
- File key: `68b5XB58w8nwT2LYOOnikK`

Observed through Figma metadata:

```text
Top-level pages:
- 0:1: Source Map
```

Observed through `search_design_system` with `disableCodeConnect=true`:

```json
{
  "components": [],
  "variables": [],
  "styles": []
}
```

Interpretation:

- Figma Code Connect was not used.
- The initial top-level metadata response did not show all pages claimed by older local reports.
- `use_figma` was used to repair missing required pages without Code Connect.
- The repair call reported that `Foundations`, `Components`, `Desktop Screens`, `Mobile Screens`, and `QA Notes` already existed and created `Interaction States` (`15:2`) plus `Sales Demo` (`15:3`).
- Direct metadata for `Sales Demo` (`15:3`) confirmed the new page and frame.
- The first buyer-demo frame now exists as `Sales Demo / 20B Enterprise Review Flow` (`16:2`).
- A final screenshot was downloaded to `/tmp/naruon-20b-sales-demo-final.png`; it is a 1080 x 608 PNG and visual inspection found no text overlap, clipped bottom copy, or placeholder shimmer.
- Responsive Product Design QA evidence now exists in `QA Notes / Naruon 20B Responsive QA Evidence` (`18:3`) with the uploaded contact-sheet image target (`18:7`).
- Because design system search is empty, the first pass should use local Naruon tokens/components derived from repo mockups, not a pretend external library.

## Existing Product Coverage

Frontend app routes currently exist for:

```text
/
/mail
/search
/calendar
/tasks
/projects
/data
/ai-hub
/security
/settings
/tools
/prompt-studio
```

Important frontend anchors:

- `frontend/src/components/EmailDetail.tsx`
- `frontend/src/components/SearchLayout.tsx`
- `frontend/src/components/SourceDrawer.tsx`
- `frontend/src/lib/product-events.ts`
- `frontend/scripts/pilot-ui-smoke.mjs`
- `frontend/scripts/pilot-ui-smoke.test.mjs`
- `frontend/scripts/full-product-ui-smoke.mjs`
- `frontend/scripts/full-product-ui-smoke.test.mjs`
- `docs/superpowers/reports/2026-07-02-naruon-20b-responsive-product-design-qa.md`
- `docs/superpowers/reports/assets/2026-07-02-naruon-responsive-qa-contact-sheet.png`

Backend APIs and services exist for:

- auth/session
- accounts
- email
- calendar
- tasks
- search
- ontology/network
- data
- AI Hub
- LLM providers
- security
- runtime/tenant config
- WebDAV/DAV
- provider writeback retry
- RBAC and URL validation

Interpretation: the repository has broad product scaffolding. The remaining sale-readiness problem is not route existence. It is buyer-visible completeness, production-path proof, provider-write evidence, security/compliance packaging, and repeatable end-to-end validation.

## Analytics State

Existing local implementation:

- `frontend/src/lib/product-events.ts`
- `frontend/src/lib/product-events.test.ts`
- call sites in `EmailDetail.tsx` and `SearchLayout.tsx`
- event dictionary in `docs/superpowers/reports/2026-07-02-naruon-event-dictionary.md`

Current limitation:

- No live analytics warehouse or destination is confirmed.
- No live KPI value can be claimed.
- Product-event dispatch is browser-local and memory-bounded.

Interpretation: analytics is good enough for privacy-safe pilot instrumentation, not final ROI proof.

## Library And Submodule Decision

Decision for current phase:

- No submodule.
- No separately versioned library.
- No new dependency for product-event, UI, or smoke-test work unless existing platform tools cannot cover the need.

Reasoning:

- The repo already has `frontend`, `backend`, and `connector` boundaries.
- `frontend/package.json` is private and already includes the needed UI/test primitives.
- There is no current independent consumer requiring separate versioning.
- A submodule would add operational drag without improving buyer evidence.

Acceptable later extraction:

- Internal workspace package under `frontend/packages/` if product events, design tokens, or UI primitives are consumed by at least three internal surfaces.
- Git submodule only when ownership and release cadence are independent from `ContextualWisdomLab/naruon`.

## Gap Summary

P0 for 20B final sale readiness:

- Figma required pages were repaired through `use_figma`, but full screen coverage and durable QA screenshots for every buyer flow are not complete.
- Full ten-area Product Design route audit now has desktop/mobile evidence, expanded selected desktop/mobile workflow-state evidence across nine IA routes, mocked provider completion result-state evidence, search graph summary/canvas-label evidence, security source-governance evidence, startup-view reload persistence evidence, and basic automated accessibility evidence, but live provider completion, full result variants, broader settings persistence, and assistive-technology audit are not complete.
- Production deployment and rollback evidence is not packaged.
- Live provider-send and provider-write execution evidence is incomplete.
- Issue #634 has a branch-level fix, but remains open as a governance risk until merged and proven on the trusted base branch.
- Buyer package, security questionnaire, and SLA/support drafts now exist, but data-processing terms, buyer approval, and production incident evidence remain incomplete.
- ROI model is not backed by live measured data.

P1 for buyer technical review:

- Full-product smoke covers all ten IA routes on localhost, supports desktop/mobile capture through `NARUON_FULL_PRODUCT_VIEWPORTS=desktop,mobile`, and is wired into the branch CI workflow with desktop default. It now asserts expanded selected desktop/mobile buyer workflow states for mail, search, calendar, tasks, projects, data, AI Hub, security, and settings, including mocked provider-send/provider-write completion states, search graph summary/canvas-label states, knowledge WebDAV provider completion/no-retry states, project source boundary, data WebDAV materialization completion and WebDAV/unique-thread intents, AI Hub workflow/evaluation/run-history navigation, security source-governance/write-boundary/policy-decision states, security deny samples, settings save actions, startup-view reload persistence, and connector token rotation, plus basic accessibility checks for visible duplicate IDs, visible interactive accessible names, and keyboard Tab focus entry.
- Mobile Settings startup-view cards were fixed from a 3-column mobile grid to `grid-cols-1 sm:grid-cols-3` after responsive QA found awkward Korean label wrapping.
- Product events do not yet cover full-product funnels beyond mail/search.
- External analytics destination, retention, and consent are not approved.
- Figma `Sales Demo` has current evidence and `QA Notes` now contains the desktop/mobile contact sheet with expanded selected desktop/mobile workflow-state, mocked provider completion result-state, search graph summary/canvas-label proof, security source-governance proof, startup-view reload persistence, and basic accessibility evidence; live provider completion and assistive-technology evidence remain incomplete.

Non-blockers:

- Review process delay.
- `opencode-review` in progress.
- Stale `CHANGES_REQUESTED` when all current review threads are resolved and product checks are passing.

## Next Actions

1. Repair Figma page structure without Code Connect.
2. Confirm the branch CI full-product smoke result and tune runtime or browser install cost if needed.
3. Expand smoke assertions from selected actions to complete workflow completion paths and result variants.
4. Extend analytics and ROI reports without claiming live KPI values.
5. Merge the issue #634 governance patch and close the issue only after trusted-base remote evidence proves blocker comments fail the governance check.
6. Review buyer package, demo script, security questionnaire, and SLA/support drafts with buyer/legal/security owners.
7. Run local and remote verification before any completion claim.
