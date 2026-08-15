# Storybook design-token library rollout plan

## Goal

Turn Naruon's repeated UI objects into a reviewable component library without breaking the current Next.js runtime or adding unpinned design dependencies in the same slice as token-definition work.

## Current slice

This PR ships only the bounded first step:

1. Add a Storybook-readable CSS token adapter.
2. Test token categories, unique names, live CSS variable mappings, and the no-remote-resource boundary.
3. Validate every CSS alias against `globals.css` rather than sampling a few declarations.
4. Document the security, standards, and product boundary.

The CSS annotation file is a Storybook documentation adapter. It is not yet a tool-neutral Design Tokens Community Group (DTCG) exchange artifact.

## Follow-on implementation sequence

### Task 1 — Storybook runtime dependency

- Use the current stable Storybook major and pin exact compatible package versions.
- Select `@storybook/nextjs` or `@storybook/nextjs-vite` only after an executable compatibility spike against Next.js 16.2, React 19, the App Router, Naruon's CSS pipeline, and Vitest 4.
- Pin the `storybook-design-token` major that explicitly supports the selected Storybook major; addon v5 targets Storybook 10 and newer, whereas addon v4 targets Storybook 9.
- Pin package versions in `frontend/package.json`.
- Update `pnpm-lock.yaml` in the same commit.
- Add `storybook` and `build-storybook` scripts.
- Add `.storybook/main.ts` and `.storybook/preview.ts`.
- Disable telemetry and remote assets in CI.

### Task 2 — token docs and interoperable exchange

- Configure the selected design-token addon version.
- Render categories from `frontend/src/app/storybook-design-tokens.css`.
- Add a build test or smoke contract proving all categories are present.
- Define a DTCG 2025.10 JSON artifact or deterministic converter for Figma and cross-product exchange.
- Add an ADR that names the authoritative token source and prevents circular CSS ↔ JSON generation.
- Validate aliases, token types, theme overrides, and generated artifacts deterministically.

### Task 3 — repeated UI primitives

Create stories for:

- Button / Async Action Button;
- Card / Evidence Card;
- Navigation Item / GNB and LNB entry;
- Evidence Pill / confidence and source-state labels;
- Modal / destructive confirmation;
- Empty, loading, permission-denied, provider-writeback-conflict, offline, and retry states.

Each story set must include default, hover, keyboard focus, disabled, busy, success, recoverable error, destructive, narrow viewport, 200% zoom, and dark-theme states where the component supports them.

### Task 4 — accessibility and interaction tests

- Install and pin Storybook's official accessibility addon.
- Configure production stories with `parameters.a11y.test = "error"`.
- Run WCAG 2.2-oriented rendered-DOM checks through the Storybook/Vitest integration.
- Add play-function interaction tests for keyboard activation, focus return, busy-state announcements, and error recovery.
- Record manual checks for focus order, accessible names, screen-reader announcements, zoom/reflow, reduced motion, and high-contrast behavior that automated heuristics cannot establish.

### Task 5 — Figma bridge

- Map DTCG token identifiers—not display labels—to Figma variables.
- Produce a component-mapping table before using Figma automation.
- Preserve semantic modes for light, dark, status, and tenant-safe themes.
- Keep production CSS as the current source of runtime truth unless an accepted ADR moves authority to the DTCG artifact.
- Treat Figma as a review and collaboration surface, not a path that can silently overwrite production tokens.

### Task 6 — CI and release gates

- Build Storybook in CI as a static artifact.
- Prove no external font, analytics, image, or telemetry fetch is required.
- Run component interaction and accessibility checks on the exact PR head.
- Preserve the existing application test, coverage, typecheck, build, security, and dependency gates.
- Publish component screenshots or a static Storybook artifact only after the build is reproducible and access-controlled where product states contain nonpublic information.

## Merge gate for this PR

- Frontend test suite must pass on the exact head.
- Every Storybook CSS alias must resolve to a production custom property.
- Storybook-facing token names must be unique.
- No package or lockfile drift is allowed in this slice.
- Storybook dependency installation remains a separate review unit.
- No claim that DTCG exchange, Figma mapping, component stories, or Storybook runtime is already shipped is permitted.
