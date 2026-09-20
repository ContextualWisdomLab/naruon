# Storybook design-token library rollout plan

## Goal

Turn Naruon's repeated UI objects into a reviewable component library without breaking the current Next.js runtime or allowing documentation-only values to masquerade as production tokens.

## Current slice

This PR ships only the bounded first step:

1. Add a Storybook-readable CSS token adapter.
2. Test token categories, unique names, complete live-variable alias resolution, candidate-value labeling, and the no-remote-resource boundary.
3. Distinguish runtime-backed aliases from documentation-only candidate scales.
4. Document the security, standards, product, and Figma boundaries.

The CSS annotation file is a Storybook documentation adapter. It is not yet a tool-neutral Design Tokens Community Group (DTCG) exchange artifact.

## Follow-on implementation sequence

### Task 1 — Storybook 10.5 runtime and browser test baseline

- Use `@storybook/nextjs-vite`; Storybook's official Vitest addon requires that framework for Next.js.
- Pin an exact Storybook 10.5-compatible package set in `frontend/package.json`.
- Pin `storybook-design-token` v5 for Storybook 10 compatibility.
- Update `pnpm-lock.yaml` in the same commit.
- Add `storybook`, `build-storybook`, and non-interactive CI test scripts.
- Add `.storybook/main.ts`, `.storybook/preview.ts`, and `.storybook/vitest.setup.ts`.
- Create a separate Vitest project for Storybook browser tests because the application already uses Vitest 4.
- Validate Next.js 16.2, React 19, App Router, server/client component boundaries, the CSS pipeline, and browser mode on the exact PR head.
- Disable telemetry and prohibit remote assets in CI.

### Task 2 — candidate-scale audit

Audit actual frontend usage before promoting any literal scale.

- Inventory font size, line height, spacing, radius, and shadow values used by repeated components.
- Detect one-off values and distinguish deliberate exceptions from drift.
- Reconcile the inventory with the candidate categories in `storybook-design-tokens.css`.
- Promote only accepted values into the authoritative token graph.
- Remove rejected candidate values instead of preserving them for compatibility.
- Add usage evidence linking each accepted token to at least one component family.

### Task 3 — interoperable token graph

- Define a DTCG 2025.10 JSON artifact or deterministic converter.
- Add an ADR naming the authoritative token source and preventing circular CSS ↔ JSON generation.
- Model primitive values separately from light/dark semantic aliases.
- Preserve status and tenant-safe semantic modes without embedding tenant secrets.
- Validate token names, types, references, cycles, theme completeness, and generated CSS deterministically.
- Generate or verify the Storybook adapter from the accepted graph.
- Add a migration note for any renamed CSS custom properties.

### Task 4 — token documentation

- Configure the selected design-token addon.
- Render every category from `frontend/src/app/storybook-design-tokens.css`.
- Show maturity (`runtime-backed` or `candidate`) and component usage.
- Generate a usage map from source rather than maintaining it manually.
- Add a static-build smoke test proving all required categories are present.
- Prevent candidate tokens from appearing as approved component inputs.

### Task 5 — repeated UI primitives

Create stories for:

- Button / Async Action Button;
- Card / Evidence Card;
- Navigation Item / GNB and LNB entry;
- Evidence Pill / confidence and source-state labels;
- Modal / destructive confirmation;
- Empty, loading, permission-denied, provider-writeback-conflict, offline, and retry states.

Each story set must include default, hover, keyboard focus, disabled, busy, success, recoverable error, destructive, narrow viewport, 200% zoom, and dark-theme states where the component supports them.

### Task 6 — accessibility and interaction tests

- Install and pin Storybook's official accessibility addon.
- Configure production stories with `parameters.a11y.test = "error"`.
- Run rendered-DOM checks through the Storybook/Vitest browser integration.
- Add play-function tests for keyboard activation, focus return, busy-state announcements, and error recovery.
- Record manual checks for focus order, accessible names, screen-reader announcements, zoom/reflow, reduced motion, target size, and high-contrast behavior that automated heuristics cannot establish.
- Keep WCAG 2.2 as the conformance target without claiming that axe automation alone establishes conformance.

### Task 7 — Figma bridge

- Map accepted DTCG identifiers—not display labels or candidate literals—to Figma variables.
- Create primitive and semantic collections with light/dark modes and explicit scopes.
- Produce a code-to-Figma component mapping table before automation.
- Preserve component state APIs and accessibility annotations.
- Keep production/DTCG authority explicit; Figma must not silently overwrite code.
- Add Code Connect only after the Storybook and Figma component APIs match.

### Task 8 — CI and release gates

- Build Storybook as a static artifact.
- Prove no external font, analytics, image, or telemetry fetch is required.
- Run component interaction and accessibility checks on the exact PR head.
- Preserve existing application tests, 100% production coverage, typecheck, build, security, and dependency gates.
- Publish screenshots or a static Storybook artifact only after the build is reproducible and access-controlled where nonpublic product states are represented.
- Add deterministic visual baselines only after fonts, viewport, browser, locale, time, and animation are fixed.

## Merge gate for this PR

- Frontend tests must pass on the exact head.
- Every Storybook CSS alias must resolve to a production custom property.
- Every literal-value category must be marked `@status candidate`.
- Storybook-facing token names must be unique.
- No package or lockfile drift is allowed in this slice.
- Storybook runtime installation remains a separate review unit.
- No claim that DTCG exchange, Figma mapping, component stories, or Storybook runtime is already shipped is permitted.
