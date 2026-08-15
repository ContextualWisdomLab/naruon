# Storybook design-token contract

## Buyer-visible gap

Naruon has many screens and repeated interface objects, but a reviewer currently has to inspect the application manually to understand whether colors, typography, spacing, radius, and elevation are shared product decisions or one-off styling. That slows product review, Figma handoff, accessibility review, and future white-label work.

## Decision

Naruon exposes a static Storybook-readable token adapter at:

```text
frontend/src/app/storybook-design-tokens.css
```

The adapter annotates categories with the comment contract used by the `storybook-design-token` addon:

```css
/**
 * @tokens Naruon Colors
 * @presenter Color
 */
--naruon-token-primary: var(--primary);
```

This slice does not add Storybook runtime dependencies or mutate the pnpm lockfile. It establishes a reviewable token surface and regression tests first, so the dependency PR can install an exact framework and addon set without inventing the token taxonomy during installation.

## Authority and maturity classes

The adapter contains two explicitly different classes of values.

### Runtime-backed aliases

Colors, sidebar colors, font families, and radii use `var(--...)` aliases that must resolve to custom properties in `frontend/src/app/globals.css`. The regression test verifies every alias, not only a sampled subset. These aliases document current production behavior.

### Candidate scales

Font sizes, line heights, spacing, and elevation currently use literal values because equivalent named production custom properties do not yet exist. Their category comments include:

```css
@status candidate
```

Candidate values are documentation hypotheses, not production truth. A component story, production component, Figma variable, or cross-repository package must not consume them until a reviewed follow-on change either:

1. promotes them into the authoritative runtime/DTCG token graph and proves generated output parity; or
2. removes or replaces them after auditing actual component usage.

This distinction prevents a documentation adapter from silently becoming a second, conflicting design system.

## Storybook installation target

The follow-on runtime PR should use `@storybook/nextjs-vite`.

Naruon already uses Vitest 4, and Storybook's official Vitest addon requires a Vite-based framework; for Next.js projects it explicitly requires `@storybook/nextjs-vite`. The runtime PR must still execute an exact compatibility spike against Naruon's current Next.js, React, App Router, server/client component boundaries, CSS pipeline, and browser test environment.

The dependency PR must:

- pin the current stable Storybook 10.5-compatible package set;
- pin `storybook-design-token` v5, which targets Storybook 10 and newer;
- configure the Storybook Vitest addon as a separate Vitest project, as recommended for Vitest 4;
- update `frontend/package.json` and `pnpm-lock.yaml` together;
- add `.storybook/main.ts`, `.storybook/preview.ts`, and `.storybook/vitest.setup.ts`;
- add `storybook`, `build-storybook`, and non-interactive CI test scripts;
- disable telemetry and prohibit remote build-time assets.

## Token categories

| Category | Maturity | Purpose |
|---|---|---|
| Naruon Colors | Runtime-backed | App background, foreground, card, action, chart, status, border, and focus colors. |
| Naruon Sidebar Colors | Runtime-backed | Global navigation and workspace shell colors. |
| Naruon Typography | Runtime-backed | Korean-first UI and monospaced technical text font stacks. |
| Naruon Candidate Font Sizes | Candidate | Proposed caption, body, lead, title, and display scale. |
| Naruon Candidate Line Heights | Candidate | Proposed compact UI, ordinary body, and reading-dense text rhythm. |
| Naruon Candidate Spacing | Candidate | Proposed layout rhythm for cards, panels, drawers, and button groups. |
| Naruon Radius | Runtime-backed | Surface and control corner scale. |
| Naruon Candidate Elevation | Candidate | Proposed panel and floating-surface shadows. |

## Security and privacy boundary

The token adapter is static CSS only.

It must not:

- import remote fonts;
- fetch external images or styles;
- include user content;
- include provider credentials;
- encode tenant-specific branding secrets;
- replace runtime authorization, audit, or evidence controls.

A regression test rejects remote URL imports and external URLs from the token source.

## DTCG, Figma, and component-library boundary

The CSS annotation grammar is a Storybook-addon adapter, not a tool-neutral exchange contract. Before automating Figma or publishing tokens to other CWL products, Naruon must add a validated Design Tokens Community Group 2025.10 artifact or a deterministic converter and accept an ADR that names one authoritative source.

The required sequence is:

1. exact, reproducible `@storybook/nextjs-vite` runtime and browser tests;
2. audited promotion or rejection of candidate scales;
3. DTCG 2025.10 token graph with deterministic CSS generation or parity verification;
4. component stories that consume only accepted semantic tokens;
5. Figma variables and components mapped from stable token identifiers;
6. Code Connect or equivalent mapping after code and Figma component APIs agree.

Figma remains a review and collaboration surface. It must not silently overwrite production values.

## First component families

The first reusable families should be selected by product frequency and decision risk:

1. Button and Async Action Button;
2. Card and Evidence Card;
3. global and local Navigation Item;
4. Evidence Pill and confidence/source-state labels;
5. Modal and destructive confirmation;
6. empty, loading, permission-denied, provider-conflict, offline, and retry states.

Each family must expose keyboard focus, disabled, busy, success, recoverable error, destructive, narrow viewport, 200% zoom, and dark-theme states where applicable.

## Done criteria for this slice

- Token adapter exists in the frontend package.
- Every category is annotated for Storybook token documentation.
- Every runtime-backed alias resolves to a production custom property.
- Every literal-value category is explicitly marked `@status candidate`.
- Token names are unique.
- Tests enforce the no-remote-resource boundary.
- Doctoring records the current Storybook, DTCG, and WCAG references.
- The documentation does not claim Storybook runtime, DTCG exchange, Figma mapping, or component stories are already shipped.
